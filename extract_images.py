#!/usr/bin/env python3
"""Reassemble data-channel (0x0006) uploads and carve out embedded images."""
import json, os, struct

SRC = "test1_bluetoothdebug_helmet.json"
OUT = "decoded"
os.makedirs(OUT, exist_ok=True)

def hx(v): return bytes(int(x,16) for x in v.split(":")) if v else b""

def load_tx_0006():
    d = json.load(open(SRC)); rows=[]
    for p in d:
        L=p["_source"]["layers"]; att=L.get("btatt")
        if not att: continue
        if att.get("btatt.opcode") in ("0x52","0x12") and att.get("btatt.handle")=="0x0006":
            rows.append((float(L["frame"]["frame.time_relative"]),
                         int(L["frame"]["frame.number"]),
                         hx(att.get("btatt.value",""))))
    return rows

def is_ctl(b):  # small control frame [len][00][cmd], len==len(b)
    return 3<=len(b)<=16 and b[0]==len(b) and b[1]==0

def reassemble(rows):
    """Group fragments into uploads; control frames are passed through."""
    blocks=[]; cur=None
    for t,n,b in rows:
        if is_ctl(b):
            if cur: blocks.append(cur); cur=None
            blocks.append(("ctl",t,n,b))
        else:
            if cur is None: cur=["up",t,n,bytearray(b)]
            else: cur[3].extend(b)
    if cur: blocks.append(cur)
    return blocks

PNG_SIG=b"\x89PNG\r\n\x1a\n"; GIF_SIG=b"GIF8"

def png_dims(b):
    i=b.find(PNG_SIG)
    if i<0: return None
    # IHDR width/height big-endian at i+16
    w,h=struct.unpack(">II", b[i+16:i+24]); return ("png",i,w,h)

def gif_dims(b):
    i=b.find(GIF_SIG)
    if i<0: return None
    w=b[i+6]|b[i+7]<<8; h=b[i+8]|b[i+9]<<8; return ("gif",i,w,h)

rows=load_tx_0006()
blocks=reassemble(rows)
k=0
print(f"{'time':>9}  {'frame':>5}  kind  details")
for blk in blocks:
    if blk[0]=="ctl": continue
    _,t,n,buf=blk; b=bytes(buf)
    # carve every image signature occurrence inside this block
    found=[]
    pos=0
    while True:
        ip=b.find(PNG_SIG,pos); ig=b.find(GIF_SIG,pos)
        cands=[x for x in (ip,ig) if x>=0]
        if not cands: break
        s=min(cands)
        if s==ig and (ip<0 or ig<ip):
            kind="gif"; w=b[s+6]|b[s+7]<<8; h=b[s+8]|b[s+9]<<8
        else:
            kind="png"; w,h=struct.unpack(">II",b[s+16:s+24])
        found.append((kind,s,w,h)); pos=s+8
    if not found:
        print(f"{t:9.3f}  {n:5d}  RAW   {len(b)}B  head={b[:20].hex()}")
        continue
    # header preceding first image = upload framing
    hdr=b[:found[0][1]]
    for ki,(kind,s,w,h) in enumerate(found):
        end=found[ki+1][1] if ki+1<len(found) else len(b)
        img=b[s:end]; k+=1
        fn=os.path.join(OUT,f"img_{k:02d}_f{n}_{w}x{h}.{kind}")
        open(fn,"wb").write(img)
    print(f"{t:9.3f}  {n:5d}  {found[0][0].upper()}  block={len(b)}B  "
          f"imgs={len(found)} dims={found[0][2]}x{found[0][3]}  "
          f"hdr({len(hdr)}B)={hdr.hex()}")
print(f"\nCarved {k} images into {OUT}/")
