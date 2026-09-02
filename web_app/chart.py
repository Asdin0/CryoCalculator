import functools
import math

import plotly.graph_objects as go

import backend_bridge
import units

PAPER = "#e9edeb"
INK = "#121a19"
INK_SOFT = "#4a5654"
RULE = "#b9c2be"

REGIONS = {
    "vapor": {"label": "VAPORE", "ink": "#09656d", "tint": "rgba(14,139,150,0.20)"},
    "liquid": {"label": "LIQUIDO", "ink": "#1b3fa0", "tint": "rgba(27,63,160,0.20)"},
    "gas": {"label": "GAS", "ink": "#26643f", "tint": "rgba(47,125,79,0.18)"},
    "supercritical": {"label": "SUPERCRITICO", "ink": "#694a8c", "tint": "rgba(107,75,143,0.20)"},
    "two-phase": {"label": "BIFASE", "ink": "#7c4d0e", "tint": "rgba(217,138,31,0.34)"},
    "solid": {"label": "SOLIDO", "ink": "#8a2f66", "tint": "rgba(168,80,136,0.20)"},
}

ISOCHORE_INK = "#b5302a"

FONT_UI = "Archivo, system-ui, sans-serif"
FONT_LABEL = "'Archivo Narrow', Archivo, system-ui, sans-serif"
FONT_DATA = "'Atkinson Hyperlegible Mono', ui-monospace, monospace"

MARKER_TRACES = 5


@functools.lru_cache(maxsize=None)
def _model_floor(fluid_key: str) -> float:
    lim = backend_bridge.limits(fluid_key)
    sat = backend_bridge.saturation_curve(fluid_key)
    melt = backend_bridge.melting_curve(fluid_key)

    drawn = [p for p in list(sat["dew_Pa"]) + list(sat["bubble_Pa"]) if p]
    drawn += [p for p in melt["pressure_Pa"] if p]
    for line in backend_bridge.isochores(fluid_key):
        drawn += [p for p in line["pressure_Pa"] if p]

    return min(drawn) if drawn else max(lim["p_min_Pa"], 1.0)


def view_floor(fluid_key: str, marker_p_Pa=None) -> float:
    lim = backend_bridge.limits(fluid_key)
    p_lo = max(lim["p_min_Pa"], 1.0)

    floor = _model_floor(fluid_key) / 3.0
    if marker_p_Pa and marker_p_Pa > 0:
        floor = min(floor, marker_p_Pa / 2.0)

    return max(p_lo, 10 ** math.floor(math.log10(max(floor, p_lo))))


def marker_xy(marker, p_unit):
    if not marker or not marker.get("pressure_Pa") or not marker.get("temperature_K"):
        return [], []
    return (
        [marker["temperature_K"]],
        [units.from_si("pressure", p_unit, marker["pressure_Pa"])],
    )


def scan_xy(scan, p_unit):
    if not scan or not scan.get("rows"):
        return [], []
    rows = scan["rows"]
    return (
        [rows[0]["temperature_K"], rows[-1]["temperature_K"]],
        [units.from_si("pressure", p_unit, rows[0]["pressure_Pa"]),
         units.from_si("pressure", p_unit, rows[-1]["pressure_Pa"])],
    )


def state_traces(marker, dome, p_unit, scan=None):
    mx, my = marker_xy(marker, p_unit)
    sx, sy = scan_xy(scan, p_unit)

    cx, cy = [], []
    if dome and dome.get("dew_Pa") and dome.get("bubble_Pa") and dome.get("temperature_K"):
        x = dome["temperature_K"]
        lo = units.from_si("pressure", p_unit, dome["dew_Pa"])
        hi = units.from_si("pressure", p_unit, dome["bubble_Pa"])
        cx, cy = [x, x], [lo, hi]

    return [(sx, sy), (mx, my), (mx, my), (mx, my), (cx, cy)]


def _x(values):
    return list(values)


def _y(values, p_unit):
    return [units.from_si("pressure", p_unit, v) for v in values]


def _ann_x(t_K):
    return math.log10(max(t_K, 1e-12))


def _ann_y(p_Pa, p_unit):
    return math.log10(max(units.from_si("pressure", p_unit, p_Pa), 1e-12))

_TICKS = {
    "K": (60, 80, 100, 130, 200, 300, 500, 700, 1000, 1500, 2000),
    "C": (-250, -200, -150, -100, -50, 0, 100, 200, 500, 700, 1000, 1500),
}


def _decade_label(value: float) -> str:
    exponent = round(math.log10(value))
    if -3 <= exponent <= 4:
        return f"{value:g}"
    return f"10<sup>{exponent}</sup>"


def _pressure_ticks(p_unit, p_view, p_hi):
    lo = units.from_si("pressure", p_unit, p_view)
    hi = units.from_si("pressure", p_unit, p_hi)
    if not (lo > 0 and hi > lo):
        return None, None

    values, text = [], []
    for exponent in range(math.ceil(math.log10(lo)), math.floor(math.log10(hi)) + 1):
        value = 10.0 ** exponent
        values.append(value)
        text.append(_decade_label(value))
    return values, text


def _temperature_ticks(t_unit, t_lo, t_hi):
    values, text = [], []
    for shown in _TICKS.get(t_unit, ()):
        t_K = units.to_si("temperature", t_unit, shown)
        if t_lo <= t_K <= t_hi:
            values.append(t_K)
            text.append(f"{shown:g}")
    return values, text


def build(fluid_key: str, t_unit: str, p_unit: str,
          marker=None, dome=None, scan=None, show_isochores: bool = True) -> go.Figure:
    lim = backend_bridge.limits(fluid_key)
    sat = backend_bridge.saturation_curve(fluid_key)
    melt = backend_bridge.melting_curve(fluid_key)

    t_lo, t_hi = lim["t_min_K"], lim["t_max_K"]
    p_lo, p_hi = max(lim["p_min_Pa"], 1.0), lim["p_max_Pa"]
    t_c, p_c = lim["t_critical_K"], lim["p_critical_Pa"]

    p_view = view_floor(fluid_key, (marker or {}).get("pressure_Pa"))

    fig = go.Figure()

    melt_above, solid_t, solid_p = [], [], []
    if sat["temperature_K"]:
        dew_t, dew_p = sat["temperature_K"], sat["dew_Pa"]
        bub_t, bub_p = sat["temperature_K"], sat["bubble_Pa"]

        _region(fig, "vapor",
                list(dew_t) + [t_c, dew_t[0]],
                list(dew_p) + [p_lo, p_lo], p_unit)

        melt_above = backend_bridge.melting_pressure_at(fluid_key, bub_t)
        upper = [min(p, p_hi) if (p and p > 0) else p_hi for p in melt_above]
        _region(fig, "liquid",
                list(bub_t) + list(reversed(bub_t)),
                list(bub_p) + list(reversed(upper)), p_unit)

        solid_t = [t for t, p in zip(bub_t, melt_above) if p and 0 < p < p_hi]
        solid_p = [p for p in melt_above if p and 0 < p < p_hi]
        if len(solid_t) >= 2:
            _region(fig, "solid",
                    solid_t + list(reversed(solid_t)),
                    solid_p + [p_hi] * len(solid_t), p_unit)

        if sat["has_band"]:
            _region(fig, "two-phase",
                    list(dew_t) + list(reversed(bub_t)),
                    list(dew_p) + list(reversed(bub_p)), p_unit)

    _region(fig, "gas", [t_c, t_hi, t_hi, t_c], [p_lo, p_lo, p_c, p_c], p_unit)
    _region(fig, "supercritical", [t_c, t_hi, t_hi, t_c], [p_c, p_c, p_hi, p_hi], p_unit)

    lettering = _Lettering([_ann_x(t_lo), _ann_x(t_hi)],
                           [_ann_y(p_view, p_unit), _ann_y(p_hi, p_unit)])

    if marker and marker.get("temperature_K") and marker.get("pressure_Pa"):
        lettering.take(_ann_x(marker["temperature_K"]),
                       _ann_y(marker["pressure_Pa"], p_unit))

    if dome and dome.get("dew_Pa") and dome.get("bubble_Pa") and dome.get("temperature_K"):
        lettering.take(_ann_x(dome["temperature_K"]),
                       _ann_y(math.sqrt(dome["dew_Pa"] * dome["bubble_Pa"]), p_unit))

    if scan and scan.get("rows"):
        middle = scan["rows"][len(scan["rows"]) // 2]
        lettering.take(_ann_x(middle["temperature_K"]),
                       _ann_y(middle["pressure_Pa"], p_unit))

    _stamp(fig, lettering, lim, t_unit, p_unit, t_hi, p_lo, p_hi, p_view)

    isochores = backend_bridge.isochores(fluid_key) if show_isochores else []
    if show_isochores:
        for index, line in enumerate(isochores):
            fig.add_trace(go.Scatter(
                x=_x(line["temperature_K"]), y=_y(line["pressure_Pa"], p_unit),
                mode="lines", line=dict(color=ISOCHORE_INK, width=1, dash="dot"),
                hovertemplate=(f"ρ = {line['rho_kg_m3']:.4g} kg/m³<extra></extra>"),
                name="", showlegend=False,
            ))
            drawn = [i for i, p in enumerate(line["pressure_Pa"]) if p is not None]
            if not drawn:
                continue
            target = int(len(drawn) * (0.42 + 0.07 * (index % 6)))
            mid = drawn[min(target, len(drawn) - 1)]
            x, y = (_ann_x(line["temperature_K"][mid]),
                    _ann_y(line["pressure_Pa"][mid], p_unit))
            fig.add_annotation(
                x=x, y=y,
                text=f"ρ {line['rho_kg_m3']:.3g}", showarrow=False,
                font=dict(family=FONT_LABEL, size=10, color=ISOCHORE_INK),
                bgcolor=PAPER, borderpad=2, opacity=0.96,
            )
            lettering.take(x, y)

    if any(p is not None for p in melt["pressure_Pa"]):
        fig.add_trace(go.Scatter(
            x=_x(melt["temperature_K"]), y=_y(melt["pressure_Pa"], p_unit),
            customdata=[units.from_si("temperature", t_unit, t)
                        for t in melt["temperature_K"]],
            mode="lines", line=dict(color=INK, width=1.5, dash="dash"),
            hovertemplate=("Curva di fusione<br>%{customdata:.4g} "
                           + units.label("temperature", t_unit) + "<extra></extra>"),
            name="", showlegend=False,
        ))

    if sat["temperature_K"]:
        if sat["has_band"]:
            for key, series, dash in (("dew_Pa", sat["dew_Pa"], "solid"),
                                      ("bubble_Pa", sat["bubble_Pa"], "longdash")):
                fig.add_trace(go.Scatter(
                    x=_x(sat["temperature_K"]), y=_y(series, p_unit),
                    mode="lines", line=dict(color=INK, width=2, dash=dash),
                    hovertemplate=("Rugiada" if key == "dew_Pa" else "Bolla") + "<extra></extra>",
                    name="", showlegend=False,
                ))
        else:
            fig.add_trace(go.Scatter(
                x=_x(sat["temperature_K"]), y=_y(sat["dew_Pa"], p_unit),
                mode="lines", line=dict(color=INK, width=2.4),
                hovertemplate="Curva di saturazione<extra></extra>",
                name="", showlegend=False,
            ))

    def inside(t_K, p_Pa):
        return t_lo <= t_K <= t_hi and p_lo <= p_Pa <= p_hi

    if inside(t_c, p_c):
        _landmark(fig, lettering, t_c, p_c, "PUNTO CRITICO", p_unit, ax=44, ay=-26)
    if lim["t_triple_K"] and lim["p_triple_Pa"] and inside(lim["t_triple_K"], lim["p_triple_Pa"]):
        _landmark(fig, lettering, lim["t_triple_K"], lim["p_triple_Pa"], "PUNTO TRIPLO",
                  p_unit, ax=-6, ay=34)

    if any(p is not None for p in melt["pressure_Pa"]):
        _curve_label(fig, lettering, melt["temperature_K"], melt["pressure_Pa"],
                     p_unit, "FUSIONE")

    if sat["temperature_K"]:
        if sat["has_band"]:
            _curve_label(fig, lettering, sat["temperature_K"], sat["bubble_Pa"],
                         p_unit, "BOLLA")
            _curve_label(fig, lettering, sat["temperature_K"], sat["dew_Pa"],
                         p_unit, "RUGIADA")
        else:
            _curve_label(fig, lettering, sat["temperature_K"], sat["dew_Pa"],
                         p_unit, "SATURAZIONE")

    if isochores:
        _curve_label(fig, lettering, isochores[0]["temperature_K"],
                     isochores[0]["pressure_Pa"], p_unit,
                     "ISOCORE ρ [kg/m³]", color=ISOCHORE_INK)

    def heights(lo, hi):
        centre = math.sqrt(lo * hi)
        return [centre, math.sqrt(lo * centre), math.sqrt(centre * hi)]

    _region_label(fig, lettering, "gas", math.sqrt(t_c * t_hi), heights(p_view, p_c), p_unit)
    _region_label(fig, lettering, "supercritical", math.sqrt(t_c * t_hi),
                  heights(p_c, p_hi), p_unit)
    if sat["temperature_K"]:
        mid = len(sat["temperature_K"]) // 2
        t_mid = sat["temperature_K"][mid]
        _region_label(fig, lettering, "vapor", t_mid,
                      heights(p_view, sat["dew_Pa"][mid]), p_unit)
        liquid_top = melt_above[mid] if (mid < len(melt_above) and melt_above[mid]
                                        and 0 < melt_above[mid] < p_hi) else p_hi
        _region_label(fig, lettering, "liquid", t_mid,
                      heights(sat["bubble_Pa"][mid], liquid_top), p_unit)

        if len(solid_t) >= 2:
            span = len(solid_t)
            interior = range(int(span * 0.15), max(int(span * 0.65), int(span * 0.15) + 1))
            widest = max(interior, key=lambda i: p_hi / solid_p[i])
            _region_label(fig, lettering, "solid", solid_t[widest],
                          heights(solid_p[widest], p_hi), p_unit)

        if sat["has_band"]:
            span = len(sat["dew_Pa"])
            interior = range(int(span * 0.18), max(int(span * 0.82), int(span * 0.18) + 1))
            widest = max(interior,
                         key=lambda i: (sat["bubble_Pa"][i] - sat["dew_Pa"][i])
                         / (sat["bubble_Pa"][i] or 1))
            _band_label(fig, lettering, "two-phase", sat["temperature_K"][widest],
                        math.sqrt(sat["dew_Pa"][widest] * sat["bubble_Pa"][widest]),
                        p_unit)

    (sx, sy), (mx, my), _, _, (cx, cy) = state_traces(marker, dome, p_unit, scan)

    fig.add_trace(go.Scatter(
        x=sx, y=sy, mode="lines",
        line=dict(color=INK, width=6),
        opacity=0.16,
        hovertemplate="Scansione<extra></extra>", showlegend=False, name="",
    ))

    fig.add_trace(go.Scatter(
        x=mx, y=my, mode="markers",
        marker=dict(size=15, color="rgba(0,0,0,0)", line=dict(color=PAPER, width=4)),
        hoverinfo="skip", showlegend=False, name="",
    ))
    fig.add_trace(go.Scatter(
        x=mx, y=my, mode="markers",
        marker=dict(size=15, symbol="circle-open", color=INK,
                    line=dict(color=INK, width=2.2)),
        hovertemplate="Stato corrente<extra></extra>", showlegend=False, name="",
    ))
    fig.add_trace(go.Scatter(
        x=mx, y=my, mode="markers",
        marker=dict(size=4, color=INK), hoverinfo="skip",
        showlegend=False, name="",
    ))

    fig.add_trace(go.Scatter(
        x=cx, y=cy, mode="lines+markers",
        line=dict(color=REGIONS["two-phase"]["ink"], width=2),
        marker=dict(size=30, symbol="line-ew", color=REGIONS["two-phase"]["ink"],
                    line=dict(color=REGIONS["two-phase"]["ink"], width=2)),
        hovertemplate="Coesistenza<extra></extra>", showlegend=False, name="",
    ))

    x_title = f"T [{units.label('temperature', t_unit)}]  ·  scala log"
    if t_unit != "K":
        x_title += " in K"

    t_tickvals, t_ticktext = _temperature_ticks(t_unit, t_lo, t_hi)
    p_tickvals, p_ticktext = _pressure_ticks(p_unit, p_view, p_hi)

    fig.update_layout(
        autosize=True,
        paper_bgcolor=PAPER, plot_bgcolor=PAPER,
        margin=dict(l=70, r=26, t=20, b=58),
        font=dict(family=FONT_UI, size=12, color=INK),
        hoverlabel=dict(bgcolor=PAPER, bordercolor=INK,
                        font=dict(family=FONT_DATA, size=12, color=INK)),
        showlegend=False, dragmode=False,
        meta=dict(
            t_offset=units.from_si("temperature", t_unit, 0.0),
            t_scale=(units.from_si("temperature", t_unit, 1.0)
                     - units.from_si("temperature", t_unit, 0.0)),
            p_unit=p_unit,
        ),
        xaxis=dict(
            title=dict(text=x_title, font=dict(family=FONT_LABEL, size=12)),
            type="log",
            range=[_ann_x(t_lo), _ann_x(t_hi)],
            **({"tickvals": t_tickvals, "ticktext": t_ticktext} if t_tickvals else {}),
            gridcolor=RULE, zeroline=False, linecolor=INK, linewidth=1.2,
            ticks="outside", tickcolor=INK, ticklen=5,
            tickfont=dict(family=FONT_DATA, size=11, color=INK_SOFT),
        ),
        yaxis=dict(
            title=dict(text=f"P [{units.label('pressure', p_unit)}]",
                       font=dict(family=FONT_LABEL, size=12)),
            type="log",
            range=[_ann_y(p_view, p_unit), _ann_y(p_hi, p_unit)],
            **({"tickvals": p_tickvals, "ticktext": p_ticktext} if p_tickvals else {}),
            gridcolor=RULE, zeroline=False, linecolor=INK, linewidth=1.2,
            ticks="outside", tickcolor=INK, ticklen=5,
            tickfont=dict(family=FONT_DATA, size=11, color=INK_SOFT),
        ),
        transition=dict(duration=0),
    )
    return fig


class _Lettering:
    def __init__(self, x_range, y_range):
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        self.placed = []

    def _norm(self, x, y):
        return ((x - self.x0) / (self.x1 - self.x0 or 1),
                (y - self.y0) / (self.y1 - self.y0 or 1))

    def clearance(self, x, y):
        if not self.placed:
            return 1.0
        nx, ny = self._norm(x, y)
        return min(math.hypot(nx - px, ny - py) for px, py in self.placed)

    def take(self, x, y):
        self.placed.append(self._norm(x, y))

    def roomiest(self, candidates):
        return max(candidates, key=lambda c: self.clearance(*c))

_LABEL_FRACTIONS = (0.22, 0.34, 0.46, 0.60, 0.74, 0.86)


def _curve_label(fig, lettering, temps, pressures, p_unit, text,
                 color=INK, size=10, fractions=_LABEL_FRACTIONS):
    drawn = [i for i, p in enumerate(pressures) if p is not None]
    if not drawn:
        return
    seen = {}
    for fraction in fractions:
        i = drawn[min(int(len(drawn) * fraction), len(drawn) - 1)]
        seen[i] = (_ann_x(temps[i]), _ann_y(pressures[i], p_unit))
    x, y = lettering.roomiest(list(seen.values()))
    fig.add_annotation(
        x=x, y=y, text=text, showarrow=False,
        font=dict(family=FONT_LABEL, size=size, color=color),
        bgcolor=PAPER, borderpad=2, opacity=0.96,
    )
    lettering.take(x, y)


def _number(value, unit_kind, unit):
    shown = units.from_si(unit_kind, unit, value)
    return f"{shown:g}"


def _stamp(fig, lettering, lim, t_unit, p_unit, t_hi, p_lo, p_hi, p_view):
    t_label = units.label("temperature", t_unit)
    p_label = units.label("pressure", p_unit)
    text = (
        f"{lim['label']}  ·  {lim['reference']}  ·  validità "
        f"{_number(lim['t_min_K'], 'temperature', t_unit)}–"
        f"{_number(lim['t_max_K'], 'temperature', t_unit)} {t_label}, "
        f"{_number(p_lo, 'pressure', p_unit)}–"
        f"{_number(p_hi, 'pressure', p_unit)} {p_label}"
    )
    x, y = _ann_x(t_hi), _ann_y(p_view, p_unit)
    fig.add_annotation(
        x=x, y=y, xanchor="right", yanchor="bottom",
        xshift=-6, yshift=6,
        text=text, showarrow=False,
        font=dict(family=FONT_LABEL, size=9, color=INK_SOFT),
        bgcolor=PAPER, borderpad=2, opacity=0.94,
    )
    lettering.take(x, y)


def _region(fig, key, t_values, p_values, p_unit):
    style = REGIONS[key]
    fig.add_trace(go.Scatter(
        x=_x(t_values), y=_y(p_values, p_unit),
        fill="toself", fillcolor=style["tint"],
        line=dict(width=0), mode="lines",
        hoverinfo="skip", showlegend=False, name="",
    ))


def _region_label(fig, lettering, key, t_K, pressures_Pa, p_unit):
    style = REGIONS[key]
    x, y = lettering.roomiest([(_ann_x(t_K), _ann_y(p, p_unit)) for p in pressures_Pa])
    fig.add_annotation(
        x=x, y=y,
        text=style["label"], showarrow=False,
        font=dict(family=FONT_LABEL, size=11, color=style["ink"]),
        bgcolor=PAPER, borderpad=2, opacity=0.9,
    )
    lettering.take(x, y)


def _band_label(fig, lettering, key, t_K, p_Pa, p_unit, ax=54, ay=34):
    style = REGIONS[key]
    x, y = _ann_x(t_K), _ann_y(p_Pa, p_unit)
    fig.add_annotation(
        x=x, y=y, text=style["label"],
        showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor=style["ink"],
        ax=ax, ay=ay,
        font=dict(family=FONT_LABEL, size=11, color=style["ink"]),
        bgcolor=PAPER, borderpad=2, opacity=0.96,
    )
    lettering.take(x, y)


def _landmark(fig, lettering, t_K, p_Pa, text, p_unit, ax=0, ay=-30):
    y = units.from_si("pressure", p_unit, p_Pa)
    fig.add_trace(go.Scatter(
        x=[t_K], y=[y], mode="markers",
        marker=dict(size=7, symbol="x-thin", color=INK, line=dict(color=INK, width=1.8)),
        hovertemplate=f"{text}<extra></extra>", showlegend=False, name="",
    ))
    fig.add_annotation(
        x=_ann_x(t_K),
        y=_ann_y(p_Pa, p_unit), text=text,
        showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor=INK,
        ax=ax, ay=ay,
        font=dict(family=FONT_LABEL, size=10, color=INK),
        bgcolor=PAPER, borderpad=3, opacity=0.98,
    )
    lettering.take(_ann_x(t_K), _ann_y(p_Pa, p_unit))
