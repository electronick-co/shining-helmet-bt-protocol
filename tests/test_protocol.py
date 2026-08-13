"""Protocol-builder tests, checked against bytes from the real capture.
Run: pytest -q   (no hardware needed)."""
import datetime
from shining_helmet import protocol as P


def test_screen():
    assert P.screen(True).hex() == "0500070101"
    assert P.screen(False).hex() == "0500070100"


def test_brightness_and_flip():
    assert P.brightness(0x60).hex() == "0500048060"
    assert P.flip(0).hex() == "0500068000"


def test_graffiti():
    assert P.graffiti(True).hex() == "0500040101"
    assert P.graffiti(False).hex() == "0500040100"


def test_sync_time_matches_capture():
    # capture frame: 0b0001801a060902110109  (2026-06-09 17:01:09, weekday=2/Tue)
    dt = datetime.datetime(2026, 6, 9, 17, 1, 9)
    assert P.sync_time(dt).hex() == "0b0001801a060902110109"


def test_draw_pixel_matches_capture():
    # capture frame: 0b00050100ffffff000000  (white pixel at 0,0 seq 0)
    assert P.draw_pixel(0, 0, (255, 255, 255), 0).hex() == "0b00050100ffffff000000"
    # capture frame: 0b00050100ffffff2e002c  (white at x=0x2e,y=0 seq 0x2c)
    assert P.draw_pixel(0x2E, 0, (255, 255, 255), 0x2C).hex() == "0b00050100ffffff2e002c"


def test_draw_pixel_bounds():
    import pytest
    with pytest.raises(ValueError):
        P.draw_pixel(48, 0, (1, 2, 3), 0)


def test_upload_header_matches_capture():
    # VERIFIED single-packet GIF upload header from the capture (frame 4364):
    #   payload 321 bytes, total 337, crc32 0x59da0e6f
    hdr = P.upload_header(321, 0x59DA0E6F, total_packet_len=337)
    assert hdr.hex() == "5101010000410100006f0eda59000000"


def test_upload_blocks_single_block():
    data = b"GIF87a" + b"\x00" * 100               # small -> one block
    blocks = P.upload_blocks(data)
    assert len(blocks) == 1
    pkt = blocks[0]
    assert pkt[16:] == data                        # 16-byte header + payload
    assert int.from_bytes(pkt[0:2], "little") == 16 + len(data)   # total len
    assert pkt[2:5] == bytes([0x01, 0x00, 0x00])   # type=GIF + first-block flag
    assert int.from_bytes(pkt[5:9], "little") == len(data)        # payload len
    assert int.from_bytes(pkt[9:13], "little") == P.crc32(data)   # crc32


def test_upload_blocks_multi_block_matches_capture_header():
    # Capture frame 4384: first block of a 20047-byte GIF starts
    #   10 10 01 00 00 4f 4e 00 00 53 43 3a 4b 00 00 00
    # i.e. total=0x1010=4112=16+4096, len=20047, crc=0x4b3a4353, flag=0.
    data = bytearray(b"GIF87a" + bytes(20047 - 6))
    blocks = P.upload_blocks(bytes(data))
    assert len(blocks) == 5                        # 4*4096 + 3663
    first, last = blocks[0], blocks[-1]
    assert int.from_bytes(first[0:2], "little") == 4112
    assert first[2:5] == bytes([0x01, 0x00, 0x00])           # type=GIF, flag=first
    assert int.from_bytes(first[5:9], "little") == 20047     # whole-file len
    assert len(first) == 4112
    for b in blocks[1:]:
        assert b[2:5] == bytes([0x01, 0x00, 0x02])           # continuation flag
        assert b[5:13] == first[5:13]                        # same file len + crc
    assert int.from_bytes(last[0:2], "little") == 16 + 3663
    # reassembled payload is the original file
    assert b"".join(b[16:] for b in blocks) == bytes(data)


def test_encode_png_is_always_rgb():
    # The helmet renders RGB PNGs but shows palette/indexed PNGs blank, so
    # encode_png must emit true-color RGB even when reducing colors.
    pytest = __import__("pytest")
    PILImage = pytest.importorskip("PIL.Image")
    from shining_helmet import images
    import io
    src = PILImage.new("RGB", (48, 12))
    for x in range(48):
        for y in range(12):
            src.putpixel((x, y), (x * 5 % 256, y * 20 % 256, (x + y) * 3 % 256))
    for colors in (0, 8, 32):
        png = images.encode_png(src, colors=colors)
        assert PILImage.open(io.BytesIO(png)).mode == "RGB"


def test_screencast_message_matches_capture():
    # Capture frame 4767: 145-byte type-00 message = 9-byte header + 136-byte PNG
    #   91 00 00 00 00 88 00 00 00 89 50 4e 47 ...
    payload = b"\x89PNG" + bytes(132)              # 136 bytes
    msg = P.screencast_message(payload)
    assert len(msg) == 145
    assert msg[:9].hex() == "910000000088000000"
    assert msg[9:] == payload


def test_upload_blocks_picture_type():
    # Capture frame 4554: PNG asset upload uses type byte 02 and got ack 05 00 02 00 03
    blocks = P.upload_blocks(b"\x89PNG" + bytes(50), content_type=P.TYPE_PICTURE)
    assert blocks[0][2] == 0x02
