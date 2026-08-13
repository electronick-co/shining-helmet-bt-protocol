import asyncio
from bleak import BleakClient

ADDR = "92:33:6F:DE:FC:35"
FA02 = "0000fa02-0000-1000-8000-00805f9b34fb"
FA03 = "0000fa03-0000-1000-8000-00805f9b34fb"
W, H = 48, 12

def f_screen(on):   return bytes([5,0,7,1,1 if on else 0])
def f_light(b):     return bytes([5,0,4,0x80,b&0xff])
def f_graf(on):     return bytes([5,0,4,1,1 if on else 0])
def f_draw(r,g,b,x,y,seq): return bytes([11,0,5,1,0,r,g,b,x,y,seq&0xff])

def cb(_h,d): print("   NOTIFY", bytes(d).hex())

async def fill(c, rgb, seq):
    r,g,b = rgb
    for y in range(H):
        for x in range(W):
            await c.write_gatt_char(FA02, f_draw(r,g,b,x,y,seq), response=False)
            seq += 1
            if (seq & 0x1f)==0: await asyncio.sleep(0.01)
    return seq

async def main():
    async with BleakClient(ADDR, timeout=20) as c:
        print("connected", c.is_connected)
        try: await c.start_notify(FA03, cb)
        except Exception as e: print("notify fail", e)
        await c.write_gatt_char(FA02, f_screen(True), response=False); await asyncio.sleep(0.3)
        await c.write_gatt_char(FA02, f_light(0x80), response=False); await asyncio.sleep(0.3)
        await c.write_gatt_char(FA02, f_graf(True), response=False);  await asyncio.sleep(0.5)
        seq = 0
        for name,rgb in [("RED",(255,0,0)),("GREEN",(0,255,0)),("BLUE",(0,0,255)),("WHITE",(255,255,255))]:
            print("filling", name)
            seq = await fill(c, rgb, seq)
            await asyncio.sleep(1.5)
        await c.write_gatt_char(FA02, f_graf(False), response=False)
        await asyncio.sleep(1.0)
        print("done")

asyncio.run(main())
