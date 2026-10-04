// Command narrate turns a room's narration script into speech with Gemini
// TTS (docs/research/06-intro-videos.md):
//
//	go run ./tools/narrate media/rooms/<room_id>         # narration.json -> narration.wav
//	go run ./tools/narrate -force media/rooms/<room_id>  # regenerate even if up to date
//
// narration.json: {"voice": "Sulafat", "style": "...", "text": "...", "model"?: "...", "start_s"?: 1.0}.
// The API key comes from GEMINI_API_KEY or ~/.config/escapebox/gemini_api_key
// and is never printed. An up-to-date narration.wav is not regenerated.
package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const defaultModel = "gemini-3.8-flash-tts"

// Script is a room's narration.json.
type Script struct {
	Voice  string  `json:"voice"`
	Style  string  `json:"style"`
	Text   string  `json:"text"`
	Model  string  `json:"model"`
	StartS float64 `json:"start_s"`
}

func main() {
	force := flag.Bool("force", false, "regenerate even if narration.wav is newer than narration.json")
	endpoint := flag.String("endpoint", "https://generativelanguage.googleapis.com/v1beta/interactions", "Gemini Interactions API endpoint")
	flag.Parse()
	if flag.NArg() != 1 {
		fmt.Fprintln(os.Stderr, "usage: narrate [-force] media/rooms/<room_id>")
		os.Exit(2)
	}
	if err := run(flag.Arg(0), *endpoint, *force); err != nil {
		fmt.Fprintln(os.Stderr, "narrate:", err)
		os.Exit(1)
	}
}

func run(dir, endpoint string, force bool) error {
	in, out := filepath.Join(dir, "narration.json"), filepath.Join(dir, "narration.wav")
	if !force && newer(out, in) {
		fmt.Println("up to date:", out)
		return nil
	}
	b, err := os.ReadFile(in)
	if err != nil {
		return err
	}
	var s Script
	if err := json.Unmarshal(b, &s); err != nil {
		return fmt.Errorf("%s: %w", in, err)
	}
	if strings.TrimSpace(s.Text) == "" || s.Voice == "" {
		return fmt.Errorf("%s: needs text and voice", in)
	}
	key, err := apiKey()
	if err != nil {
		return err
	}
	wav, err := synthesize(endpoint, key, s)
	if err != nil {
		return err
	}
	if err := os.WriteFile(out, wav, 0o644); err != nil {
		return err
	}
	fmt.Printf("wrote %s (%d bytes)\n", out, len(wav))
	return nil
}

func newer(a, b string) bool {
	sa, errA := os.Stat(a)
	sb, errB := os.Stat(b)
	return errA == nil && errB == nil && !sa.ModTime().Before(sb.ModTime())
}

func apiKey() (string, error) {
	if k := strings.TrimSpace(os.Getenv("GEMINI_API_KEY")); k != "" {
		return k, nil
	}
	home, _ := os.UserHomeDir()
	if b, err := os.ReadFile(filepath.Join(home, ".config", "escapebox", "gemini_api_key")); err == nil {
		if k := strings.TrimSpace(string(b)); k != "" {
			return k, nil
		}
	}
	return "", errors.New("no API key: set GEMINI_API_KEY or write it to ~/.config/escapebox/gemini_api_key (chmod 600)")
}

// request builds the Interactions API body for single-speaker speech.
func request(s Script) map[string]any {
	model := s.Model
	if model == "" {
		model = defaultModel
	}
	text := map[string]any{"type": "text", "text": s.Text}
	if s.Style != "" {
		text["annotations"] = []any{map[string]any{"type": "speech_metadata", "style": s.Style}}
	}
	return map[string]any{
		"model":             model,
		"input":             []any{map[string]any{"type": "user_input", "content": []any{text}}},
		"response_format":   map[string]any{"type": "audio", "mime_type": "audio/wav"},
		"generation_config": map[string]any{"speech_config": []any{map[string]any{"voice": s.Voice}}},
	}
}

func synthesize(endpoint, key string, s Script) ([]byte, error) {
	body, _ := json.Marshal(request(s))
	req, err := http.NewRequest(http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-goog-api-key", key)
	resp, err := (&http.Client{Timeout: 3 * time.Minute}).Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 64<<20))
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Gemini answered HTTP %d: %.400s", resp.StatusCode, raw)
	}
	return decodeAudio(raw)
}

// decodeAudio returns the WAV bytes from an Interactions response
// (steps[].content[].data, base64).
func decodeAudio(raw []byte) ([]byte, error) {
	var r struct {
		Steps []struct {
			Content []struct {
				Data string `json:"data"`
			} `json:"content"`
		} `json:"steps"`
	}
	if err := json.Unmarshal(raw, &r); err != nil {
		return nil, fmt.Errorf("response: %w", err)
	}
	for _, st := range r.Steps {
		for _, c := range st.Content {
			if c.Data == "" {
				continue
			}
			wav, err := base64.StdEncoding.DecodeString(c.Data)
			if err != nil {
				return nil, fmt.Errorf("audio: %w", err)
			}
			if len(wav) < 44 || string(wav[:4]) != "RIFF" {
				return nil, errors.New("audio is not a WAV file")
			}
			return wav, nil
		}
	}
	return nil, errors.New("no audio in the response")
}
