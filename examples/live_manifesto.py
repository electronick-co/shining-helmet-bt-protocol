"""A choreographed word performance with DYNAMIC timing — slow dramatic words,
rapid-fire bursts, stutter-flashes, dramatic pauses, and a held finale. Mixes in
a short effect interlude. All centered, auto-sized, via the screencast path.

Usage:
    python examples/live_manifesto.py                  # built-in show
    python examples/live_manifesto.py --speed 1.5      # 1.5x faster overall
    python examples/live_manifesto.py --color 255,30,0
"""
from __future__ import annotations
import argparse
import asyncio
import random
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PIL import Image                                      # noqa: E402
from shining_helmet import ShiningHelmet, images, constants as C  # noqa: E402
import live_effects                                       # noqa: E402

# Steampunk / industrial palette for chaos bursts (brass, copper, rust, amber).
STEAMPUNK = [(212, 175, 55), (184, 115, 51), (183, 65, 14), (255, 140, 0),
             (205, 127, 50), (255, 200, 40), (150, 75, 0), (230, 160, 70)]


class Stage:
    """Helpers that render + time a word performance on an open graffiti canvas."""
    def __init__(self, h, color, speed):
        self.h = h
        self.color = color
        self.speed = speed              # >1 = faster (divides every duration)
        self._black = images.text_frame("", bg=(0, 0, 0))

    async def _sleep(self, s):
        await asyncio.sleep(max(0.0, s / self.speed))

    async def word(self, text, hold, *, gap=0.0):
        """Show one word, hold, optional trailing blackout."""
        await self.h.screencast(images.fit_text_frame(text, color=self.color))
        await self._sleep(hold)
        if gap:
            await self.h.screencast(self._black)
            await self._sleep(gap)

    async def burst(self, words, each=0.18, gap=0.04):
        """Rapid-fire a list of words."""
        for w in words:
            await self.word(w, each, gap=gap)

    async def stutter(self, text, times=3, on=0.07, off=0.06):
        """Strobe a single word on/off for emphasis, then hold it briefly."""
        frame = images.fit_text_frame(text, color=self.color)
        for _ in range(times):
            await self.h.screencast(frame)
            await self._sleep(on)
            await self.h.screencast(self._black)
            await self._sleep(off)
        await self.h.screencast(frame)
        await self._sleep(0.35)

    async def chaos_burst(self, words, *, n=None, each=0.055, jitter=0.03,
                          shift=2, recolor=True):
        """Ultra-fast, almost-subliminal flashes of `words` — chaotic timing,
        color, and position jitter for a steampunk/anarchic feel. `n` = how many
        flashes (random picks); default = shuffle the list once. No acks (speed).
        """
        if n is None:
            seq = list(words)
            random.shuffle(seq)
        else:
            seq = [random.choice(words) for _ in range(n)]
        for w in seq:
            col = random.choice(STEAMPUNK) if recolor else self.color
            fr = images.fit_text_frame(w, color=col)
            if shift:
                dx, dy = random.randint(-shift, shift), random.randint(-1, 1)
                shifted = Image.new("RGB", (C.WIDTH, C.HEIGHT), (0, 0, 0))
                shifted.paste(fr, (dx, dy))
                fr = shifted
            await self.h.screencast(fr, wait_ack=False)
            await self._sleep(max(0.02, each + random.uniform(-jitter, jitter)))

    async def pause(self, s):
        await self.h.screencast(self._black)
        await self._sleep(s)

    async def effect(self, name, seconds, fps=20):
        await live_effects.play(self.h, name, seconds / self.speed, fps, no_ack=True)


async def run(args):
    color = tuple(int(x) for x in args.color.split(","))
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.set_brightness(180)
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        s = Stage(h, color, args.speed)

        # --- Act 1: slow, dramatic build ---------------------------------
        await s.word("WAKE", 0.9, gap=0.15)
        await s.word("UP", 1.1, gap=0.5)

        # --- Act 2: rapid-fire indictment --------------------------------
        await s.burst(["WORK", "BUY", "OBEY", "CONSUME", "SLEEP"], each=0.22, gap=0.05)
        await s.pause(0.6)

        # --- Act 3: the turn, with emphasis ------------------------------
        await s.word("RISE", 0.8, gap=0.12)
        await s.stutter("AGAINST", times=3)
        await s.word("THE", 0.45, gap=0.1)
        await s.word("MACHINE", 1.3, gap=0.4)

        # --- Act 4: glitch interlude -------------------------------------
        await s.effect("matrix", 3.0)

        # --- Finale: slow, held ------------------------------------------
        await s.burst(["NO", "GODS"], each=0.5, gap=0.12)
        await s.burst(["NO", "MASTERS"], each=0.5, gap=0.12)
        await s.pause(0.4)
        await s.word("2026", 2.0)

        await h.graffiti(False)
    print("performance complete.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--color", default="255,40,0", help="R,G,B")
    p.add_argument("--speed", type=float, default=1.0, help=">1 faster, <1 slower")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
