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

def color_for(x):
    if x < 16:  return (255,0,0)      # left third  RED
    if x < 32:  return (0,255,0)      # middle third GREEN
    return (0,0,255)                  # right third BLUE

async def main():
    async with BleakClient(ADDR, timeout=20) as c:
        print("connected", c.is_connected)
        try: await c.start_notify(FA03, cb)
        except Exception as e: print("notify fail", e)
        await c.write_gatt_char(FA02, f_screen(True), response=False); await asyncio.sleep(0.3)
        await c.write_gatt_char(FA02, f_light(0xC0), response=False);  await asyncio.sleep(0.3)
        await c.write_gatt_char(FA02, f_graf(True), response=False);   await asyncio.sleep(0.5)
        seq = 0
        for y in range(H):
            for x in range(W):
                r,g,b = color_for(x)
                await c.write_gatt_char(FA02, f_draw(r,g,b,x,y,seq), response=False)
                seq += 1
                if (seq & 0x1f)==0: await asyncio.sleep(0.01)
        print(f"drew {seq} pixels (R|G|B bars)")
        await asyncio.sleep(0.5)
        await c.write_gatt_char(FA02, f_graf(False), response=False)
        await asyncio.sleep(2.0)
        print("done - bars should be displayed")

asyncio.run(main())
