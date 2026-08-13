"""Live TEXT on the helmet: scrolling marquee + static messages.

Uses the screencast path (graffiti mode + per-frame PNG push).

Examples:
    python examples/live_text.py "BURNING MAN 2026"            # scroll it
    python examples/live_text.py "HI" --static --hold 3        # centered, held
    python examples/live_text.py "RGB" --color 255,80,0 --fps 20
    python examples/live_text.py "fast" --no-ack --fps 30      # push uncapped
"""
from __future__ import annotations
import argparse
import asyncio

from shining_helmet import ShiningHelmet, images


def parse_rgb(s):
    return tuple(int(x) for x in s.split(",")) if s else (255, 255, 255)


async def run(args):
    color = parse_rgb(args.color)
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        if args.static:
            frame = images.text_frame(args.text, color=color, font_size=args.font)
            print(f">>> static text {args.text!r}, held {args.hold}s")
            await h.graffiti(True)
            await asyncio.sleep(0.3)
            for _ in range(max(1, int(args.hold))):
                await h.screencast(frame)
                await asyncio.sleep(1.0)
        else:
            frames = list(images.scroll_frames(
                args.text, color=color, font_size=args.font, step=args.step))
            print(f">>> scrolling {args.text!r}: {len(frames)} frames x{args.loops} "
                  f"@ {args.fps} fps")
            n = await h.stream(frames, fps=args.fps, loops=args.loops,
                               wait_ack=not args.no_ack, close_graffiti=True)
            print(f"    sent {n} frames")
    print("done.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--address", default=None)
    p.add_argument("--static", action="store_true", help="center the text instead of scrolling")
    p.add_argument("--color", default="255,255,255", help="R,G,B")
    p.add_argument("--font", type=int, default=11, help="font px height (panel is 12 tall)")
    p.add_argument("--step", type=int, default=1, help="scroll px per frame")
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--loops", type=int, default=2)
    p.add_argument("--hold", type=float, default=4.0, help="seconds (static mode)")
    p.add_argument("--no-ack", action="store_true", help="don't wait per-frame ack (faster, may drop)")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
