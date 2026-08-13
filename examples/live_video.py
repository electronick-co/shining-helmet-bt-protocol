"""Live VIDEO / animation playback on the helmet (via screencast).

Plays animated GIF / WebP / APNG natively. For MP4/MOV install
`imageio imageio-ffmpeg`. Source is resized to 48x12.

Examples:
    python examples/live_video.py clip.gif --loops 3
    python examples/live_video.py movie.mp4 --stride 3 --fps 12
    python examples/live_video.py                       # built-in demo animation
"""
from __future__ import annotations
import argparse
import asyncio
import os

from shining_helmet import ShiningHelmet, images, constants as C

DEMO = os.path.join(os.path.dirname(__file__), "..", "decoded", "test_animation.gif")


def build_demo():
    """A simple looping demo GIF if none exists yet."""
    from PIL import Image
    import math
    frames = []
    for f in range(24):
        im = Image.new("RGB", (C.WIDTH, C.HEIGHT), (0, 0, 0))
        px = im.load()
        for x in range(C.WIDTH):
            y = int((math.sin(x / 6.0 + f / 3.0) * 0.5 + 0.5) * (C.HEIGHT - 1))
            px[x, y] = (255, 120, 0)
            if y + 1 < C.HEIGHT:
                px[x, y + 1] = (120, 40, 0)
        frames.append(im)
    os.makedirs(os.path.dirname(DEMO), exist_ok=True)
    frames[0].save(DEMO, save_all=True, append_images=frames[1:], duration=80, loop=0)
    return DEMO


async def run(args):
    src = args.source
    if not src:
        src = build_demo()
        print(f"no source given — using built-in demo {src}")

    if src.lower().endswith((".mp4", ".mov", ".mkv", ".avi", ".webm")):
        frames = list(images.iter_mp4_frames(src, stride=args.stride,
                                             max_frames=args.max_frames))
    else:
        frames = list(images.iter_video_frames(src, max_frames=args.max_frames))
    print(f">>> {len(frames)} frames from {os.path.basename(src)} "
          f"x{args.loops} @ {args.fps} fps")

    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        n = await h.stream(frames, fps=args.fps, loops=args.loops,
                           wait_ack=not args.no_ack, close_graffiti=True)
        print(f"    sent {n} frames")
    print("done.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", nargs="?", default=None, help="GIF/WebP/APNG or MP4 (with imageio)")
    p.add_argument("--address", default=None)
    p.add_argument("--fps", type=float, default=12.0)
    p.add_argument("--loops", type=int, default=2)
    p.add_argument("--stride", type=int, default=2, help="MP4: keep every Nth frame")
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--no-ack", action="store_true")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
