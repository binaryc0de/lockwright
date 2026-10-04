#!/usr/bin/env bash
# Downloads the CC0 materials and models used by the rooms into
# game/assets/core/third_party/, exactly as published (PLAN.md 8.6). Re-runnable;
# skips files that already exist. Every entry here is listed in ATTRIBUTION.md.
#   tools/thirdparty/fetch_cc0.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
dest="$root/game/assets/core/third_party"
need() { command -v "$1" >/dev/null || { echo "missing $1" >&2; exit 1; }; }
need curl; need jq; need unzip

# ambientCG material: <id> <resolution e.g. 2K-JPG>. Keeps colour, normal (GL), roughness, AO.
ambientcg() {
	local id=$1 res=$2 dir="$dest/ambientcg/$1"
	[[ -f "$dir/.done" ]] && return
	mkdir -p "$dir"
	local zip; zip="$(mktemp)"
	curl -fsSL -A escapebox-fetch -o "$zip" "https://ambientcg.com/get?file=${id}_${res}.zip"
	unzip -q -o "$zip" "*_Color.jpg" "*_NormalGL.jpg" "*_Roughness.jpg" "*_AmbientOcclusion.jpg" -d "$dir" || true
	rm -f "$zip"
	touch "$dir/.done"
	echo "ambientcg $id"
}

# Poly Haven texture set: <id> <res e.g. 2k>. diff, nor_gl, arm (AO/rough/metal packed).
polyhaven_tex() {
	local id=$1 res=$2 dir="$dest/polyhaven/$1"
	[[ -f "$dir/.done" ]] && return
	mkdir -p "$dir"
	for map in diff nor_gl arm; do
		curl -fsSL -o "$dir/${id}_${map}_${res}.jpg" \
			"https://dl.polyhaven.org/file/ph-assets/Textures/jpg/$res/$id/${id}_${map}_${res}.jpg"
	done
	touch "$dir/.done"
	echo "polyhaven texture $id"
}

# Poly Haven model as glTF with its includes: <id> <res e.g. 1k>.
polyhaven_model() {
	local id=$1 res=$2 dir="$dest/polyhaven/$1"
	[[ -f "$dir/.done" ]] && return
	mkdir -p "$dir"
	local files; files="$(curl -fsSL "https://api.polyhaven.com/files/$id")"
	curl -fsSL -o "$dir/${id}_${res}.gltf" "$(jq -r ".gltf[\"$res\"].gltf.url" <<<"$files")"
	jq -r ".gltf[\"$res\"].gltf.include | to_entries[] | \"\(.key) \(.value.url)\"" <<<"$files" |
		while read -r rel url; do
			mkdir -p "$dir/$(dirname "$rel")"
			curl -fsSL -o "$dir/$rel" "$url"
		done
	touch "$dir/.done"
	echo "polyhaven model $id"
}

# Kenney audio pack subset: <pack> <file>... (CC0, https://kenney.nl). The
# download link carries a hash, so it is read from the pack's page.
kenney_audio() {
	local pack=$1; shift
	local dir="$dest/kenney/$pack"
	[[ -f "$dir/.done" ]] && return
	mkdir -p "$dir"
	local url zip tmp
	url="$(curl -fsSL "https://kenney.nl/assets/$pack" | grep -o 'https://kenney.nl/media/pages/assets/[^"]*\.zip' | head -1)"
	zip="$(mktemp)"; tmp="$(mktemp -d)"
	curl -fsSL -o "$zip" "$url"
	unzip -q -o "$zip" -d "$tmp"
	cp "$(find "$tmp" -iname 'License.txt' | head -1)" "$dir/License.txt"
	for f in "$@"; do cp "$(find "$tmp" -name "$f" | head -1)" "$dir/$f"; done
	chmod -R u+w "$tmp"; rm -rf "$zip" "$tmp"
	touch "$dir/.done"
	echo "kenney $pack ($# sounds)"
}

ambientcg Carpet012 2K-JPG
ambientcg OfficeCeiling001 2K-JPG
polyhaven_tex painted_plaster_wall 2k
polyhaven_model desk_lamp_arm_01 1k
polyhaven_model mounted_fluorescent_lights 1k
polyhaven_model office_notepads 1k
polyhaven_model stationery_supplies 1k
polyhaven_model clipboard 1k
polyhaven_model cardboard_box_01 1k
polyhaven_model fire_alarm 1k
polyhaven_model security_camera_02 1k
polyhaven_tex concrete_floor_painted 2k
kenney_audio interface-sounds click_002.ogg confirmation_002.ogg error_004.ogg bong_001.ogg confirmation_004.ogg
kenney_audio impact-sounds impactMetal_heavy_002.ogg impactGeneric_light_002.ogg footstep_carpet_000.ogg footstep_carpet_001.ogg footstep_carpet_002.ogg footstep_carpet_003.ogg footstep_carpet_004.ogg
kenney_audio sci-fi-sounds forceField_001.ogg
kenney_audio rpg-audio doorOpen_1.ogg doorClose_2.ogg creak1.ogg handleSmallLeather.ogg bookFlip2.ogg metalLatch.ogg

# The Clockmaker's Study: room-specific downloads live in the room's own
# directory, so they ship only in its pack (ADR-0030), not in every client.
# Listed in game/rooms/clockmaker/assets/ATTRIBUTION.md.
dest="$root/game/rooms/clockmaker/assets/third_party"
polyhaven_tex old_wooden_floor_02 1k
polyhaven_tex dark_paneled_wood 1k
polyhaven_tex quatrefoil_jacquard_fabric 1k
polyhaven_tex velour_velvet 1k
polyhaven_tex plastered_wall_03 1k
polyhaven_tex dark_wooden_planks 1k
for m in ArmChair_01 lantern_chandelier_01 fancy_picture_frame_01 fancy_picture_frame_02 \
	book_encyclopedia_set_01 brass_candleholders Lantern_01 \
	bench_vice_01 hand_plane_no4 vintage_hand_drill magnifying_glass_01 screwdrivers_02 pliers \
	small_oil_can_01 vintage_pocket_watch vintage_oil_lamp ClassicConsole_01 vintage_suitcase \
	vintage_grandfather_clock_01 mantel_clock_01 vintage_wooden_drawer_01; do
	polyhaven_model "$m" 1k
done
