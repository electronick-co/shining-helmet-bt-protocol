"""Full capability showcase — runs every live-playback demo in sequence.

A single connection drives: scrolling text, a generative effects reel, an image
slideshow, and an animation clip. Good for a quick "what can this thing do" tour.

Usage: python examples/live_showcase.py [--address ...] [--fps 15]
"""
from __future__ import annotations
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from shining_helmet import ShiningHelmet, images               # noqa: E402
import live_effects                                            # noqa: E402
import live_video                                              # noqa: E402
import live_slideshow                                          # noqa: E402


async def run(args):
    fps = args.fps
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.set_brightness(160)
        await h.graffiti(True)
        await asyncio.sleep(0.3)

        print("\n=== 1. TEXT marquee ===")
        await h.stream(images.scroll_frames("BURNING MAN 2026  *  ",
                                            color=(255, 140, 0), font_size=11),
                       fps=fps, loops=1, open_graffiti=False)

        print("\n=== 2. EFFECTS reel ===")
        for e in ["plasma", "rainbow", "fire", "matrix", "sparkle"]:
            await live_effects.play(h, e, args.effect_seconds, fps, args.no_ack)

        print("\n=== 3. SLIDESHOW (color cards) ===")
        for im in live_slideshow.color_cards():
            await h.screencast(im)
            await asyncio.sleep(1.0)

        print("\n=== 4. ANIMATION clip ===")
        clip = live_video.build_demo()
        await h.stream(list(images.iter_video_frames(clip)),
                       fps=fps, loops=3, open_graffiti=False)

        print("\n=== finale: centered text ===")
        for _ in range(3):
            await h.screencast(images.text_frame("<3", color=(255, 0, 80)))
            await asyncio.sleep(1.0)

        await h.graffiti(False)
    print("\nshowcase complete.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--effect-seconds", type=float, default=6.0)
    p.add_argument("--no-ack", action="store_true")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
