# Printable requests

Printed documents and screen images (PLAN.md 8.6, ASSET_PIPELINE.md Section 7). They live here, not in `assets/requests/`, because `tools/assetcheck` checks GLB assets only. Codex builds each with `tools/printables/` into the path the request names, plus a 25 % legibility preview in `assets/previews/printables/<doc_id>_25.png` and a short report in `assets/reports/printables/<doc_id>.md`.
