"""Steampunk / anarchic word performance — readable dramatic lines punctuated by
ultra-fast, almost-subliminal CHAOS BURSTS of dark machine words (jittered color,
timing, and position). Furnace fire + ember interludes.

Usage:
    python examples/live_chaos.py
    python examples/live_chaos.py --speed 1.3
    python examples/live_chaos.py --intensity 24      # more flashes per burst
"""
from __future__ import annotations
import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from shining_helmet import ShiningHelmet            # noqa: E402
from live_manifesto import Stage                    # noqa: E402

# Dark / industrial / anarchic word pool for the subliminal bursts.
DARK = [
    "GEARS", "STEAM", "IRON", "RUST", "COAL", "BRASS", "SMOKE", "ASH", "OIL",
    "GRIND", "PISTON", "FURNACE", "SOOT", "CHAINS", "DEBT", "FLESH", "BONE",
    "DECAY", "ENTROPY", "VOID", "DUST", "OBLIVION", "GREED", "ROT", "TEETH",
    "ENGINE", "BLOOD", "RUIN", "EMBER", "CINDER", "HOLLOW", "HUNGER", "COG",
    "WIRE", "VALVE", "PRESSURE", "SCREAM", "GHOST", "CORRODE", "BURN",
]


async def run(args):
    color = tuple(int(x) for x in args.color.split(","))
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.set_brightness(190)
        await h.graffiti(True)
        await asyncio.sleep(0.3)
        s = Stage(h, color, args.speed)
        ki = args.intensity

        # I. the world is a machine ---------------------------------------
        await s.word("THE", 0.5, gap=0.08)
        await s.word("AGE", 0.5, gap=0.08)
        await s.word("OF", 0.4, gap=0.08)
        await s.word("RUST", 1.1, gap=0.3)
        await s.chaos_burst(DARK, n=ki)                  # subliminal flood

        # II. the furnace -------------------------------------------------
        await s.effect("fire", 2.5)
        await s.word("FEED", 0.45, gap=0.06)
        await s.word("THE", 0.35, gap=0.06)
        await s.stutter("FURNACE", times=4, on=0.06, off=0.05)
        await s.chaos_burst(DARK, n=ki + 6, each=0.045)   # faster, more chaotic

        # III. the turn ---------------------------------------------------
        await s.pause(0.5)
        await s.word("WE", 0.5, gap=0.08)
        await s.word("ARE", 0.5, gap=0.08)
        await s.word("THE", 0.4, gap=0.06)
        await s.stutter("SMOKE", times=3)
        await s.effect("sparkle", 2.0)                    # embers

        # IV. revolt ------------------------------------------------------
        await s.chaos_burst(DARK, n=ki + 10, each=0.04, jitter=0.04)  # peak chaos
        await s.word("BURN", 0.5, gap=0.05)
        await s.word("IT", 0.4, gap=0.05)
        await s.stutter("DOWN", times=5, on=0.07, off=0.05)
        await s.pause(0.4)

        # V. finale -------------------------------------------------------
        await s.word("NO", 0.6, gap=0.1)
        await s.word("MASTERS", 1.4)

        await h.graffiti(False)
    print("performance complete.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--address", default=None)
    p.add_argument("--color", default="255,120,0", help="R,G,B for readable words")
    p.add_argument("--speed", type=float, default=1.0, help=">1 faster, <1 slower")
    p.add_argument("--intensity", type=int, default=16,
                   help="flashes per chaos burst (more = denser subliminal flood)")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
