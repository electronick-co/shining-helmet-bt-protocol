"""Draw three vertical bars R | G | B (verified per-pixel path). Run: python examples/rgb_bars.py"""
import asyncio
from shining_helmet import ShiningHelmet, constants as C


def color_for(x):
    return (255, 0, 0) if x < 16 else (0, 255, 0) if x < 32 else (0, 0, 255)


async def main():
    async with ShiningHelmet() as h:
        await h.power(True)
        await h.set_brightness(0xC0)
        await h.graffiti(True)
        h.reset_seq()
        for y in range(C.HEIGHT):
            for x in range(C.WIDTH):
                await h.draw_pixel(x, y, color_for(x))
        await asyncio.sleep(0.3)
        await h.graffiti(False)
        print("done — should show R|G|B bars")


if __name__ == "__main__":
    asyncio.run(main())
