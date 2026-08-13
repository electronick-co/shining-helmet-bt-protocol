import asyncio
from bleak import BleakClient

ADDR = "92:33:6F:DE:FC:35"
FA02 = "0000fa02-0000-1000-8000-00805f9b34fb"

def f_screen(on): return bytes([5,0,7,1,1 if on else 0])

async def main():
    async with BleakClient(ADDR, timeout=20) as c:
        print("connected", c.is_connected)
        await c.write_gatt_char(FA02, f_screen(False), response=False)
        await asyncio.sleep(1.0)
        print("sent screen OFF")

asyncio.run(main())
