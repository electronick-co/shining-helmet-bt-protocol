"""Encoder / frame-helper tests. No hardware needed.

These pin the encoding rules the panel actually requires — several of them are
non-obvious device quirks that cost a live debugging session to find, so a
regression here would silently produce a blank display.
"""
import io

import pytest

PILImage = pytest.importorskip("PIL.Image")

from shining_helmet import constants as C          # noqa: E402
from shining_helmet import images                  # noqa: E402


def _gradient(w=C.WIDTH, h=C.HEIGHT):
    im = PILImage.new("RGB", (w, h))
    for x in range(w):
        for y in range(h):
            im.putpixel((x, y), (x * 5 % 256, y * 20 % 256, (x + y) * 3 % 256))
    return im


def _animation(n=4):
    return [PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (i * 40, 0, 0)) for i in range(n)]


# ---------------------------------------------------------------- GIF encoding
def test_encode_gif_is_gif_at_panel_size():
    gif = images.encode_gif(_gradient())
    assert gif[:3] == b"GIF"
    im = PILImage.open(io.BytesIO(gif))
    assert im.size == (C.WIDTH, C.HEIGHT)


def test_encode_gif_resizes_arbitrary_input():
    gif = images.encode_gif(PILImage.new("RGB", (500, 300), (1, 2, 3)))
    assert PILImage.open(io.BytesIO(gif)).size == (C.WIDTH, C.HEIGHT)


def test_encode_gif_keeps_every_frame_of_an_animation():
    src = io.BytesIO()
    frames = _animation(5)
    frames[0].save(src, format="GIF", save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    src.seek(0)
    out = PILImage.open(io.BytesIO(images.encode_gif(src)))
    assert getattr(out, "n_frames", 1) == 5


def test_encode_gif_sequence_collapses_identical_frames():
    # A held word should cost ONE frame with an accumulated delay, not fps*seconds
    # of duplicates -- that collapse is what buys show time under the 40960 cap.
    held = PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (255, 0, 0))
    moving = PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (0, 255, 0))
    seq = [held, held, held, moving]

    collapsed = PILImage.open(io.BytesIO(
        images.encode_gif_sequence(seq, fps=10, collapse=True)))
    assert collapsed.n_frames == 2
    assert collapsed.info["duration"] == 300          # 3 x 100 ms accumulated


def test_collapse_false_cannot_prevent_collapsing():
    """Pillow's GIF writer merges identical consecutive frames and sums their
    durations on its own, regardless of optimize= or disposal=. So collapse=False
    is NOT an escape hatch -- it produces byte-identical output. Anything that
    needs genuinely duplicated frames has to make them differ."""
    held = PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (255, 0, 0))
    moving = PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (0, 255, 0))
    seq = [held, held, held, moving]

    on = images.encode_gif_sequence(seq, fps=10, collapse=True)
    off = images.encode_gif_sequence(seq, fps=10, collapse=False)
    assert on == off
    assert PILImage.open(io.BytesIO(off)).n_frames == 2


def test_encode_gif_sequence_rejects_empty():
    with pytest.raises(ValueError):
        images.encode_gif_sequence([])


# ---------------------------------------------------------------- PNG encoding
def test_encode_png_is_always_truecolor_rgb():
    # The helmet renders RGB PNGs but shows palette ("P" mode) PNGs BLANK, so
    # quantizing must always convert back to RGB.
    for colors in (0, 4, 8, 32, 256):
        png = images.encode_png(_gradient(), colors=colors)
        assert PILImage.open(io.BytesIO(png)).mode == "RGB", f"colors={colors}"


def test_encode_png_fit_prefers_full_color_when_it_fits():
    src = PILImage.new("RGB", (C.WIDTH, C.HEIGHT), (10, 20, 30))   # trivially small
    assert images.encode_png_fit(src, max_bytes=10_000) == images.encode_png(src)


def test_encode_png_fit_quantizes_only_when_over_budget():
    src = _gradient()
    full = images.encode_png(src)
    tight = images.encode_png_fit(src, max_bytes=len(full) - 1)
    assert len(tight) <= len(full)
    assert PILImage.open(io.BytesIO(tight)).mode == "RGB"


def test_encode_png_fit_returns_smallest_when_nothing_fits():
    # An impossible budget must still return usable bytes, not raise.
    out = images.encode_png_fit(_gradient(), max_bytes=1)
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------- frame helpers
def test_load_frame_returns_flat_row_major_pixels(tmp_path):
    p = tmp_path / "src.png"
    _gradient().save(p)
    px = images.load_frame(str(p))
    assert len(px) == C.WIDTH * C.HEIGHT
    assert all(len(v) == 3 for v in px[:10])


def test_frame_to_draw_writes_covers_every_pixel():
    px = [(1, 2, 3)] * (C.WIDTH * C.HEIGHT)
    writes, seq = images.frame_to_draw_writes(px, start_seq=0)
    assert len(writes) == C.WIDTH * C.HEIGHT
    assert seq == C.WIDTH * C.HEIGHT
    assert all(len(w) == 11 for w in writes)


def test_frame_to_draw_writes_can_skip_black():
    px = [(0, 0, 0)] * (C.WIDTH * C.HEIGHT)
    px[0] = (255, 0, 0)
    writes, _ = images.frame_to_draw_writes(px, skip_black=True)
    assert len(writes) == 1


def test_text_frame_is_panel_sized_and_thresholded():
    # Antialiased grey edges are unreadable at 12 px tall, so glyph rendering
    # must produce hard on/off pixels only.
    fr = images.text_frame("HI", color=(255, 255, 255), bg=(0, 0, 0))
    assert fr.size == (C.WIDTH, C.HEIGHT)
    assert {c for _, c in fr.getcolors()} <= {(0, 0, 0), (255, 255, 255)}


def test_fit_text_frame_shrinks_long_text_to_fit():
    short = images.fit_text_frame("HI")
    long = images.fit_text_frame("A MUCH LONGER STRING OF TEXT")
    assert short.size == long.size == (C.WIDTH, C.HEIGHT)
    assert {c for _, c in long.getcolors()} <= {(0, 0, 0), (255, 255, 255)}


def test_scroll_frames_are_lazy_and_panel_sized():
    import types
    gen = images.scroll_frames("SCROLL ME")
    assert isinstance(gen, types.GeneratorType)      # stream() relies on laziness
    frames = list(gen)
    assert len(frames) > 1
    assert all(f.size == (C.WIDTH, C.HEIGHT) for f in frames)


def test_iter_video_frames_reads_an_animation(tmp_path):
    p = tmp_path / "anim.gif"
    frames = _animation(6)
    frames[0].save(p, format="GIF", save_all=True, append_images=frames[1:],
                   duration=80, loop=0)
    got = list(images.iter_video_frames(str(p)))
    assert len(got) == 6
    assert all(f.size == (C.WIDTH, C.HEIGHT) for f in got)
    assert len(list(images.iter_video_frames(str(p), max_frames=2))) == 2
