"""Set a single flip value and exit (for stepwise orientation testing).

Usage: python examples/flip_set.py <0-3> [--address ...]
The stored image should be the orientation "F" (run brightness_flip_test or
`shining-helmet image decoded/test_orientation.png` first).
"""
from __future__ import annotations
import argparse
import asyncio

from shining_helmet import ShiningHelmet


async def run(args):
    async with ShiningHelmet(address=args.address) as h:
        await h.power(True)
        await h.flip(args.direction)
        await asyncio.sleep(1)
    print(f"flip({args.direction}) sent — observe the panel.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("direction", type=int, choices=range(4))
    p.add_argument("--address", default=None)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
