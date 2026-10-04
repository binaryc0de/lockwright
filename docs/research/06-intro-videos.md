# Intro videos per room (research, 2026-10-03)

**Question (owner):** add a short intro video per room, shown on the site before players start a game. Can Codex generate video clips; if not, how do we make them?

## Findings

| Option | What it gives | Cost | Fit |
|---|---|---|---|
| **Godot Movie Maker** (`--write-movie`, built in since 4.0) | Frame-perfect, non-real-time recording of the real room: scripted camera moves, the room's own lights, props and synthesised sound, title text as UI. Output MJPEG AVI or PNG + WAV. | Free, local. **Spike:** 10 s at 1080p/30 fps recorded in 18 s on the RTX 3080 Ti. | Best: always matches the room, re-render when the room changes, no external service. |
| **Blender 5.2 FFmpeg encoding** (headless, already installed and pinned) | Assembles the recording (plus music/narration and title cards in the sequencer) into WebM (VP9) and MP4 (H.264). | Free, local. **Spike:** the 10 s clip encoded to 4.2 MB MP4 / 7.9 MB WebM at 720p; Chrome played the MP4 (`video playing 1280x720 10.03`). | Fills the missing system ffmpeg; scriptable in the Codex lane. |
| **Codex `image_generation`** (stable, enabled in Codex CLI 0.160) | Still images only: poster frames, title cards, period key art (e.g. a foggy Clerkenwell street). | Included in the Codex plan. | Good for posters and stills that Movie Maker footage cannot show. **Codex has no video generation.** |
| **OpenAI Sora 2 (Videos API)** | Text/image-to-video. | Was $0.10/s (sora-2), $0.30-0.70/s (pro). | **Gone:** OpenAI removed the Videos API, sora-2 and sora-2-pro on 24 September 2026. |
| **Google Veo 3.1 (Gemini API)** | Text/image-to-video, 8 s clips with generated audio, 720p-4K; image-to-video keeps a look consistent. | Fast tier about $0.10-0.12/s (720p/1080p), standard $0.40/s: roughly $1-3 per 8 s clip. | Optional extra for a story establishing shot (the street outside, the funeral, Mrs Pell at the door) that the room itself cannot show. Needs a Google API key and billing (the owner's call); AI clips do not match the room exactly. |

## Recommendation

1. **Trailer from the room itself** (default for every room): a short `RoomTrailer` tool scene in `game/tests/scenes/` that loads a room and plays a camera path from `game/rooms/<id>/trailer.json` (shots: position, look target, duration, caption). It is recorded with Movie Maker and encoded by a Blender script in `tools/` (WebM + MP4 + poster PNG), for about 20-40 s at 720p (about 5-10 MB). Captions come from the room's intro briefing. Shots must be planned around props (the spike's straight-line path flew through the chandelier).
2. **Stills from Codex**: a poster frame / title card per room via `image_generation`, also used as the video's `poster` and on the lobby card.
3. **Optional AI establishing shot** (Veo 3.1 Fast, image-to-video from the Codex key art) only if the owner wants story beyond the room, with a cap of one or two 8 s clips per room.
4. **Site**: an optional `briefing.intro_video` entry in `room.yaml` (schema, additive); the platform serves `/media/rooms/<id>/intro.{webm,mp4,png}` (videos stay out of the room pack, so the game download does not grow); the lobby room card and the game page get a muted, click-to-play `<video>` with the poster before "Start a game".
5. **Audio**: room tone and the room's own synthesised sounds come with the recording. Narration in Mrs Pell's voice would need TTS (a local open model, or a hosted voice API): a separate decision.

## Spike details

- Recording: `godot --path game --write-movie out.avi --fixed-fps 30 <scene>`, 301 frames, 46 MB MJPEG.
- Encoding: Blender sequencer movie strip; `image_settings.media_type = "VIDEO"`, `file_format = "FFMPEG"`, WEBM/VP9 or MPEG4/H264, CRF medium. `SequenceEditor.strips` (Blender 5 renamed `sequences`).
- Browser check: HTML5 `<video autoplay muted>` served over HTTP in headless Chrome reported playback; headless screenshots do not capture video overlays, so the check reads the `playing` event.

## Sources

- Godot Movie Maker: https://docs.godotengine.org/en/latest/tutorials/animation/creating_movies.html, https://godotengine.org/article/movie-maker-mode-arrives-in-godot-4/
- Sora 2 API shutdown and prices: https://unifically.com/blogs/sora-api, https://ecorpit.com/sora-2-videos-api-shutdown-migration-cost-2026/
- Veo 3.1 prices: https://www.buildfastwithai.com/blogs/google-veo-3-1-ai-video-generator, https://developers.googleblog.com/en/veo-3-and-veo-3-fast-new-pricing-new-configurations-and-better-resolution/
