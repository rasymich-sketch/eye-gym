"""Крупные схемы упражнений: смотреть на рисунок, без абзаца текста."""

from __future__ import annotations

import math
import tkinter as tk

INK = "#241c18"
TRACK = "#e6d9c8"
ACCENT = "#1a6b73"
SOFT = "#c5e0e2"
SKIN = "#f4d4c0"
SKIN_DEEP = "#e2b79a"
WHITE = "#fffefb"
IRIS = "#2c6678"
PUPIL = "#1a1a1a"
SKY = "#d5f0f4"
HILL = "#7eaf6e"
SUN = "#f0c14a"
CARD = "#fffdf9"


def draw_picture(canvas: tk.Canvas, kind: str, elapsed: float, duration: float, width: int, height: int) -> None:
    canvas.delete("all")
    drawer = {
        "ready": _ready,
        "blink": _blink,
        "vertical": _vertical,
        "horizontal": _horizontal,
        "diagonal": _diagonal,
        "circle": _circle,
        "eight": _eight,
        "nearfar": _nearfar,
        "palming": _palming,
    }.get(kind, _ready)
    drawer(canvas, elapsed, max(duration, 1), width, height)


def _dot(canvas: tk.Canvas, x: float, y: float, radius: float, fill: str) -> None:
    canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=fill, outline="")
    if radius >= 16:
        canvas.create_oval(
            x - radius * 0.42,
            y - radius * 0.55,
            x - radius * 0.05,
            y - radius * 0.12,
            fill="#f4fbfb",
            outline="",
        )


def _follow(canvas: tk.Canvas, at, elapsed: float) -> tuple[float, float]:
    for back, radius, fill in ((0.34, 11, "#efe4d6"), (0.22, 15, "#b9d8da"), (0.11, 19, "#4e98a0")):
        x, y = at(max(0.0, elapsed - back))
        _dot(canvas, x, y, radius, fill)
    x, y = at(elapsed)
    _dot(canvas, x, y, 28, ACCENT)
    return x, y


def _arrow(canvas: tk.Canvas, x: float, y: float, dx: float, dy: float, size: float = 26) -> None:
    length = math.hypot(dx, dy) or 1
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    canvas.create_polygon(
        x + ux * size,
        y + uy * size,
        x + px * size * 0.62,
        y + py * size * 0.62,
        x - px * size * 0.62,
        y - py * size * 0.62,
        fill=ACCENT,
        outline="",
    )


def _face(canvas: tk.Canvas, cx: float, cy: float, radius: float) -> None:
    canvas.create_oval(cx - radius * 0.22, cy - radius * 0.15, cx - radius * 1.05, cy + radius * 0.35, fill=SKIN_DEEP, outline="")
    canvas.create_oval(cx + radius * 0.22, cy - radius * 0.15, cx + radius * 1.05, cy + radius * 0.35, fill=SKIN_DEEP, outline="")
    canvas.create_oval(
        cx - radius,
        cy - radius * 1.08,
        cx + radius,
        cy + radius * 1.18,
        fill=SKIN,
        outline=INK,
        width=5,
    )


def _eye(
    canvas: tk.Canvas,
    cx: float,
    cy: float,
    radius: float,
    pupil: tuple[float, float] = (0, 0),
    lid: float = 0,
) -> None:
    ew, eh = radius * 0.40, radius * 0.22
    openness = max(0.0, 1.0 - min(1.0, lid))
    if openness < 0.18:
        canvas.create_arc(
            cx - ew,
            cy - eh * 0.35,
            cx + ew,
            cy + eh * 0.7,
            start=200,
            extent=140,
            style="arc",
            outline=INK,
            width=6,
        )
        return
    eh_now = eh * openness
    canvas.create_oval(cx - ew, cy - eh_now, cx + ew, cy + eh_now, fill=WHITE, outline=INK, width=5)
    pr = min(eh_now * 0.75, eh * 0.62)
    ix = cx + pupil[0] * openness
    iy = cy + pupil[1] * openness
    canvas.create_oval(ix - pr, iy - pr, ix + pr, iy + pr, fill=IRIS, outline="")
    canvas.create_oval(ix - pr * 0.45, iy - pr * 0.45, ix + pr * 0.45, iy + pr * 0.45, fill=PUPIL, outline="")


def _eyes(canvas: tk.Canvas, cx: float, cy: float, radius: float, pupil: tuple[float, float], lid: float) -> None:
    shift = radius * 0.38
    _eye(canvas, cx - shift, cy - radius * 0.08, radius, pupil, lid)
    _eye(canvas, cx + shift, cy - radius * 0.08, radius, pupil, lid)


def _ready(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    cx, cy = width / 2, height * 0.40
    radius = min(width, height) * 0.30
    shoulder_y = cy + radius * 1.35
    canvas.create_polygon(
        cx - radius * 0.28,
        cy + radius * 0.95,
        cx + radius * 0.28,
        cy + radius * 0.95,
        cx + radius * 1.35,
        shoulder_y + radius * 0.35,
        cx - radius * 1.35,
        shoulder_y + radius * 0.35,
        fill="#f7e4d6",
        outline=INK,
        width=5,
    )
    _face(canvas, cx, cy, radius)
    _eyes(canvas, cx, cy, radius, (0, 0), 0.05)


def _blink(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    cx, cy = width / 2, height / 2
    radius = min(width, height) * 0.36
    lid = 0.12 + 0.78 * abs(math.sin(elapsed * math.pi * 1.15))
    _face(canvas, cx, cy, radius)
    _eyes(canvas, cx, cy, radius, (0, 0), lid)


def _span(width: int, height: int) -> tuple[float, float, float, float, float, float]:
    margin = 46
    return width / 2, height / 2, margin, width - margin, margin, height - margin


def _vertical(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    cx, _cy, _left, _right, top, bottom = _span(width, height)
    canvas.create_line(cx, top, cx, bottom, fill=TRACK, width=18, capstyle="round")
    _arrow(canvas, cx, top + 8, 0, -1)
    _arrow(canvas, cx, bottom - 8, 0, 1)

    def at(t: float) -> tuple[float, float]:
        y = (top + bottom) / 2 + math.sin(t / 3.2 * 2 * math.pi) * ((bottom - top) / 2 - 36)
        return cx, y

    _follow(canvas, at, elapsed)


def _horizontal(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    _cx, cy, left, right, _top, _bottom = _span(width, height)
    canvas.create_line(left, cy, right, cy, fill=TRACK, width=18, capstyle="round")
    _arrow(canvas, left + 8, cy, -1, 0)
    _arrow(canvas, right - 8, cy, 1, 0)

    def at(t: float) -> tuple[float, float]:
        x = (left + right) / 2 + math.sin(t / 3.2 * 2 * math.pi) * ((right - left) / 2 - 36)
        return x, cy

    _follow(canvas, at, elapsed)


def _diagonal(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    _cx, _cy, left, right, top, bottom = _span(width, height)
    first = ((right, top), (left, bottom))
    second = ((left, top), (right, bottom))
    which = int(elapsed // 4) % 2
    start, end = (first, second)[which]
    other = second if which == 0 else first
    canvas.create_line(*other[0], *other[1], fill="#f3ece3", width=12, capstyle="round")
    canvas.create_line(*start, *end, fill=TRACK, width=18, capstyle="round")
    _arrow(canvas, end[0], end[1], end[0] - start[0], end[1] - start[1])

    def at(t: float) -> tuple[float, float]:
        local = t % 4
        u = (1 - math.cos(local / 4 * 2 * math.pi)) / 2
        pair = (first, second)[int(t // 4) % 2]
        x = pair[0][0] + (pair[1][0] - pair[0][0]) * u
        y = pair[0][1] + (pair[1][1] - pair[0][1]) * u
        return x, y

    _follow(canvas, at, elapsed)


def _circle(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    cx, cy, *_rest = _span(width, height)
    radius = min(width, height) * 0.34
    canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=TRACK, width=16)
    clockwise = elapsed < duration / 2
    turn = 1 if clockwise else -1
    local = elapsed if clockwise else elapsed - duration / 2

    def at(t: float) -> tuple[float, float]:
        clock = t < duration / 2
        sign = 1 if clock else -1
        moment = t if clock else t - duration / 2
        angle = sign * moment / 5.5 * 2 * math.pi
        return cx + math.cos(angle) * radius, cy + math.sin(angle) * radius

    dot_x, dot_y = _follow(canvas, at, elapsed)
    angle = turn * local / 5.5 * 2 * math.pi
    tangent_x = -math.sin(angle) * turn
    tangent_y = math.cos(angle) * turn
    _arrow(canvas, dot_x + tangent_x * 40, dot_y + tangent_y * 40, tangent_x, tangent_y, 20)


def _eight(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    cx, cy, *_rest = _span(width, height)
    rx = (width - 120) / 2
    ry = (height - 120) / 2

    def at(t: float) -> tuple[float, float]:
        angle = t / 5.0 * 2 * math.pi
        return cx + math.sin(angle) * rx, cy + math.sin(2 * angle) * ry * 0.55

    points: list[float] = []
    for step in range(73):
        x, y = at(step / 72 * 5)
        points.extend((x, y))
    canvas.create_line(*points, fill=TRACK, width=16, smooth=True, capstyle="round")
    _follow(canvas, at, elapsed)


def _nearfar(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    near = int(elapsed // 3) % 2 == 0
    _target_finger(canvas, width * 0.28, height * 0.56, 1.08 if near else 0.78, near)
    _target_window(canvas, width * 0.72, height * 0.50, 1.08 if not near else 0.78, not near)


def _target_finger(canvas: tk.Canvas, cx: float, cy: float, scale: float, active: bool) -> None:
    if active:
        canvas.create_oval(cx - 78 * scale, cy - 130 * scale, cx + 78 * scale, cy + 100 * scale, outline=ACCENT, width=8)
    fill = SKIN if active else "#e8ddd2"
    outline = INK if active else "#c2b4a6"
    width = 5 if active else 3
    s = scale
    canvas.create_oval(cx - 50 * s, cy - 8 * s, cx + 46 * s, cy + 78 * s, fill=fill, outline=outline, width=width)
    canvas.create_oval(cx - 62 * s, cy + 8 * s, cx - 16 * s, cy + 48 * s, fill=fill, outline=outline, width=width)
    canvas.create_rectangle(cx - 16 * s, cy - 78 * s, cx + 16 * s, cy + 8 * s, fill=fill, outline=outline, width=width)
    canvas.create_oval(cx - 16 * s, cy - 100 * s, cx + 16 * s, cy - 62 * s, fill=fill, outline=outline, width=width)


def _target_window(canvas: tk.Canvas, cx: float, cy: float, scale: float, active: bool) -> None:
    s = scale
    if active:
        canvas.create_oval(cx - 100 * s, cy - 90 * s, cx + 100 * s, cy + 90 * s, outline=ACCENT, width=8)
    frame = ACCENT if active else "#cbbbaa"
    x0, y0 = cx - 68 * s, cy - 52 * s
    x1, y1 = cx + 68 * s, cy + 52 * s
    canvas.create_rectangle(x0, y0, x1, y1, fill=SKY, outline=frame, width=8 if active else 4)
    canvas.create_polygon(x0 + 3, y1 - 3, cx - 4 * s, cy + 6 * s, x1 - 3, y1 - 3, fill=HILL, outline="")
    canvas.create_oval(cx + 16 * s, cy - 38 * s, cx + 40 * s, cy - 14 * s, fill=SUN, outline="")
    mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
    canvas.create_line(mid_x, y0, mid_x, y1, fill=frame, width=6)
    canvas.create_line(x0, mid_y, x1, mid_y, fill=frame, width=6)


def _palming(canvas: tk.Canvas, elapsed: float, duration: float, width: int, height: int) -> None:
    cx, cy = width / 2, height * 0.40
    radius = min(width, height) * 0.27
    canvas.create_line(40, height - 26, width - 40, height - 26, fill="#d9c7b2", width=8, capstyle="round")
    left_x, right_x = cx - radius * 0.62, cx + radius * 0.62
    hand_y = cy - radius * 0.02
    canvas.create_line(left_x, hand_y + 58, cx - radius * 1.15, height - 30, fill=SKIN_DEEP, width=30, capstyle="round")
    canvas.create_line(right_x, hand_y + 58, cx + radius * 1.15, height - 30, fill=SKIN_DEEP, width=30, capstyle="round")
    _face(canvas, cx, cy, radius)
    _hand(canvas, left_x, hand_y, flip=True)
    _hand(canvas, right_x, hand_y, flip=False)


def _hand(canvas: tk.Canvas, cx: float, cy: float, flip: bool) -> None:
    sign = -1 if flip else 1
    for dx, lift in ((-34, 6), (-12, 16), (12, 16), (34, 4)):
        fx = cx + sign * dx
        canvas.create_oval(fx - 13, cy - 86 - lift, fx + 13, cy + 6, fill=SKIN, outline=INK, width=4)
    canvas.create_oval(cx - 54, cy - 6, cx + 54, cy + 64, fill=SKIN, outline=INK, width=5)
    canvas.create_oval(cx + sign * 24, cy + 16, cx + sign * 72, cy + 64, fill=SKIN, outline=INK, width=4)
