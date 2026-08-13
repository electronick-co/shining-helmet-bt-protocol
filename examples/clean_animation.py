"""Upload a clean animated GIF (black background, moving rainbow bar).

Compresses well, so it may fit in 1-2 blocks — multi-block is already verified;
this is a visual-quality check.
"""
from __future__ import annotations
import argparse
import asyncio
import os

from shining_helmet import ShiningHelmet, constants as C, protocol, images

OUT_GIF = os.path.join(os.path.dirname(__file__), "..", "decoded", "clean_animation.gif")


def build(n_frames: int = 12) -> str:
    from PIL import Image
    frames = []
    for f in range(n_frames):
        im = Image.new("RGB", (C.WIDTH, C.HEIGHT), (0, 0, 0))
        px = im.load()
        bar_x = (f * C.WIDTH) // n_frames
        for y in range(C.HEIGHT):
            for dx in range(3):
                px[(bar_x + dx) % C.WIDTH, y] = [
                    (255, 0, 0), (255, 160, 0), (0, 255, 0),
                    (0, 160, 255), (160, 0, 255), (255, 255, 255)][y % 6]
        frames.append(im)
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    frames[0].save(OUT_GIF, save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    return OUT_GIF


async def run(args):
    gif = images.encode_gif(build(args.frames))
    print(f"clean animation: {len(gif)} bytes -> "
          f"{len(protocol.upload_blocks(gif))} block(s)")
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.upload_bytes(gif)
        print("uploaded — panel should show ONLY a moving rainbow bar on black.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--frames", type=int, default=12)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
