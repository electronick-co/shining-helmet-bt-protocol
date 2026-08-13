"""Async BLE client for the Shining Display helmet. Cross-platform via bleak.

Works on PC (Windows/macOS) and Raspberry Pi / Linux (BlueZ). On the Pi, ensure
BlueZ + bluetooth service are running and the user can access BLE (often the
`bluetooth` group or running once with sudo to verify).

Typical use:

    import asyncio
    from shining_helmet import ShiningHelmet

    async def main():
        async with ShiningHelmet() as h:   # auto-discovers by name prefix
            await h.power(True)
            await h.set_brightness(0xC0)
            await h.draw_image("logo.png")
    asyncio.run(main())
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from bleak import BleakClient, BleakScanner

from . import constants as C
from . import protocol

log = logging.getLogger("shining_helmet")


class ShiningHelmet:
    def __init__(self, address: Optional[str] = None, *, name_prefix: str = C.DEVICE_NAME_PREFIX,
                 timeout: float = 20.0, inter_pixel_delay: float = 0.0):
        """address: BLE MAC/UUID. If None, scan for a device whose name starts
        with `name_prefix`.  inter_pixel_delay throttles per-pixel draws (s)."""
        self.address = address
        self.name_prefix = name_prefix
        self.timeout = timeout
        self.inter_pixel_delay = inter_pixel_delay
        self._client: Optional[BleakClient] = None
        self._seq = 0
        self._notify_waiters: list[tuple] = []  # (future, predicate|None)
        # extra notification subscribers: callables (data: bytes) -> None
        self.notify_handlers: list = []

    # ---------------------------------------------------------------- discovery
    @staticmethod
    async def discover(name_prefix: str = C.DEVICE_NAME_PREFIX, timeout: float = 12.0):
        """Return a list of (address, name) for matching advertised devices."""
        found = []
        devices = await BleakScanner.discover(timeout=timeout)
        for d in devices:
            if (d.name or "").startswith(name_prefix):
                found.append((d.address, d.name))
        return found

    # ---------------------------------------------------------------- lifecycle
    async def connect(self):
        if self.address is None:
            matches = await self.discover(self.name_prefix, self.timeout)
            if not matches:
                raise RuntimeError(f"no helmet advertising name prefix {self.name_prefix!r}")
            self.address = matches[0][0]
            log.info("auto-selected %s", matches[0])
        self._client = BleakClient(self.address, timeout=self.timeout)
        await self._client.connect()
        await self._client.start_notify(C.CHAR_NOTIFY, self._on_notify)
        log.info("connected to %s", self.address)
        # NOTE: the display channel needs NO auth (VERIFIED). The JieLi RCSP auth
        # on SERVICE_AUTH is only required for OTA firmware updates -> see auth.py.
        return self

    async def disconnect(self):
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(C.CHAR_NOTIFY)
            except Exception:
                pass
            await self._client.disconnect()
        self._client = None

    async def __aenter__(self):
        return await self.connect()

    async def __aexit__(self, *exc):
        await self.disconnect()

    # ---------------------------------------------------------------- notifications
    def _on_notify(self, _handle, data: bytearray):
        b = bytes(data)
        log.debug("notify %s", b.hex())
        for cb in self.notify_handlers[:]:
            try:
                cb(b)
            except Exception:
                log.exception("notify handler error")
        for entry in self._notify_waiters[:]:
            fut, pred = entry
            if fut.done() or (pred is not None and not pred(b)):
                continue
            fut.set_result(b)
            self._notify_waiters.remove(entry)

    async def _wait_notify(self, timeout: float = 2.0, pred=None) -> Optional[bytes]:
        """Wait for the next notification (optionally one matching `pred`)."""
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        entry = (fut, pred)
        self._notify_waiters.append(entry)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            if entry in self._notify_waiters:
                self._notify_waiters.remove(entry)
            return None

    # ---------------------------------------------------------------- raw write
    async def _write(self, payload: bytes, response: bool = False):
        if not self._client or not self._client.is_connected:
            raise RuntimeError("not connected")
        await self._client.write_gatt_char(C.CHAR_WRITE, payload, response=response)

    # ---------------------------------------------------------------- commands
    # All one-shot commands use acknowledged writes: write-without-response is
    # VERIFIED to occasionally drop frames silently (seen live with flip()).
    async def power(self, on: bool):
        await self._write(protocol.screen(on), response=True)

    async def set_brightness(self, level: int):
        await self._write(protocol.brightness(level), response=True)

    async def flip(self, direction: int = 0):
        await self._write(protocol.flip(direction), response=True)

    async def sync_time(self, when=None):
        await self._write(protocol.sync_time(when), response=True)

    async def graffiti(self, open_: bool):
        await self._write(protocol.graffiti(open_), response=True)

    async def reset(self):
        """Restore the factory animations, clearing any uploaded image.
        VERIFIED live: acks `05 00 03 80 01`, connection stays up, no reboot."""
        await self._write(protocol.reset(), response=True)

    def reset_seq(self):
        self._seq = 0

    async def draw_pixel(self, x: int, y: int, rgb):
        # VERIFIED: pixel writes MUST be acknowledged (response=True). Fire-and-forget
        # write-without-response overruns the device and most pixels are dropped
        # (symptom: scattered dots instead of a fill).
        await self._write(protocol.draw_pixel(x, y, rgb, self._seq), response=True)
        self._seq = (self._seq + 1) & 0xFF
        if self.inter_pixel_delay:
            await asyncio.sleep(self.inter_pixel_delay)

    # ---------------------------------------------------------------- high level
    async def draw_image(self, path: str, *, open_close: bool = True, throttle_every: int = 32,
                         throttle_delay: float = 0.01):
        """Render a 48x12 image via the per-pixel graffiti path (VERIFIED path).

        For full-screen/animated content this is slow-ish (576 writes). Prefer
        upload_image() once the bulk path is verified.
        """
        from . import images
        pixels = images.load_frame(path)
        writes, self._seq = images.frame_to_draw_writes(pixels, self._seq)
        if open_close:
            await self.graffiti(True)
            await asyncio.sleep(0.3)
        for w in writes:
            await self._write(w, response=True)   # acknowledged: prevents pixel dropout
        if open_close:
            await asyncio.sleep(0.3)
            await self.graffiti(False)

    async def show_image(self, source, *, idx: int = 0, ftype: int = 0):
        """Display an image persistently (VERIFIED path for a single 48x12 frame).

        `source` is a file path or PIL.Image (any size/format). It's resized to
        48x12 and encoded as GIF (the device renders GIF; PNG uploads show blank),
        then uploaded. Fast (one packet) and persists after disconnect.
        """
        from . import images
        gif = images.encode_gif(source)
        await self.upload_bytes(gif, idx=idx, ftype=ftype)

    async def upload_bytes(self, data: bytes, *, content_type: int = protocol.TYPE_GIF,
                           idx: int = 0, ftype: int = 0, chunk_size: int = 480,
                           ack_timeout: float = 5.0, retries: int = 3):
        """Upload a file via the block-transfer path.

        Framing decoded from the app (see protocol.upload_blocks): the file goes
        out in blocks of 16-byte header + <=4096 payload; each block is written
        in `chunk_size` slices; after each block the device notifies
        `05 00 <type> 00 <status>` — READY(1) = send next block, SAVED(3) =
        whole file stored, SPACE_FULL(2)/ERROR(0) = abort/resend.

        VERIFIED live for single- and multi-block (animated GIF) uploads.
        """
        if len(data) > C.MAX_UPLOAD_BYTES:
            # The device rejects oversize files at block 1 with status 0 after
            # burning three retries — fail fast with a useful message instead.
            raise ValueError(
                f"file is {len(data)} bytes; the device stores at most "
                f"{C.MAX_UPLOAD_BYTES} (10 x 4096-byte blocks)")
        blocks = protocol.upload_blocks(data, content_type=content_type,
                                        idx=idx, ftype=ftype)
        log.info("upload: %d byte file -> %d block(s)", len(data), len(blocks))

        def is_status(b: bytes) -> bool:
            return (len(b) == 5 and b[0] == 0x05 and b[1] == 0x00
                    and b[2] == content_type and b[3] == 0x00)

        for i, block in enumerate(blocks):
            last = i == len(blocks) - 1
            for attempt in range(1, retries + 1):
                for off in range(0, len(block), chunk_size):
                    await self._write(block[off:off + chunk_size], response=True)
                note = await self._wait_notify(ack_timeout, pred=is_status)
                if note is None:
                    if len(blocks) == 1:
                        # the originally-verified single-packet path didn't wait;
                        # a missed/disabled notification shouldn't fail it
                        log.warning("no upload status notification (continuing)")
                        return
                    log.warning("block %d/%d: no status notification (attempt %d)",
                                i + 1, len(blocks), attempt)
                    continue
                status = note[4]
                if status == C.UPLOAD_STATUS_READY or (last and status == C.UPLOAD_STATUS_SAVED):
                    log.debug("block %d/%d ack: %s", i + 1, len(blocks), note.hex())
                    break
                if status == C.UPLOAD_STATUS_SPACE_FULL:
                    raise RuntimeError("device storage full (upload status 2)")
                log.warning("block %d/%d: status %d, resending (attempt %d)",
                            i + 1, len(blocks), status, attempt)
            else:
                raise RuntimeError(f"upload failed at block {i + 1}/{len(blocks)}")

    def _chunk_size(self, override: Optional[int] = None) -> int:
        """Max ATT payload per write: negotiated MTU − 3 (ATT header), capped."""
        if override:
            return override
        mtu = getattr(self._client, "mtu_size", 0) or 23
        return max(20, mtu - 3)

    async def screencast(self, source, *, wait_ack: bool = True,
                         ack_timeout: float = 4.0, chunk_size: Optional[int] = None,
                         colors: Optional[int] = None):
        """Push one full frame via the type-00 'screencast' path (9-byte header
        + 48x12 PNG). VERIFIED live: renders instantly; persists while graffiti
        mode is open (ephemeral ~0.5 s otherwise). Returns the ack notification
        (or None on timeout / wait_ack=False).

        Frame rate is bounded by PNG size / MTU (one BLE write per ~MTU bytes),
        NOT the device ack. `colors`:
          - None (default) = AUTO: full color, quantized only as much as needed
            to keep dense frames at one write/frame (best quality for the speed).
          - 0 = always true color (may take 2-3 writes for dense frames).
          - N (2-256) = force an N-color palette.
        `chunk_size` defaults to negotiated MTU−3.
        """
        from . import images
        chunk_size = self._chunk_size(chunk_size)
        if colors is None:
            png = images.encode_png_fit(source, max_bytes=chunk_size - 9)
        else:
            png = images.encode_png(source, colors=colors)
        msg = protocol.screencast_message(png)
        waiter = None
        if wait_ack:
            # register BEFORE writing — the ack can beat the write call's return
            waiter = asyncio.ensure_future(self._wait_notify(
                ack_timeout,
                pred=lambda b: len(b) == 5 and b[:4] == bytes([5, 0, 0, 0])))
        for off in range(0, len(msg), chunk_size):
            await self._write(msg[off:off + chunk_size], response=True)
        return await waiter if waiter else None

    async def stream(self, frames, *, fps: float = 10.0, loops: int = 1,
                     open_graffiti: bool = True, close_graffiti: bool = False,
                     wait_ack: bool = True, colors: Optional[int] = None,
                     on_frame=None):
        """Live-play a sequence of frames via the screencast path.

        `frames` is any iterable of PIL.Image (any size — resized to 48x12),
        including a generator. Opens graffiti mode (so frames persist between
        pushes), then screencasts each frame, pacing to `fps`. With wait_ack the
        device gates at ~7.7 fps; set wait_ack=False to push faster (may drop).

        `loops` replays the sequence, which requires holding every frame in
        memory — so it is only materialized when loops > 1. At the default
        loops=1 a generator is consumed lazily, which is what makes streaming an
        ENDLESS generator (a live effect, an audio-reactive source) work:
        materializing one would never return.

        Returns the number of frames sent.
        """
        if loops > 1:
            frames = list(frames)      # replaying needs the frames kept around
        interval = 1.0 / fps if fps > 0 else 0.0
        sent = 0
        if open_graffiti:
            await self.graffiti(True)
            await asyncio.sleep(0.3)
        try:
            loop = asyncio.get_running_loop()
            for _ in range(max(1, loops)):
                for i, fr in enumerate(frames):
                    t0 = loop.time()
                    await self.screencast(fr, wait_ack=wait_ack, colors=colors)
                    sent += 1
                    if on_frame:
                        on_frame(sent, i)
                    if interval:
                        dt = interval - (loop.time() - t0)
                        if dt > 0:
                            await asyncio.sleep(dt)
        finally:
            if close_graffiti:
                await self.graffiti(False)
        return sent

    async def upload_image(self, path: str, **kw):
        """Upload an image file. If not already a 48x12 GIF, prefer show_image()."""
        from . import images
        await self.upload_bytes(images.read_file_for_upload(path), **kw)
