package main

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// Origin kinds derived from a request's Transforms section.
const (
	OriginBaseCenter = "base_center"
	OriginMountBack  = "mount_back"
	OriginHinge      = "hinge"
)

// Default budgets when a request omits them (docs/ASSET_PIPELINE.md section 4).
const (
	defaultTextureMaxPx = 2048
	defaultPropTris     = 20000
	defaultHeroTris     = 60000
)

// Request is the machine-checkable part of assets/requests/<id>.md.
type Request struct {
	ID             string
	Title          string // the "# <asset_id>" heading
	Status         string
	Class          string
	TriangleBudget int
	TextureMaxPx   int
	Parts          []string
	Animations     []string
	Origin         string
	// Notes are parser warnings (defaults applied, unexpandable ranges).
	Notes []string
}

var (
	reBudgetNum  = regexp.MustCompile(`(?:<=|≤)\s*([0-9][0-9_,]*)\s*(\([^)]*\))?`)
	rePx         = regexp.MustCompile(`(?:<=|≤)\s*([0-9][0-9_,]*)\s*px`)
	reBacktick   = regexp.MustCompile("`([^`]+)`")
	reRange      = regexp.MustCompile("`([^`]+)`\\s*(?:\\.\\.\\.?|…)\\s*`([^`]+)`")
	reTrailDigit = regexp.MustCompile(`^(.*?)(\d+)$`)
	// Template boilerplate that mentions wall mounting for every prop; it must
	// not turn a floor prop into a wall prop.
	templateWallAside = "(or wall-mount plane for wall props)"
)

type section struct {
	heading string // lower-cased heading text without "## "
	body    []string
}

// ParseRequest parses a request file's text. id comes from the file name.
func ParseRequest(id, text string) (*Request, error) {
	r := &Request{ID: id}
	text = strings.ReplaceAll(text, "\r\n", "\n")
	lines := strings.Split(text, "\n")

	var sections []section
	cur := &section{heading: ""}
	for _, ln := range lines {
		trimmed := strings.TrimSpace(ln)
		if strings.HasPrefix(trimmed, "# ") && r.Title == "" {
			r.Title = strings.TrimSpace(strings.TrimPrefix(trimmed, "# "))
			continue
		}
		if strings.HasPrefix(trimmed, "## ") {
			sections = append(sections, *cur)
			cur = &section{heading: strings.ToLower(strings.TrimSpace(strings.TrimPrefix(trimmed, "## ")))}
			continue
		}
		cur.body = append(cur.body, ln)
		if v, ok := fieldValue(trimmed, "status"); ok && r.Status == "" {
			r.Status = firstWord(v)
		}
		if v, ok := fieldValue(trimmed, "class"); ok && r.Class == "" {
			r.Class = firstWord(v)
		}
	}
	sections = append(sections, *cur)
	find := func(prefix string) *section {
		for i := range sections {
			if strings.HasPrefix(sections[i].heading, prefix) {
				return &sections[i]
			}
		}
		return nil
	}

	if r.Status == "" {
		return nil, fmt.Errorf("request %s: no **Status:** line", id)
	}
	if r.Class == "" {
		return nil, fmt.Errorf("request %s: no **Class:** line", id)
	}

	// Budgets.
	budgets := find("budgets")
	r.TextureMaxPx = defaultTextureMaxPx
	if budgets != nil {
		for _, ln := range budgets.body {
			if m := rePx.FindStringSubmatch(ln); m != nil {
				n, err := parseNum(m[1])
				if err != nil {
					return nil, fmt.Errorf("request %s: texture budget: %w", id, err)
				}
				r.TextureMaxPx = n
				break
			}
		}
		for _, ln := range budgets.body {
			if !strings.Contains(strings.ToLower(ln), "triangles") {
				continue
			}
			n, err := pickTriangleBudget(ln, r.Class)
			if err != nil {
				return nil, fmt.Errorf("request %s: %w", id, err)
			}
			r.TriangleBudget = n
			break
		}
	}
	if r.TriangleBudget == 0 {
		r.TriangleBudget = defaultPropTris
		if r.Class == "hero" {
			r.TriangleBudget = defaultHeroTris
		}
		r.Notes = append(r.Notes, fmt.Sprintf("no Triangles budget found; using the %s default %d", r.Class, r.TriangleBudget))
	}

	// Named parts and animations: backticked names in the first table column.
	if s := find("named parts"); s != nil {
		parts, notes := firstColumnNames(s.body)
		r.Parts = parts
		r.Notes = append(r.Notes, notes...)
	}
	if s := find("animations"); s != nil {
		anims, notes := firstColumnNames(s.body)
		r.Animations = anims
		r.Notes = append(r.Notes, notes...)
	}

	// Origin kind.
	r.Origin = OriginBaseCenter
	if s := find("transforms"); s != nil {
		body := strings.ToLower(strings.Join(s.body, "\n"))
		body = strings.ReplaceAll(body, templateWallAside, "")
		switch {
		case strings.Contains(body, "wall") || strings.Contains(body, "mount"):
			r.Origin = OriginMountBack
		case strings.Contains(body, "hinge"):
			r.Origin = OriginHinge
		}
	}
	return r, nil
}

// fieldValue matches "**Name:** value" (markdown emphasis optional).
func fieldValue(line, name string) (string, bool) {
	clean := strings.TrimLeft(line, "-*> \t")
	clean = strings.ReplaceAll(clean, "**", "")
	clean = strings.ReplaceAll(clean, "__", "")
	low := strings.ToLower(clean)
	if !strings.HasPrefix(low, name+":") {
		return "", false
	}
	return strings.TrimSpace(clean[len(name)+1:]), true
}

func firstWord(s string) string {
	s = strings.TrimSpace(strings.ReplaceAll(s, "`", ""))
	if f := strings.Fields(s); len(f) > 0 {
		return strings.ToLower(strings.TrimRight(f[0], ".,;|"))
	}
	return ""
}

func parseNum(s string) (int, error) {
	s = strings.NewReplacer(",", "", "_", "").Replace(s)
	return strconv.Atoi(s)
}

// pickTriangleBudget takes "<= N" numbers from a Triangles line; with
// several, the one annotated "(hero)" wins for hero requests, else the first.
func pickTriangleBudget(line, class string) (int, error) {
	ms := reBudgetNum.FindAllStringSubmatch(line, -1)
	if len(ms) == 0 {
		return 0, fmt.Errorf("Triangles line has no '<= N' budget: %q", strings.TrimSpace(line))
	}
	chosen := ms[0][1]
	if class == "hero" {
		for _, m := range ms {
			if strings.Contains(strings.ToLower(m[2]), "hero") {
				chosen = m[1]
				break
			}
		}
	}
	return parseNum(chosen)
}

// firstColumnNames collects backticked names from the first column of the
// markdown table(s) in a section, expanding `x_0` .. `x_9` ranges.
func firstColumnNames(body []string) (names, notes []string) {
	seen := map[string]bool{}
	add := func(n string) {
		n = strings.TrimSpace(n)
		if n != "" && !seen[n] {
			seen[n] = true
			names = append(names, n)
		}
	}
	for _, ln := range body {
		t := strings.TrimSpace(ln)
		if !strings.HasPrefix(t, "|") {
			continue
		}
		cells := strings.Split(strings.Trim(t, "|"), "|")
		cell := strings.TrimSpace(cells[0])
		if strings.Trim(cell, "-: ") == "" {
			continue // separator row
		}
		// Expand ranges first, then take the remaining single names.
		for _, m := range reRange.FindAllStringSubmatch(cell, -1) {
			exp, ok := expandRange(m[1], m[2])
			if !ok {
				notes = append(notes, fmt.Sprintf("cannot expand range `%s` .. `%s`; using both endpoints only", m[1], m[2]))
			}
			for _, n := range exp {
				add(n)
			}
		}
		rest := reRange.ReplaceAllString(cell, "")
		for _, m := range reBacktick.FindAllStringSubmatch(rest, -1) {
			add(m[1])
		}
	}
	return names, notes
}

// expandRange expands prefixN .. prefixM (same prefix, numeric suffix).
// Zero padding of the first endpoint is preserved.
func expandRange(a, b string) ([]string, bool) {
	ma, mb := reTrailDigit.FindStringSubmatch(a), reTrailDigit.FindStringSubmatch(b)
	if ma == nil || mb == nil || ma[1] != mb[1] {
		return []string{a, b}, false
	}
	lo, _ := strconv.Atoi(ma[2])
	hi, _ := strconv.Atoi(mb[2])
	if hi < lo || hi-lo > 1000 {
		return []string{a, b}, false
	}
	width := 0
	if strings.HasPrefix(ma[2], "0") && len(ma[2]) > 1 {
		width = len(ma[2])
	}
	out := make([]string, 0, hi-lo+1)
	for i := lo; i <= hi; i++ {
		out = append(out, fmt.Sprintf("%s%0*d", ma[1], width, i))
	}
	return out, true
}
