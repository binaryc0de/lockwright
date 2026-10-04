"""Assembles a room's intro trailer with Blender's sequencer and FFmpeg
(docs/research/06-intro-videos.md). Runs under Blender only:

  blender -b --factory-startup --python tools/trailer/assemble.py -- \
      --record rec.avi --out-dir media/rooms/<id> [--narration n.wav --narration-start 1.0] \
      [--pre clip1.mp4,clip2.mp4] [--poster-at 6.0] [--width 1280 --height 720]

Story clips (--pre) play first, then the recording with its own room sound;
the narration starts --narration-start seconds into the recording. Writes
intro.mp4 (H.264/AAC, which every current browser plays) and poster.jpg (the
title card by default).
"""
import argparse
import os
import sys

import bpy

FPS = 30


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--record", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--narration", default="")
    p.add_argument("--narration-start", type=float, default=1.0)
    p.add_argument("--room-volume", type=float, default=0.55)
    p.add_argument("--pre", default="")
    p.add_argument("--poster-at", type=float, default=2.25)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def add_clip(ed, path, start, channel, w, h, volume):
    """A movie strip scaled to fill the canvas (Blender 5.2 ignores
    fit_method, so scale through the transform) plus its sound, if any."""
    m = ed.strips.new_movie(os.path.basename(path), path, channel=channel, frame_start=start)
    e = m.elements[0]
    m.transform.scale_x = w / e.orig_width
    m.transform.scale_y = h / e.orig_height
    end = m.frame_final_end
    try:
        s = ed.strips.new_sound(os.path.basename(path) + ".snd", path, channel=channel + 1, frame_start=start)
        s.volume = volume
    except (RuntimeError, TypeError):
        s = None  # no audio track
    return m, s, end


def fade(strip, prop, frame_from, frame_to, v_from, v_to):
    setattr(strip, prop, v_from)
    strip.keyframe_insert(prop, frame=frame_from)
    setattr(strip, prop, v_to)
    strip.keyframe_insert(prop, frame=frame_to)


def render(scn, path, container, codec, audio):
    ff = scn.render.ffmpeg
    ff.format, ff.codec, ff.audio_codec = container, codec, audio
    ff.constant_rate_factor = "MEDIUM"
    ff.ffmpeg_preset = "GOOD"
    ff.audio_bitrate = 128
    ff.audio_channels = "STEREO"
    scn.render.filepath = path
    bpy.ops.render.render(animation=True)
    print("TRAILER wrote", path)


def main():
    a = args()
    os.makedirs(a.out_dir, exist_ok=True)
    scn = bpy.context.scene
    scn.render.fps = FPS
    scn.render.resolution_x, scn.render.resolution_y, scn.render.resolution_percentage = a.width, a.height, 100
    ed = scn.sequence_editor_create()
    cursor = 1
    strips = []
    for path in [p for p in a.pre.split(",") if p]:
        m, s, cursor = add_clip(ed, path, cursor, 1, a.width, a.height, 1.0)
        strips.append((m, s))
    record_start = cursor
    m, s, cursor = add_clip(ed, a.record, record_start, 1, a.width, a.height, a.room_volume)
    strips.append((m, s))
    narration = None
    if a.narration:
        narration = ed.strips.new_sound("narration", a.narration, channel=4,
                                        frame_start=record_start + int(a.narration_start * FPS))
    scn.frame_start, scn.frame_end = 1, cursor - 1
    # Fade in from black over half a second, out over the last second.
    first, last = strips[0][0], strips[-1][0]
    fade(first, "blend_alpha", 1, 1 + FPS // 2, 0.0, 1.0)
    fade(last, "blend_alpha", scn.frame_end - FPS, scn.frame_end, 1.0, 0.0)
    for snd in [s for _, s in strips if s] + ([narration] if narration else []):
        fade(snd, "volume", scn.frame_end - FPS, scn.frame_end, snd.volume, 0.0)

    img = scn.render.image_settings
    if hasattr(img, "media_type"):
        img.media_type = "VIDEO"
    img.file_format = "FFMPEG"
    render(scn, os.path.join(a.out_dir, "intro.mp4"), "MPEG4", "H264", "AAC")

    if hasattr(img, "media_type"):
        img.media_type = "IMAGE"
    img.file_format = "JPEG"
    img.quality = 88
    scn.frame_set(record_start + int(a.poster_at * FPS))
    scn.render.filepath = os.path.join(a.out_dir, "poster.jpg")
    bpy.ops.render.render(write_still=True)
    print("TRAILER wrote", scn.render.filepath)


main()
