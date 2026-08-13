"""Client behaviour tests against a fake BLE transport. No hardware needed.

FakeBleak reassembles the writes it receives into whole protocol messages and
replies with the same status notifications the real helmet sends, so the ack
gating in upload_bytes() is exercised for real rather than stubbed out.
"""
import asyncio

import pytest

from shining_helmet import constants as C
from shining_helmet import protocol as P
from shining_helmet.client import ShiningHelmet

PILImage = pytest.importorskip("PIL.Image")
from shining_helmet import images  # noqa: E402


class FakeBleak:
    """Minimal stand-in for bleak.BleakClient."""

    def __init__(self, helmet, mtu=512):
        self.helmet = helmet
        self.mtu_size = mtu
        self.is_connected = True
        self.writes = []          # every raw write, in order
        self._buf = b""
        self._payload_seen = 0

    async def write_gatt_char(self, char, data, response=False):
        assert char == C.CHAR_WRITE
        assert response is True, "all writes must be acknowledged"
        assert len(data) <= self.mtu_size - 3, "chunk exceeds MTU-3"
        self.writes.append(bytes(data))
        self._buf += bytes(data)
        self._maybe_ack()

    def _maybe_ack(self):
        """Once a full message has arrived, notify like the device does."""
        while len(self._buf) >= 2:
            total = int.from_bytes(self._buf[0:2], "little")
            if total < 2 or len(self._buf) < total:
                return
            msg, self._buf = self._buf[:total], self._buf[total:]
            self._ack_for(msg)

    def _ack_for(self, msg):
        kind = msg[2]
        if kind == 0x00 and len(msg) >= 9:                 # screencast
            self._notify(bytes([5, 0, 0, 0, C.UPLOAD_STATUS_READY]))
            return
        if kind in (P.TYPE_GIF, P.TYPE_PICTURE) and len(msg) >= 16:   # upload block
            file_len = int.from_bytes(msg[5:9], "little")
            self._payload_seen += len(msg) - P.UPLOAD_HEADER_LEN
            done = self._payload_seen >= file_len
            status = C.UPLOAD_STATUS_SAVED if done else C.UPLOAD_STATUS_READY
            if done:
                self._payload_seen = 0
            self._notify(bytes([5, 0, kind, 0, status]))

    def _notify(self, data):
        # Deliver on the next loop iteration: the client registers its waiter
        # after issuing the writes, exactly as with a real radio.
        asyncio.get_running_loop().call_soon(self.helmet._on_notify, 0, bytearray(data))

    async def connect(self): ...
    async def disconnect(self): self.is_connected = False
    async def start_notify(self, *a): ...
    async def stop_notify(self, *a): ...


def make_helmet(**kw):
    h = ShiningHelmet(address="AA:BB:CC:DD:EE:FF", **kw)
    h._client = FakeBleak(h)
    return h


# ---------------------------------------------------------------- control cmds
def test_control_commands_send_expected_frames():
    async def run():
        h = make_helmet()
        await h.power(True)
        await h.set_brightness(0x60)
        await h.flip(1)
        await h.graffiti(True)
        await h.reset()
        return h._client.writes
    writes = asyncio.run(run())
    assert writes[0].hex() == "0500070101"
    assert writes[1].hex() == "0500048060"
    assert writes[2].hex() == "0500068001"
    assert writes[3].hex() == "0500040101"
    assert writes[4].hex() == "04000380"


def test_write_before_connect_raises():
    async def run():
        h = ShiningHelmet(address="AA:BB:CC:DD:EE:FF")   # no _client attached
        with pytest.raises(RuntimeError):
            await h.power(True)
    asyncio.run(run())


def test_draw_pixel_advances_and_wraps_seq():
    async def run():
        h = make_helmet()
        for _ in range(3):
            await h.draw_pixel(0, 0, (1, 2, 3))
        assert [w[-1] for w in h._client.writes] == [0, 1, 2]
        h._seq = 0xFF
        await h.draw_pixel(0, 0, (1, 2, 3))
        assert h._seq == 0          # rolls over, stays a single byte
    asyncio.run(run())


# ---------------------------------------------------------------- upload path
def test_single_block_upload_completes():
    async def run():
        h = make_helmet()
        data = images.encode_gif(PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (9, 9, 9)))
        await h.upload_bytes(data)
        sent = b"".join(h._client.writes)
        assert sent[P.UPLOAD_HEADER_LEN:] == data      # payload arrived intact
    asyncio.run(run())


def test_multi_block_upload_is_ack_gated_and_reassembles():
    async def run():
        h = make_helmet()
        data = bytes(range(256)) * 40                  # 10240 B -> 3 blocks
        await h.upload_bytes(data)
        blocks = P.upload_blocks(data)
        assert len(blocks) == 3
        # Every chunk fits MTU-3 (asserted in the fake) and the payload survives.
        sent = b"".join(h._client.writes)
        recovered = b""
        off = 0
        while off < len(sent):
            total = int.from_bytes(sent[off:off + 2], "little")
            recovered += sent[off + P.UPLOAD_HEADER_LEN:off + total]
            off += total
        assert recovered == data
    asyncio.run(run())


def test_oversize_upload_is_rejected_before_any_write():
    async def run():
        h = make_helmet()
        with pytest.raises(ValueError, match="at most"):
            await h.upload_bytes(b"\x00" * (C.MAX_UPLOAD_BYTES + 1))
        assert h._client.writes == []      # nothing hit the radio
    asyncio.run(run())


def test_upload_at_exactly_the_cap_is_allowed():
    async def run():
        h = make_helmet()
        await h.upload_bytes(b"\x00" * C.MAX_UPLOAD_BYTES)
        assert h._client.writes
    asyncio.run(run())


# ---------------------------------------------------------------- streaming
def test_screencast_chunks_at_mtu_minus_3():
    async def run():
        h = make_helmet()
        ack = await h.screencast(PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (5, 5, 5)))
        assert ack == bytes([5, 0, 0, 0, 1])
        assert all(len(w) <= 512 - 3 for w in h._client.writes)
    asyncio.run(run())


def test_stream_sends_one_frame_each_and_counts_them():
    async def run():
        h = make_helmet()
        frames = [PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (i, 0, 0)) for i in range(5)]
        n = await h.stream(frames, fps=0, open_graffiti=False)
        assert n == 5
    asyncio.run(run())


def test_stream_replays_when_loops_greater_than_one():
    async def run():
        h = make_helmet()
        frames = [PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (i, 0, 0)) for i in range(3)]
        n = await h.stream(iter(frames), fps=0, loops=3, open_graffiti=False)
        assert n == 9      # a one-shot iterator must still replay
    asyncio.run(run())


def test_stream_consumes_an_endless_generator_lazily():
    """REGRESSION: stream() used to do list(frames) unconditionally, so an
    endless generator hung before a single frame was ever sent."""
    class Stop(Exception):
        pass

    def endless():
        i = 0
        while True:
            yield PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (i % 256, 0, 0))
            i += 1

    async def run():
        h = make_helmet()
        seen = []

        def on_frame(sent, i):
            seen.append(sent)
            if sent == 3:
                raise Stop
        with pytest.raises(Stop):
            await h.stream(endless(), fps=0, open_graffiti=False, on_frame=on_frame)
        assert seen == [1, 2, 3]

    asyncio.run(asyncio.wait_for(run(), timeout=10))


def test_stream_closes_graffiti_even_if_a_frame_fails():
    async def run():
        h = make_helmet()

        def boom(sent, i):
            raise RuntimeError("frame handler blew up")
        with pytest.raises(RuntimeError):
            await h.stream([PILImage.new("RGB", (C.WIDTH, C.HEIGHT))],
                           fps=0, open_graffiti=True, close_graffiti=True,
                           on_frame=boom)
        assert h._client.writes[0].hex() == "0500040101"    # graffiti open
        assert h._client.writes[-1].hex() == "0500040100"   # ...and closed again
    asyncio.run(run())
