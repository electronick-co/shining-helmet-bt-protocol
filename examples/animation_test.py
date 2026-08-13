"""Live test for the multi-block upload path (verify:upload-multipacket).

Builds a 48x12 animated GIF big enough to need several 4096-byte blocks, uploads
it with the decoded block framing, and dumps every notification with timestamps.

Expected per the decoded app protocol:
  * after each full block  -> notify 05 00 01 00 01  (READY: send next block)
  * after the last block   -> notify 05 00 01 00 03  (SAVED: file stored)
  * the panel then plays the animation, persisting across disconnect.

Usage:
    python examples/animation_test.py                 # ~8-frame moving-bar animation
    python examples/animation_test.py --frames 16     # bigger file, more blocks
    python examples/animation_test.py --gif my.gif    # upload your own animated GIF
"""
from __future__ import annotations
import argparse
import asyncio
import os
import time

from shining_helmet import ShiningHelmet, constants as C, protocol

OUT_GIF = os.path.join(os.path.dirname(__file__), "..", "decoded", "test_animation.gif")


def build_animation(n_frames: int) -> str:
    """A moving vertical rainbow bar + frame counter dots; visually unambiguous
    (direction = left->right) and poorly compressible enough to span blocks."""
    from PIL import Image
    frames = []
    for f in range(n_frames):
        im = Image.new("RGB", (C.WIDTH, C.HEIGHT), (0, 0, 0))
        px = im.load()
        bar_x = (f * C.WIDTH) // n_frames
        for y in range(C.HEIGHT):
            for dx in range(3):
                x = (bar_x + dx) % C.WIDTH
                px[x, y] = [(255, 0, 0), (255, 160, 0), (0, 255, 0),
                            (0, 160, 255), (160, 0, 255), (255, 255, 255)][y % 6]
        # textured background so the GIF doesn't compress below one block
        for y in range(C.HEIGHT):
            for x in range(C.WIDTH):
                if px[x, y] == (0, 0, 0):
                    px[x, y] = ((x * 37 + y * 11 + f * 53) % 64,
                                (x * 13 + y * 29 + f * 17) % 64,
                                (x * 7 + y * 41 + f * 31) % 64)
        # frame index dots along the top
        for i in range(f + 1):
            if i < C.WIDTH:
                px[i, 0] = (255, 255, 255)
        frames.append(im)
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    frames[0].save(OUT_GIF, save_all=True, append_images=frames[1:],
                   duration=150, loop=0)
    return OUT_GIF


async def run(args):
    notes = []
    t0 = time.monotonic()

    if args.gif:
        gif_path = args.gif
    else:
        gif_path = build_animation(args.frames)
    from shining_helmet import images
    gif = images.encode_gif(gif_path)         # 48x12, all frames preserved
    n_blocks = len(protocol.upload_blocks(gif))
    print(f"animated GIF: {gif_path}  (encoded {len(gif)} bytes -> {n_blocks} block(s))")
    if n_blocks < 2:
        print("NOTE: file fits in one block; multi-block framing won't be exercised."
              " Increase --frames.")

    async with ShiningHelmet(address=args.address) as h:
        h.notify_handlers.append(
            lambda b: notes.append((round(time.monotonic() - t0, 3), b.hex())))
        await h.power(True)
        print(">>> uploading", n_blocks, "block(s)...")
        await h.upload_bytes(gif)
        print(">>> upload returned OK — the panel should be animating now.")
        await asyncio.sleep(args.pause)

    print("\n=== notification log (t, hex) ===")
    for t, hexs in notes:
        print(f"  {t:7.3f}  {hexs}")
    if not notes:
        print("  (none)")
    print("\nIf the animation plays: tick verify:upload-multipacket + verify:upload-ack"
          " in VERIFY.md. Also note whether it persists after disconnect.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--frames", type=int, default=8)
    p.add_argument("--gif", default=None, help="upload this animated GIF instead")
    p.add_argument("--pause", type=float, default=6.0)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
