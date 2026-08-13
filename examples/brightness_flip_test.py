"""Live sweep for verify:brightness-range and verify:flip-values.

Uploads the orientation "F" image (persists), then:
  1. brightness sweep — each value printed, held ~2.5 s
  2. flip 0..3 — each held 5 s (note the orientation for each value!)
  3. restores brightness 0xC0 / flip 0

Usage: python examples/brightness_flip_test.py [--skip-brightness] [--skip-flip]
"""
from __future__ import annotations
import argparse
import asyncio

from shining_helmet import ShiningHelmet

BRIGHTNESS_STEPS = [0, 1, 2, 4, 8, 16, 32, 64, 96, 128, 160, 192, 224, 255]


async def run(args):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from upload_test import build_test_pixels
    _, img_path = build_test_pixels()

    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        print(">>> uploading orientation image (orange F + R/G/B/W corners)...")
        await h.show_image(img_path)
        await asyncio.sleep(2)

        if not args.skip_brightness:
            print(">>> BRIGHTNESS SWEEP — call out when it visibly changes / maxes out")
            for v in BRIGHTNESS_STEPS:
                print(f"    brightness = {v}")
                await h.set_brightness(v)
                await asyncio.sleep(2.5)
            print("    restoring brightness 0xC0 (192)")
            await h.set_brightness(0xC0)
            await asyncio.sleep(1)

        if not args.skip_flip:
            print(">>> FLIP SWEEP — note the F orientation for each value")
            for d in range(4):
                print(f"    flip({d})")
                await h.flip(d)
                await asyncio.sleep(5)
            print("    restoring flip(0)")
            await h.flip(0)
            await asyncio.sleep(1)

    print("done — report what you saw; VERIFY.md gets updated from your notes.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--skip-brightness", action="store_true")
    p.add_argument("--skip-flip", action="store_true")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
