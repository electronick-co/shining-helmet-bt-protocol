"""Word-by-word TEXT flash on the helmet (propaganda / glitch style).

Each word is shown centered and auto-sized to fill the panel, held for --hold,
with a brief blackout blink between words. Long words shrink to fit.

Examples:
    python examples/live_words.py OBEY RISE AGAINST THE MACHINE
    python examples/live_words.py "NO FUTURE" --hold 0.5 --color 255,0,0
    python examples/live_words.py --loops 3                     # built-in phrase
"""
from __future__ import annotations
import argparse
import asyncio

from shining_helmet import ShiningHelmet, images

DEFAULT = ["OBEY", "RISE", "AGAINST", "THE", "MACHINE",
           "NO", "GODS", "NO", "MASTERS", "2026"]


def parse_rgb(s):
    return tuple(int(x) for x in s.split(",")) if s else (255, 255, 255)


async def run(args):
    color = parse_rgb(args.color)
    words = args.words or DEFAULT
    blank = images.text_frame("", bg=(0, 0, 0))
    frames = [(images.fit_text_frame(w, color=color), w) for w in words]
    print(f">>> {len(words)} words x{args.loops}: {' / '.join(words)}")

    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        if args.brightness is not None:
            await h.set_brightness(args.brightness)
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        try:
            for _ in range(max(1, args.loops)):
                for frame, w in frames:
                    await h.screencast(frame)
                    await asyncio.sleep(args.hold)
                    if args.gap > 0:
                        await h.screencast(blank)
                        await asyncio.sleep(args.gap)
        finally:
            await h.graffiti(False)
    print("done.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("words", nargs="*", help="words to flash (omit for built-in phrase)")
    p.add_argument("--address", default=None)
    p.add_argument("--hold", type=float, default=0.7, help="seconds per word")
    p.add_argument("--gap", type=float, default=0.1, help="blackout blink between words (s)")
    p.add_argument("--color", default="255,255,255", help="R,G,B")
    p.add_argument("--brightness", type=int, default=None)
    p.add_argument("--loops", type=int, default=1)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
