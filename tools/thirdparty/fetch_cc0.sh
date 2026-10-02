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
