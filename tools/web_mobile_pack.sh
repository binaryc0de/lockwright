#!/usr/bin/env bash
# Adds the phone/tablet pack to an exported browser client (ADR-0038): exports
# index.mobile.pck (ETC2/ASTC textures; phones cannot use the desktop S3TC/BPTC
# ones) next to index.pck, and makes index.html load it on touch devices.
#   tools/web_mobile_pack.sh [build/client-web]
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT="${GODOT:-godot}"
DIR="${1:-build/client-web}"
[ -f "$DIR/index.html" ] || { echo "no $DIR/index.html; export client-web first" >&2; exit 2; }
"$GODOT" --headless --path game --export-pack client-web-mobile "$(realpath "$DIR")/index.mobile.pck" > build/export-client-web-mobile.log 2>&1 \
	|| { tail -20 build/export-client-web-mobile.log; exit 1; }
SIZE=$(stat -c %s "$DIR/index.mobile.pck")
# Same test as Device.wants_mobile_textures() in the game: the GPU has ETC2
# and lacks S3TC (phones and tablets). Decided by the GPU, not by touch: a
# touch laptop keeps the desktop pack, and a device with neither format gets
# the desktop pack, which Godot can unpack (slowly) rather than draw black.
PICK="(function () { try { var gl = document.createElement('canvas').getContext('webgl2'); if (gl \\&\\& !gl.getExtension('WEBGL_compressed_texture_s3tc') \\&\\& gl.getExtension('WEBGL_compressed_texture_etc')) { GODOT_CONFIG.mainPack = 'index.mobile.pck'; GODOT_CONFIG.fileSizes['index.mobile.pck'] = $SIZE; } var lose = gl \\&\\& gl.getExtension('WEBGL_lose_context'); if (lose) lose.loseContext(); } catch (e) {} })();"
grep -q "index.mobile.pck" "$DIR/index.html" && sed -i '/index\.mobile\.pck/d' "$DIR/index.html"
sed -i "/^const GODOT_CONFIG = /a $PICK" "$DIR/index.html"
grep -qF "GODOT_CONFIG.mainPack = 'index.mobile.pck'" "$DIR/index.html" || { echo "could not patch $DIR/index.html" >&2; exit 1; }
echo "index.mobile.pck: $SIZE bytes"
