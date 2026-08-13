"""Live IMAGE slideshow on the helmet (via screencast), with fade transitions.

Cycles through image files, each shown for --hold seconds with an optional
crossfade between them. Resizes everything to 48x12.

Examples:
    python examples/live_slideshow.py pics/*.png
    python examples/live_slideshow.py a.jpg b.jpg --hold 2 --fade 0.6
    python examples/live_slideshow.py                      # built-in color cards
"""
from __future__ import annotations
import argparse
import asyncio

import numpy as np
from PIL import Image

from shining_helmet import ShiningHelmet, constants as C

W, H = C.WIDTH, C.HEIGHT


def color_cards():
    cards = []
    for name, col in [("RED", (220, 0, 0)), ("GRN", (0, 200, 0)),
                      ("BLU", (0, 80, 255)), ("SUN", (255, 160, 0))]:
        im = Image.new("RGB", (W, H), col)
        cards.append(im)
    return cards


def load(path):
    return Image.open(path).convert("RGB").resize((W, H), Image.NEAREST)


def crossfade(a, b, steps):
    aa = np.asarray(a, float); bb = np.asarray(b, float)
    for k in range(1, steps + 1):
        t = k / steps
        yield Image.fromarray((aa * (1 - t) + bb * t).astype(np.uint8), "RGB")


async def run(args):
    if args.sources:
        imgs = [load(p) for p in args.sources]
        print(f">>> slideshow: {len(imgs)} images")
    else:
        imgs = color_cards()
        print(">>> slideshow: built-in color cards")

    fade_steps = int(args.fade * args.fps)
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        for loop in range(args.loops):
            for i, im in enumerate(imgs):
                await h.screencast(im)
                await asyncio.sleep(args.hold)
                if fade_steps > 0:
                    nxt = imgs[(i + 1) % len(imgs)]
                    await h.stream(crossfade(im, nxt, fade_steps), fps=args.fps,
                                   open_graffiti=False)
        await h.graffiti(False)
    print("done.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sources", nargs="*", help="image files (omit for built-in cards)")
    p.add_argument("--address", default=None)
    p.add_argument("--hold", type=float, default=2.0, help="seconds per image")
    p.add_argument("--fade", type=float, default=0.5, help="crossfade seconds (0=cut)")
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--loops", type=int, default=1)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
