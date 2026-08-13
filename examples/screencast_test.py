"""Live test for the type-00 'screencast' path (verify:screencast).

Three phases, with pauses so a human can watch the panel:
  A. one frame WITHOUT graffiti mode (does it render at all outside graffiti?)
  B. graffiti open + one frame (the captured context)
  C. stream N frames of a bouncing-ball animation as fast as acks allow -> fps

Frame content per phase (all 48x12 PNGs):
  A: solid RED with a white border
  B: solid GREEN with a white border
  C: magenta bouncing ball on dark blue

Usage: python examples/screencast_test.py [--frames 60] [--no-ack]
"""
from __future__ import annotations
import argparse
import asyncio
import time

from shining_helmet import ShiningHelmet, constants as C


def solid(color, border=(255, 255, 255)):
    from PIL import Image
    im = Image.new("RGB", (C.WIDTH, C.HEIGHT), color)
    px = im.load()
    for x in range(C.WIDTH):
        px[x, 0] = px[x, C.HEIGHT - 1] = border
    for y in range(C.HEIGHT):
        px[0, y] = px[C.WIDTH - 1, y] = border
    return im


def ball_frame(t: float):
    from PIL import Image
    im = Image.new("RGB", (C.WIDTH, C.HEIGHT), (0, 0, 40))
    px = im.load()
    import math
    cx = (math.sin(t * 2.0) * 0.5 + 0.5) * (C.WIDTH - 5) + 2
    cy = (math.sin(t * 3.1) * 0.5 + 0.5) * (C.HEIGHT - 5) + 2
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            px[int(cx) + dx, int(cy) + dy] = (255, 0, 255)
    return im


async def run(args):
    notes = []
    t0 = time.monotonic()
    async with ShiningHelmet(address=args.address) as h:
        h.notify_handlers.append(
            lambda b: notes.append((round(time.monotonic() - t0, 3), b.hex())))
        await h.power(True)

        print(">>> A: screencast RED frame, graffiti CLOSED. Watch the panel.")
        ack = await h.screencast(solid((255, 0, 0)))
        print("    ack:", ack.hex() if ack else None)
        await asyncio.sleep(args.pause)

        print(">>> B: graffiti OPEN + screencast GREEN frame.")
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        ack = await h.screencast(solid((0, 255, 0)))
        print("    ack:", ack.hex() if ack else None)
        await asyncio.sleep(args.pause)

        print(f">>> C: streaming {args.frames} bouncing-ball frames "
              f"({'awaiting ack each' if not args.no_ack else 'no ack waits'})...")
        sent = acked = 0
        t_start = time.monotonic()
        for i in range(args.frames):
            ack = await h.screencast(ball_frame(i * 0.15), wait_ack=not args.no_ack)
            sent += 1
            acked += 1 if ack else 0
        dt = time.monotonic() - t_start
        print(f"    {sent} frames in {dt:.2f}s = {sent / dt:.1f} fps "
              f"({acked} acked)")
        await asyncio.sleep(args.pause)

        print(">>> closing graffiti (watch: does the panel revert?)")
        await h.graffiti(False)
        await asyncio.sleep(args.pause)

    print("\n=== notification log ===")
    for t, hexs in notes:
        print(f"  {t:7.3f}  {hexs}")
    print("\nRecord in VERIFY.md: A rendered? B rendered? C fps + smoothness? "
          "revert behavior on graffiti close / disconnect?")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--frames", type=int, default=60)
    p.add_argument("--no-ack", action="store_true",
                   help="don't wait for the 05 00 00 00 01 ack between frames")
    p.add_argument("--pause", type=float, default=4.0)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
