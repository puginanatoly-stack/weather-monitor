"""Hand-rolled SVG charts — no charting library. Shared by every page in pages.py."""

from __future__ import annotations


def svg_line_chart(points: list[tuple[str, float]], width=700, height=200, color="#8a5a2e", unit="°C") -> str:
    if not points:
        return "<p>Нет данных.</p>"
    values = [v for _, v in points]
    y_min, y_max = min(values), max(values)
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    pad = (y_max - y_min) * 0.15
    y_min -= pad
    y_max += pad

    n = len(points)
    plot_w = width - 55
    plot_h = height - 40

    def sx(i: int) -> float:
        return 45 + (i / (n - 1)) * plot_w if n > 1 else 45

    def sy(v: float) -> float:
        return 15 + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h

    path_d = " ".join(f"{'M' if i == 0 else 'L'}{sx(i):.1f},{sy(v):.1f}" for i, (_, v) in enumerate(points))
    circles = "".join(f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="2.5" fill="{color}"/>' for i, (_, v) in enumerate(points))

    step = max(1, n // 8)
    x_labels = "".join(
        f'<text x="{sx(i):.1f}" y="{height - 6}" font-size="10" text-anchor="middle" class="axis">{label}</text>'
        for i, (label, _) in enumerate(points) if i % step == 0
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px">'
        f'<line x1="45" y1="15" x2="45" y2="{15 + plot_h}" class="grid"/>'
        f'<line x1="45" y1="{15 + plot_h}" x2="{45 + plot_w}" y2="{15 + plot_h}" class="grid"/>'
        f'<text x="41" y="19" font-size="10" text-anchor="end" class="axis">{y_max - pad:.0f}{unit}</text>'
        f'<text x="41" y="{15 + plot_h + 4}" font-size="10" text-anchor="end" class="axis">{y_min + pad:.0f}{unit}</text>'
        f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2"/>'
        f"{circles}{x_labels}"
        f"</svg>"
    )


def svg_bar_chart(points: list[tuple[str, float]], width=700, height=200, threshold=5.0, max_v=9.0) -> str:
    if not points:
        return "<p>Нет данных.</p>"
    n = len(points)
    plot_w = width - 55
    plot_h = height - 40
    bar_w = plot_w / n * 0.7

    def sx(i: int) -> float:
        return 45 + (i / n) * plot_w

    def sy(v: float) -> float:
        return 15 + plot_h - (v / max_v) * plot_h

    bars = ""
    for i, (_, v) in enumerate(points):
        x, y = sx(i), sy(v)
        h = (15 + plot_h) - y
        css_class = "bar-storm" if v >= threshold else "bar-ok"
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(h, 0):.1f}" class="{css_class}"/>'

    step = max(1, n // 8)
    x_labels = "".join(
        f'<text x="{sx(i) + bar_w / 2:.1f}" y="{height - 6}" font-size="10" text-anchor="middle" class="axis">{label}</text>'
        for i, (label, _) in enumerate(points) if i % step == 0
    )
    thr_y = sy(threshold)

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px">'
        f'<line x1="45" y1="{15 + plot_h}" x2="{45 + plot_w}" y2="{15 + plot_h}" class="grid"/>'
        f'<line x1="45" y1="{thr_y:.1f}" x2="{45 + plot_w}" y2="{thr_y:.1f}" class="threshold"/>'
        f'<text x="41" y="{thr_y + 3:.1f}" font-size="9" text-anchor="end" class="threshold-label">буря</text>'
        f"{bars}{x_labels}"
        f"</svg>"
    )


def svg_ring_gauge(rings: list[tuple[str, float, float, str]], center_label: str, center_sub: str, size=260) -> str:
    """'Earth Core'-style concentric ring gauge. rings: (label, value, max, color)."""
    cx = cy = size / 2
    stroke_w = 11
    gap = 15
    base_r = size / 2 - stroke_w / 2 - 4

    arcs = ""
    for i, (_, value, max_value, color) in enumerate(rings):
        r = base_r - i * gap
        frac = max(0.0, min(1.0, value / max_value)) if max_value else 0.0
        circumference = 2 * 3.14159265 * r
        dash = circumference * frac
        arcs += f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" class="ring-bg" stroke-width="{stroke_w}"/>'
        arcs += (
            f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" stroke="{color}" stroke-width="{stroke_w}" '
            f'stroke-dasharray="{dash:.1f} {circumference:.1f}" stroke-linecap="round" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )

    return (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        f"{arcs}"
        f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" class="ring-center-label">{center_label}</text>'
        f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" class="ring-center-sub">{center_sub}</text>'
        f"</svg>"
    )


def ring_legend(rings: list[tuple[str, float, float, str]], fmt: dict[str, str]) -> str:
    items = "".join(
        f'<div class="ring-legend-item"><span class="dot" style="background:{color}"></span>'
        f'{label}: <b>{fmt.get(label, "{:.0f}").format(value)}</b></div>'
        for label, value, _max, color in rings
    )
    return f'<div class="ring-legend">{items}</div>'


def kp_to_level(kp: float) -> tuple[str, str]:
    """Returns (short badge word, full description) — mirrors Calm/Active/Storm framing."""
    if kp < 4:
        return "Спокойно", "Спокойно"
    if kp < 5:
        return "Активно", "Неустойчиво"
    if kp < 6:
        return "Буря", "G1 — слабая буря"
    if kp < 7:
        return "Буря", "G2 — умеренная буря"
    if kp < 8:
        return "Буря", "G3 — сильная буря"
    if kp < 9:
        return "Буря", "G4 — очень сильная буря"
    return "Буря", "G5 — экстремальная буря"


def badge_class(word: str) -> str:
    return {"Спокойно": "badge-calm", "Активно": "badge-active", "Буря": "badge-storm"}.get(word, "badge-calm")
