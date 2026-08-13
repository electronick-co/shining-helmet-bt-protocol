"""Brightness sweep with the current value rendered ON the panel.

Opens graffiti mode and, for each step, screencasts a frame showing the
brightness number (white digits) + a full RGB gradient strip, then applies the
brightness. The digits dim with the panel (global dimming) but stay readable,
so the observer always knows which value they're looking at.

Usage: python examples/brightness_labeled_test.py [--hold 3]
"""
from __future__ import annotations
import argparse
import asyncio

from shining_helmet import ShiningHelmet, constants as C

STEPS = [255, 224, 192, 160, 128, 96, 64, 32, 16, 8, 4, 2, 1, 0, 64]  # end visible

FONT = {  # 3x5 digit bitmaps
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
}


def label_frame(value: int):
    from PIL import Image
    im = Image.new("RGB", (C.WIDTH, C.HEIGHT), (0, 0, 0))
    px = im.load()
    # digits, 2x scale (6x10), starting at x=1,y=1
    x0 = 1
    for ch in str(value):
        for ry, row in enumerate(FONT[ch]):
            for rx, bit in enumerate(row):
                if bit == "1":
                    for sy in (0, 1):
                        for sx in (0, 1):
                            px[x0 + rx * 2 + sx, 1 + ry * 2 + sy] = (255, 255, 255)
        x0 += 8
    # R/G/B/full-white reference blocks on the right
    for y in range(C.HEIGHT):
        for x in range(28, 33):
            px[x, y] = (255, 0, 0)
        for x in range(33, 38):
            px[x, y] = (0, 255, 0)
        for x in range(38, 43):
            px[x, y] = (0, 0, 255)
        for x in range(43, 48):
            px[x, y] = (255, 255, 255)
    return im


async def run(args):
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        print(">>> sweep — the number on the panel IS the current brightness")
        for v in STEPS:
            await h.screencast(label_frame(v))
            await h.set_brightness(v)
            print(f"    showing {v}")
            await asyncio.sleep(args.hold)
        await h.set_brightness(0xC0)
        await h.graffiti(False)
    print("done — at which numbers did it visibly change / max out / turn off?")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--hold", type=float, default=3.0)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
