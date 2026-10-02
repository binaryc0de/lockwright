# Engine Evaluation: Pluggable Co-op Escape Room Platform (research as of 2026-10-01)

> Research report produced by a sub-agent during planning. Verify version numbers before relying on them.

## Recommendation

**Prototype AND long-term platform: Godot 4.7.x (stable 4.7.2, Aug 2026).** Runner-up: Unreal Engine 5.8. Web stack (Three.js + Colyseus) is the alternative only if "open a link, no install" becomes a hard requirement. They can be the same engine; Godot's only real ceilings (web export without Forward+, no native sandbox) have workable paths.

## Comparison

| Criterion | Godot 4.7 | Unreal 5.8 | Unity 6.3 LTS / 6.6 | Web (Three.js r186 / Babylon 9 / PlayCanvas) |
|---|---|---|---|---|
| Solo-dev "pretty good" graphics | Good: Forward+ (Vulkan/D3D12/Metal), SDFGI/VoxelGI, SSR overhaul (4.6), AreaLight3D + HDR output (4.7), shader baker (4.5) | Best: Lumen/Nanite; Linux needs Vulkan SM6 | Very good: HDRP | Good-ish: WebGPU Baseline in all browsers since Nov 2025; clustered lighting in Three r185, Babylon 9 volumetrics; no SDFGI-class GI out of box |
| Room-pack packaging | `.pck`/`.zip` via `ProjectSettings.load_resource_pack()`; packs carry .tscn/.gd/assets; multiple packs stack | Content-only plugin -> `.pak` (+`.ucas/.utoc`); ModioUGC plugin (5.3-5.7) handles mount/discover | Addressables/AssetBundles = assets only; mod code needs Roslyn runtime compile (no unload) or Lua (MoonSharp/Lua-CSharp) | JS modules + glTF; a pack is a URL |
| Script sandboxing | None natively: pack scripts run with full privileges and (default `replace_files=true`) can overwrite core files. Mitigate with godot-sandbox (libriscv GDExtension, 4.4+: RISC-V sandbox for SafeGDScript/C++/Rust, timeouts, memory limits) or data-only rooms + signed packs (Crypto class) | None; Blueprint/C++ in a pak runs fully trusted | None; Roslyn mods trusted; Lua interpreters are sandboxable | Browser sandbox for free, but room JS still touches game state; use iframe/Worker + message bus for true isolation |
| Dedicated server Linux | Built-in: "Dedicated Server" export strips render/audio, `--headless`, ENetMultiplayerPeer + RPC/MultiplayerSynchronizer | Yes, but requires engine source build from GitHub (launcher binary cannot build server targets) | NGO (MIT) targets Linux; Unity sold Multiplay hosting to Rocket Science (Mar 2026) | Colyseus 0.18 (Aug 2026, MIT): Node authoritative rooms over WebSockets; WebRTC only for P2P |
| Cloud cost | ~$3/mo t4g.nano reported; Oracle Always-Free VM works; AWS Graviton ARM fine | Server image is multi-GB; source build CI is heavy | Similar to Godot | Cheapest: Node on any $5 VPS or Colyseus Cloud $15/mo |
| AI-agent friendliness | Best: .tscn/.tres/.gd/project.godot are all plain text; 2026 practitioner consensus pairs Claude Code/Codex with Godot or web | Worst: .uasset/Blueprint binary; C++ fine but content is opaque | Middle: YAML scenes with GUID soup, C# fine | Best: everything is code |
| Learning curve for the owner | Lowest (existing GDScript + Linux/ARM export) | Highest (C++/Blueprint, giant builds) | Medium | Medium; you own more plumbing (physics, nav, audio) |
| Licensing | MIT, $0 | Free to $1M lifetime gross, then 5% | Personal free under $200k revenue/funding; Runtime Fee cancelled Sep 2024 | MIT (Three/Babylon/PlayCanvas engine/Colyseus) |

## Per-engine notes

**Godot 4.7.** Jolt physics default since 4.6; LibGodot embedding (4.6); D3D12 default on Windows (4.6). Room-pack design: a pack = `rooms/<id>/room.tscn` + `manifest.json` + CC0 assets (Poly Haven, ambientCG, Kenney, Quaternius via glTF). Caveats: (1) GDExtension `.so` binaries cannot load from inside a PCK, so room packs must be pure scripts/assets unless you ship a sandbox; (2) load packs with `replace_files=false` and a path allowlist so a pack cannot overwrite `res://core/*`; (3) godot-sandbox is third-party (MIT) and adds a RISC-V toolchain requirement for authors, so for the prototype treat packs as trusted and expose a small puzzle API (locks, triggers, inventory, hint text) that most rooms can use data-only; (4) web export is Compatibility renderer (WebGL2) only, so "no-install" would mean a visually downgraded client, and threaded builds need COOP/COEP headers.

**Unreal 5.8.** Visual ceiling is unmatched and ModioUGC gives a ready UGC pipeline, but dedicated server = source build (hours of compile, ~100 GB), Blueprint assets are binary so third-party AI agents must author in C++ or data tables, and a solo dev pays in iteration speed. Runner-up for a future "premium" client if Godot visuals disappoint.

**Unity 6.3 LTS (Dec 2025; 6.6 current; CoreCLR migrating).** Addressables are mature, but they deliberately exclude scripts, so room logic must be Lua or Roslyn-compiled C#. Licensing is now benign, but 2023 trust damage plus YAML scene noise make it the weakest fit for this profile.

**Web.** WebGPU Baseline removes the old "it's just WebGL" discount, and a room pack being a URL is the cleanest plugin story. Costs: you build inventory/interaction/physics (Rapier) from scratch, readable text on props and moody lighting take more hand-tuning, and 2-6 player state over WebSockets through Colyseus is easy. Keep as an escape hatch; the core room format could be mirrored as glTF + JSON so a web client remains possible later.

## Concrete plan
1. Prototype in Godot 4.7.2 with Forward+, ENet high-level multiplayer, one "core" project exporting client + dedicated-server builds for Linux x86/ARM.
2. Define `room.pck` spec now: manifest, entry scene, allowed node/script API, signed with Crypto; agents author .tscn/.gd text directly.
3. When opening to untrusted third parties, add godot-sandbox or restrict packs to data + sandboxed SafeGDScript; server validates puzzle state so a hostile client pack cannot cheat co-op.

## Sources
- https://godotengine.org/releases/4.5/ ; https://godotengine.org/releases/4.6/ ; https://godotengine.org/download/archive/4.7-stable/
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html
- https://docs.godotengine.org/en/4.5/tutorials/export/exporting_for_web.html
- https://github.com/libriscv/godot-sandbox
- https://gameye.com/blog/godot-dedicated-server-hosting/ ; https://vksegfault.github.io/posts/godot-server-aws-azure/
- https://gameye.com/blog/unreal-engine-5-dedicated-server-docker-container/ ; https://github.com/modio/modio-ue-modiougc ; https://en.wikipedia.org/wiki/Unreal_Engine_5
- https://unity.com/blog/unity-is-canceling-the-runtime-fee ; https://unity.com/blog/unity-6-3-lts-is-now-available ; https://dev.to/gamedevtoollab/choosing-the-right-real-time-networking-stack-for-unity-in-2026-29f4 ; https://github.com/DipCrai/UnityModLoaderSystem
- https://vr.org/articles/webgpu-baseline-2026-three-js-webxr-default ; https://www.utsubo.com/blog/threejs-2026-what-changed ; https://docs.colyseus.io/
- https://chierhu.medium.com/ai-coding-tools-for-video-game-development-a-first-principles-analysis-of-what-actually-works-90dfa10edd13
