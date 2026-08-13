"""Image helpers: load/resize to 48x12 and turn a frame into draw-pixel writes.

Requires the optional `pillow` dependency:  pip install "shining-helmet[images]"
"""
from __future__ import annotations
from . import constants as C
from . import protocol

try:
    from PIL import Image, ImageSequence, ImageDraw, ImageFont  # noqa: F401
    _HAVE_PIL = True
except ImportError:  # pragma: no cover
    _HAVE_PIL = False

# Common system fonts to try for text rendering (first that loads wins).
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
_font_cache: dict = {}


def _require_pil():
    if not _HAVE_PIL:
        raise RuntimeError('Pillow required: pip install "shining-helmet[images]"')


def load_frame(path: str):
    """Open an image and return a WIDTH*HEIGHT list of (r,g,b), nearest-resized."""
    _require_pil()
    im = Image.open(path).convert("RGB").resize((C.WIDTH, C.HEIGHT), Image.NEAREST)
    px = im.load()
    return [px[x, y] for y in range(C.HEIGHT) for x in range(C.WIDTH)]


def frame_to_pixels(pixels):
    """Yield (x, y, (r,g,b)) for a flat row-major WIDTH*HEIGHT pixel list."""
    for i, rgb in enumerate(pixels):
        yield i % C.WIDTH, i // C.WIDTH, rgb


def frame_to_draw_writes(pixels, start_seq: int = 0, skip_black: bool = False):
    """Build the full list of draw_pixel() frames for one image.

    Returns (writes, next_seq). This is the *graffiti* path (per-pixel) — VERIFIED
    to be accepted by the device. For large/animated content the bulk image-upload
    path (protocol.upload_blocks) is far more efficient.

    TODO(verify:draw-orientation) confirm origin/axis & RGB order on the panel.
    """
    seq = start_seq
    writes = []
    for x, y, rgb in frame_to_pixels(pixels):
        if skip_black and rgb == (0, 0, 0):
            continue
        writes.append(protocol.draw_pixel(x, y, rgb, seq))
        seq += 1
    return writes, seq


def encode_gif(source, *, duration_ms: int | None = None) -> bytes:
    """Return 48x12 GIF bytes ready for upload_bytes().

    `source` may be a file path or a PIL.Image. VERIFIED: the device renders
    uploaded **GIF** (a PNG upload is accepted but displays blank), so this is the
    encoder to use for the bulk/persistent display path.

    Animated sources keep all their frames (output is an animated GIF, looped).
    `duration_ms` overrides the per-frame duration; defaults to the source's
    timing or 200 ms.
    """
    _require_pil()
    import io
    im = source if isinstance(source, Image.Image) else Image.open(source)
    frames = [f.convert("RGB").resize((C.WIDTH, C.HEIGHT), Image.NEAREST)
              for f in ImageSequence.Iterator(im)]
    buf = io.BytesIO()
    if len(frames) == 1:
        frames[0].save(buf, format="GIF")  # Pillow emits GIF87a for a static frame
    else:
        dur = duration_ms or im.info.get("duration") or 200
        frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                       duration=dur, loop=0)
    return buf.getvalue()


def encode_gif_sequence(frames, *, fps: float = 10.0, colors: int = 8,
                        collapse: bool = True) -> bytes:
    """Encode an iterable of PIL frames as one 48x12 animated GIF for upload.

    Unlike `encode_gif` (which re-encodes an existing image at a single frame
    duration), this takes generated frames and gives every frame its own delay,
    so `collapse` can merge runs of IDENTICAL consecutive frames into a single
    frame with the accumulated duration. For a text show — where a word is held
    for half a second — that is a large saving: the held run costs one frame
    instead of `fps/2`, and the device's 40960-byte cap (C.MAX_UPLOAD_BYTES)
    buys much more show time.

    `colors` quantizes each frame (8 keeps GIFs small; 0 = full color).

    NOTE on `collapse`: Pillow's GIF writer ALREADY merges identical consecutive
    frames and sums their durations, unconditionally — `optimize=` and
    `disposal=` do not disable it. So `collapse=False` produces byte-identical
    output and is not an escape hatch; it only skips doing the same work here
    first. Producing genuinely repeated frames would require making them differ.

    TODO(verify:gif-frame-delays): the stored file keeps the per-frame delays,
    but it is not yet eyeballed whether the panel honors them or re-times every
    frame equally. If it re-times, the fix is to render at a uniform delay and
    repeat *slightly differing* frames — not to pass collapse=False.
    """
    _require_pil()
    import io
    step_ms = max(10, int(round(1000 / fps)))
    out, durations = [], []
    for f in frames:
        f = f.convert("RGB").resize((C.WIDTH, C.HEIGHT), Image.NEAREST)
        if colors and 2 <= colors <= 256:
            f = f.quantize(colors=colors, method=Image.FASTOCTREE).convert("RGB")
        if collapse and out and f.tobytes() == out[-1].tobytes():
            durations[-1] += step_ms
        else:
            out.append(f)
            durations.append(step_ms)
    if not out:
        raise ValueError("no frames")
    buf = io.BytesIO()
    if len(out) == 1:
        out[0].save(buf, format="GIF")
    else:
        out[0].save(buf, format="GIF", save_all=True, append_images=out[1:],
                    duration=durations, loop=0)
    return buf.getvalue()


def encode_png(source, *, colors: int = 0) -> bytes:
    """Return 48x12 PNG bytes for the type-00 screencast path.

    The app's graffiti canvas snapshots are PNGs (~140-250 B), so PNG is the
    captured-known-good format for screencast (unlike the upload path, which
    needs GIF). `source` is a file path or PIL.Image.

    `colors` (2-256): reduce the number of distinct colors before encoding.
    Full-color frames (e.g. plasma) make ~1 KB PNGs = 2-3 BLE writes/frame;
    fewer colors compress smaller (≈1 write) for a big live-fps gain with little
    visible loss. 0 = no reduction (full true color).

    NOTE: the output is ALWAYS a true-color (RGB) PNG. The helmet's decoder
    renders RGB PNGs but shows palette/indexed (mode "P") PNGs as BLANK, so even
    when reducing colors we quantize then convert back to RGB.
    """
    _require_pil()
    import io
    im = source if isinstance(source, Image.Image) else Image.open(source)
    im = im.convert("RGB").resize((C.WIDTH, C.HEIGHT), Image.NEAREST)
    if colors and 2 <= colors <= 256:
        im = im.quantize(colors=colors, method=Image.FASTOCTREE).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def encode_png_fit(source, max_bytes: int) -> bytes:
    """Encode a 48x12 PNG that fits in `max_bytes`, preserving as much color as
    possible. Tries true color first; only if it's too big does it quantize
    (32→16→8→4 colors), stopping at the first palette that fits. Returns the
    smallest option if none fit.

    This is the right default for live streaming: sparse/few-color frames
    (matrix, text) stay full-quality, while dense full-color frames (plasma,
    fire) are quantized just enough to stay at one BLE write/frame.
    """
    _require_pil()
    best = encode_png(source)
    if len(best) <= max_bytes:
        return best
    for n in (32, 16, 8, 4):
        cand = encode_png(source, colors=n)
        if len(cand) < len(best):
            best = cand
        if len(best) <= max_bytes:
            break
    return best


def load_font(size: int, path: str | None = None):
    """Load a TrueType font at `size` px, trying common system fonts; falls back
    to PIL's built-in bitmap font if none are found."""
    _require_pil()
    key = (path, size)
    if key in _font_cache:
        return _font_cache[key]
    candidates = [path] if path else _FONT_CANDIDATES
    font = None
    for p in candidates:
        if not p:
            continue
        try:
            font = ImageFont.truetype(p, size)
            break
        except (OSError, ValueError):
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def render_text_strip(text, *, color=(255, 255, 255), bg=(0, 0, 0),
                      font_size: int = 11, font_path: str | None = None,
                      pad: int = 2, threshold: int = 96):
    """Render `text` to a HEIGHT-tall RGB strip as wide as the text needs.
    Used as the source for a scrolling marquee. Vertically centered.

    Rendered CRISP: the glyph mask is thresholded so each pixel is either full
    `color` or `bg` — no antialiased grey "shadow" pixels, which are hard to read
    on a 12 px panel. `threshold` (0-255) sets the cutoff; lower = thicker text.
    """
    _require_pil()
    font = load_font(font_size, font_path)
    # measure on a 1-channel mask
    tmp = Image.new("L", (1, 1))
    d = ImageDraw.Draw(tmp)
    box = d.textbbox((0, 0), text, font=font)
    tw = (box[2] - box[0]) + pad * 2
    w = max(tw, C.WIDTH)
    mask = Image.new("L", (w, C.HEIGHT), 0)
    d = ImageDraw.Draw(mask)
    ty = (C.HEIGHT - (box[3] - box[1])) // 2 - box[1]
    d.text((pad, ty), text, fill=255, font=font)
    # threshold -> hard 1-bit mask, then composite color over bg
    mask = mask.point(lambda v: 255 if v >= threshold else 0)
    strip = Image.new("RGB", (w, C.HEIGHT), bg)
    strip.paste(Image.new("RGB", (w, C.HEIGHT), color), (0, 0), mask)
    return strip


def text_frame(text, **kw):
    """A single 48x12 frame with `text` centered (truncated if too wide)."""
    _require_pil()
    strip = render_text_strip(text, **kw)
    frame = Image.new("RGB", (C.WIDTH, C.HEIGHT), kw.get("bg", (0, 0, 0)))
    x = (C.WIDTH - strip.width) // 2
    frame.paste(strip, (x, 0))
    return frame


def fit_text_frame(text, *, color=(255, 255, 255), bg=(0, 0, 0),
                   font_path: str | None = None, max_size: int = 12,
                   min_size: int = 5, threshold: int = 96, margin: int = 1):
    """A 48x12 frame with `text` sized as LARGE as fits, centered on BOTH axes
    (tight to the actual glyph pixels, so vertical centering ignores font
    ascent/descent padding). Good for word-by-word display — short words fill
    the panel, long ones shrink to fit.
    """
    _require_pil()
    avail_w = C.WIDTH - margin * 2
    chosen, box = min_size, None
    for size in range(max_size, min_size - 1, -1):
        font = load_font(size, font_path)
        d = ImageDraw.Draw(Image.new("L", (1, 1)))
        b = d.textbbox((0, 0), text, font=font)
        if (b[2] - b[0]) <= avail_w and (b[3] - b[1]) <= C.HEIGHT:
            chosen, box = size, b
            break
    font = load_font(chosen, font_path)
    if box is None:
        box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    # render the glyphs onto a tight mask (offset by the bbox origin), threshold
    mask = Image.new("L", (max(tw, 1), max(th, 1)), 0)
    ImageDraw.Draw(mask).text((-box[0], -box[1]), text, fill=255, font=font)
    mask = mask.point(lambda v: 255 if v >= threshold else 0)
    frame = Image.new("RGB", (C.WIDTH, C.HEIGHT), bg)
    ox = (C.WIDTH - tw) // 2
    oy = (C.HEIGHT - th) // 2
    frame.paste(Image.new("RGB", mask.size, color), (ox, oy), mask)
    return frame


def scroll_frames(text, *, step: int = 1, gap: int = C.WIDTH, **kw):
    """Yield 48x12 frames scrolling `text` right-to-left (marquee).

    Scrolls from fully off-screen right to fully off-screen left, with `gap`
    blank columns trailing so it loops cleanly. `step` px per frame.
    Pass through render_text_strip kwargs (color, bg, font_size, font_path).
    """
    _require_pil()
    bg = kw.get("bg", (0, 0, 0))
    strip = render_text_strip(text, **kw)
    total = strip.width + gap
    canvas = Image.new("RGB", (total, C.HEIGHT), bg)
    canvas.paste(strip, (0, 0))
    # start with text just off the right edge, scroll until off the left
    for off in range(-C.WIDTH, total, step):
        frame = Image.new("RGB", (C.WIDTH, C.HEIGHT), bg)
        frame.paste(canvas, (-off, 0))
        yield frame


def iter_video_frames(source, *, max_frames: int | None = None):
    """Yield 48x12 RGB frames from an animated source.

    Natively supports animated GIF / WebP / APNG (via Pillow). For MP4/MOV,
    install `imageio[ffmpeg]` and use iter_mp4_frames instead. `source` is a
    path or PIL.Image.
    """
    _require_pil()
    im = source if isinstance(source, Image.Image) else Image.open(source)
    for i, fr in enumerate(ImageSequence.Iterator(im)):
        if max_frames and i >= max_frames:
            break
        yield fr.convert("RGB").resize((C.WIDTH, C.HEIGHT), Image.NEAREST)


def iter_mp4_frames(path, *, stride: int = 1, max_frames: int | None = None):
    """Yield 48x12 RGB frames from an MP4/MOV/etc. Requires `imageio[ffmpeg]`
    (pip install imageio imageio-ffmpeg). `stride` skips frames (downsample fps).
    """
    _require_pil()
    try:
        import imageio.v3 as iio
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("MP4 playback needs: pip install imageio imageio-ffmpeg") from e
    count = 0
    for i, frame in enumerate(iio.imiter(path, plugin="pyav")):
        if i % stride:
            continue
        yield (Image.fromarray(frame).convert("RGB")
               .resize((C.WIDTH, C.HEIGHT), Image.NEAREST))
        count += 1
        if max_frames and count >= max_frames:
            break


def read_file_for_upload(path: str) -> bytes:
    """Read a GIF/PNG verbatim for the bulk upload path.

    The device displays real GIF/PNG files at 48x12. This returns the raw bytes;
    callers should ensure the image is already 48x12 (use a tool to pre-size, or
    re-encode a load_frame() result). TODO(verify:upload-format) confirm whether
    the device requires a specific encoder/palette/format variant.
    """
    with open(path, "rb") as f:
        return f.read()
