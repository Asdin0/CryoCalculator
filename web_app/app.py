import json
import math
import os
import urllib.parse

import dash
from dash import Input, Output, Patch, State, dcc, html
from flask import request
from werkzeug.middleware.proxy_fix import ProxyFix

import backend_bridge
import chart
import format as fmt
import units

app = dash.Dash(
    __name__,
    title="CryoCalculator",
    update_title=None,
    suppress_callback_exceptions=True,
    compress=True,
)
server = app.server

server.wsgi_app = ProxyFix(server.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.index_string = """<!DOCTYPE html>
<html lang="it">
<head>
{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<meta name="description" content="Proprietà termodinamiche di fluidi reali dall'equazione di stato di Helmholtz.">
</head>
<body>
{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>"""

CSP = "; ".join((
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
))

_CSP_ENFORCED = os.environ.get("CSP_ENFORCE", "").strip().lower() in ("1", "true", "yes")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
}


@server.after_request
def _security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    response.headers.setdefault(
        "Content-Security-Policy" if _CSP_ENFORCED else "Content-Security-Policy-Report-Only",
        CSP,
    )
    if request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


@server.route("/healthz")
def _healthz():
    return {"status": "ok"}, 200

PROPERTY_NOTES = {
    "density_kg_m3": "Risolta per bisezione sull'equazione di pressione, non tabulata.",
    "compressibility_factor": "Pv/RT. Vale 1 per il gas ideale; lo scarto da 1 misura quanto il fluido è reale.",
    "internal_energy_J_kg": "Riferita allo stato di riferimento della correlazione, non a uno zero assoluto.",
    "enthalpy_J_kg": "u + Pv. Le differenze fra due stati sono significative; il valore assoluto dipende dal riferimento.",
    "entropy_J_kg_K": "Anch'essa riferita allo stato di riferimento della correlazione.",
    "dew_point_pressure_Pa": "La pressione alla quale, a questa temperatura, il vapore comincia a condensare.",
    "bubble_point_pressure_Pa": "La pressione alla quale, a questa temperatura, il liquido comincia a bollire.",
    "dew_point_density_kg_m3": "Densità del vapore saturo: il ramo dilatato della curva di saturazione.",
    "bubble_point_density_kg_m3": "Densità del liquido saturo: il ramo denso della curva di saturazione.",
}

UNIT_KINDS = (
    {"kind": "density", "symbols": "ρ", "name": "densità"},
    {"kind": "specific_energy", "symbols": "u, h", "name": "energia interna ed entalpia"},
    {"kind": "specific_entropy", "symbols": "s", "name": "entropia"},
    {"kind": "pressure", "symbols": "P", "name": "pressioni di rugiada e bolla"},
)

SCAN_STATUS = {
    "two-phase": "bifase",
    "out-of-range": "fuori range",
    "extrapolated": "estrapolazione",
}


def _one_of(value, allowed, default):
    try:
        return value if value in allowed else default
    except TypeError:
        return default


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except (OverflowError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _clean_pin(pinned):
    if not isinstance(pinned, dict):
        return {}
    values = pinned.get("values")
    values = values if isinstance(values, dict) else {}
    return {
        "temperature_K": _number(pinned.get("temperature_K")),
        "pressure_Pa": _number(pinned.get("pressure_Pa")),
        "phase": _one_of(pinned.get("phase"), backend_bridge.PHASE_LABELS, None),
        "phase_label": backend_bridge.PHASE_LABELS.get(
            _one_of(pinned.get("phase"), backend_bridge.PHASE_LABELS, None), "—"),
        "extrapolated": bool(pinned.get("extrapolated")),
        "values": {p["key"]: _number(values.get(p["key"]))
                   for p in backend_bridge.PROPERTIES},
    }


def _named_dropdown(dropdown, name):
    return html.Div(
        className="named-control",
        children=[html.Span(name, className="visually-hidden control-name"), dropdown],
    )


def _number_input(input_id, value, step, label_text, unit_kind, unit_value):
    return html.Div(
        className="field",
        children=[
            html.Label(label_text, htmlFor=input_id, className="field-label",
                       id=f"{input_id}-label"),
            html.Div(
                className="field-row",
                children=[
                    dcc.Input(
                        id=input_id, type="number", value=value, step=step,
                        debounce=False, className="field-input",
                    ),
                    _named_dropdown(
                        dcc.Dropdown(
                            id=f"{input_id}-unit", options=units.options(unit_kind),
                            value=unit_value, clearable=False, searchable=False,
                            className="field-unit",
                        ),
                        f"Unità di misura per {label_text.lower()}",
                    ),
                ],
            ),
        ],
    )


def _data_row(prop, unit_kind, second=False):
    key = prop["key"]
    note = PROPERTY_NOTES.get(key)
    symbol = html.Span(prop["symbol"], className="row-symbol")
    name = html.Span(prop["name"], className="row-name")
    return html.Tr(
        className="data-row", id=f"row-{key}", role="row",
        children=[
            html.Th(
                className="row-head", scope="row", role="rowheader",
                children=[symbol, name] if not note else [
                    symbol,
                    html.Details(
                        className="row-note",
                        children=[
                            html.Summary(name, className="row-name"),
                            html.P(note, className="row-note-body"),
                        ],
                    ),
                ],
            ),
            html.Td(
                className="row-value", id=f"val-{key}", role="cell",
                children=_value_cell(None),
            ),
            html.Td(
                className="row-value row-value-second", id=f"val2-{key}", role="cell",
                children=_value_cell(None),
            ) if second else None,
            html.Td(
                className="row-unit", role="cell",
                children=html.Span(
                    id=f"unit-label-{key}", className="row-unit-fixed",
                    children="—" if unit_kind == "dimensionless"
                    else units.label(unit_kind, units.DEFAULTS[unit_kind]),
                ),
            ),
        ],
    )


def _unit_bar():
    return html.Div(
        className="unit-bar",
        children=[html.Span("Unità", className="unit-bar-label")] + [
            html.Div(
                className="unit-pick",
                children=[
                    html.Span(spec["symbols"], className="unit-pick-symbol",
                              **{"aria-hidden": "true"}),
                    _named_dropdown(
                        dcc.Dropdown(
                            id=f"unit-{spec['kind']}", options=units.options(spec["kind"]),
                            value=units.DEFAULTS[spec["kind"]], clearable=False,
                            searchable=False, className="unit-pick-select",
                        ),
                        f"Unità di misura per {spec['name']}",
                    ),
                ],
            ) for spec in UNIT_KINDS
        ],
    )


def _data_table(properties, caption, second=False, head=None):
    body = html.Tbody(
        role="rowgroup",
        children=[_data_row(p, p["kind"], second=second) for p in properties],
    )
    return html.Table(
        className="data-grid", role="table",
        children=[html.Caption(caption, className="visually-hidden")]
                 + ([html.Thead(head, role="rowgroup")] if head is not None else [])
                 + [body],
    )


def _value_cell(value, decimals=None):
    if decimals is None:
        decimals = fmt.significant_decimals(value)
    p = fmt.parts(value, decimals)
    fraction = ([html.Span(".", className="v-dot"), p["fraction"]] if p["fraction"] else [])
    return [
        html.Span(p["integer"], className="v-int"),
        html.Span(fraction, className="v-frac" + ("" if p["fraction"] else " is-empty")),
        html.Span(p["exponent"], className="v-exp"),
    ]


def serve_layout():
    fluid = backend_bridge.DEFAULT_FLUID
    mode = "tp"
    t_unit = units.DEFAULTS["temperature"]
    p_unit = units.DEFAULTS["pressure"]

    def num(_key, fallback):
        return fallback

    lim = backend_bridge.limits(fluid)
    t_default = units.from_si("temperature", t_unit, 300.0)
    p_default = units.from_si("pressure", p_unit, 101325.0)

    return html.Div(
        className="sheet",
        children=[
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="base-key"),
            dcc.Store(id="restored", data=False),
            dcc.Store(id="table-csv"),
            dcc.Store(id="table-tsv"),
            dcc.Store(id="input-units",
                      data={"t": units.DEFAULTS["temperature"],
                            "p": units.DEFAULTS["pressure"]}),
            dcc.Store(id="url-query"),
            dcc.Store(id="url-sink"),
            dcc.Download(id="csv-download"),
            dcc.Store(id="current-state"),
            dcc.Store(id="pinned"),
            dcc.Store(id="scan-tsv"),
            dcc.Store(id="scan-csv"),
            dcc.Store(id="announce"),
            dcc.Store(id="announce-sink"),
            dcc.Store(id="invalid-field"),
            dcc.Store(id="invalid-sink"),
            dcc.Input(id="scan-request", type="text", value="",
                      className="offscreen-input"),
            dcc.Interval(id="copy-reset", interval=1600, disabled=True),

            html.Header(
                className="masthead",
                children=[
                    html.H1("CryoCalculator", className="wordmark"),
                    html.Div(
                        className="masthead-model", id="masthead-model",
                        children=_model_line(lim),
                    ),
                ],
            ),

            html.Main(
                className="plate",
                children=[
                    html.Div(
                        className="chart-frame",
                        children=[
                            html.Figure(
                                className="chart", role="group",
                                **{"aria-labelledby": "chart-caption"},
                                children=[
                                    dcc.Graph(
                                        id="chart",
                                        responsive=True,
                                        style={"width": "100%", "height": "100%"},
                                        config={
                                            "displayModeBar": False,
                                            "scrollZoom": False,
                                            "doubleClick": False,
                                            "responsive": True,
                                        },
                                    ),
                                    html.Figcaption(
                                        id="chart-caption", className="visually-hidden",
                                        children=_chart_caption(None, None, None,
                                                                units.DEFAULTS["temperature"],
                                                                units.DEFAULTS["pressure"]),
                                    ),
                                ],
                            ),
                            html.Section(
                                className="titleblock", **{"aria-label": "Ingressi di stato"},
                                children=[
                                    html.Div(
                                        className="titleblock-head",
                                        children=[
                                            html.Fieldset(
                                                className="seg-group",
                                                children=[
                                                    html.Legend("Fluido",
                                                                className="visually-hidden"),
                                                    dcc.RadioItems(
                                                        id="fluid", value=fluid,
                                                        options=[
                                                            {"label": backend_bridge.FLUIDS[k]["label"], "value": k}
                                                            for k in backend_bridge.FLUIDS
                                                        ],
                                                        className="seg", inline=True,
                                                    ),
                                                ],
                                            ),
                                            html.Fieldset(
                                                className="seg-group",
                                                children=[
                                                    html.Legend("Grandezze in ingresso",
                                                                className="visually-hidden"),
                                                    dcc.RadioItems(
                                                        id="mode", value=mode,
                                                        options=[
                                                            {"label": "T, P", "value": "tp"},
                                                            {"label": "T, ρ", "value": "trho"},
                                                        ],
                                                        className="seg seg-mode", inline=True,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="titleblock-fields",
                                        children=[
                                            _number_input(
                                                "in-t", num("t", t_default), "any",
                                                "Temperatura", "temperature", t_unit,
                                            ),
                                            _number_input(
                                                "in-p", num("p", p_default), "any",
                                                "Pressione", "pressure", p_unit,
                                            ),
                                        ],
                                    ),
                                    html.P(id="range-note", className="range-note",
                                           children=_range_text(lim, t_unit, p_unit)),
                                    html.P(id="mode-note", className="range-note is-note",
                                           role="status", **{"aria-live": "polite"}),
                                    html.Div(id="status", className="status"),
                                ],
                            ),
                        ],
                    ),

                    html.Section(
                        id="datablock", className="datablock",
                        **{"aria-label": "Stato termodinamico"},
                        children=[
                            html.Div(
                                className="datablock-head",
                                children=[
                                    html.Div(
                                        className="datablock-identity",
                                        children=[
                                            html.H2("Stato", className="datablock-title"),
                                            html.Div(id="phase-badge",
                                                     className="phase-badge",
                                                     children=_phase_chip(None)),
                                        ],
                                    ),
                                    html.Div(
                                        className="datablock-actions",
                                        children=[
                                            html.Button(
                                                "COPIA", id="copy-button", n_clicks=0,
                                                className="action action-text",
                                                **{"aria-label": "Copia la tabella di stato negli appunti"},
                                                title="Copia la tabella di stato negli appunti",
                                            ),
                                            html.Button(
                                                "CSV", id="csv-button", n_clicks=0,
                                                className="action action-text",
                                                title="Scarica la tabella di stato in formato CSV",
                                                **{"aria-label": "Scarica la tabella di stato in formato CSV"},
                                            ),
                                            html.Button(
                                                "SVG", id="svg-button", n_clicks=0,
                                                className="action action-text",
                                                title="Scarica la carta termodinamica in formato SVG",
                                                **{"aria-label": "Scarica la carta termodinamica in formato SVG"},
                                            ),
                                            html.Button(
                                                "FISSA", id="pin-button", n_clicks=0,
                                                className="action action-text",
                                                title="Fissa questo stato per confrontarlo",
                                                **{"aria-label": "Fissa questo stato per confrontarlo con il prossimo"},
                                            ),
                                            html.Button(
                                                "SGANCIA", id="unpin-button", n_clicks=0,
                                                className="action action-text is-hidden",
                                                title="Togli lo stato fissato",
                                                **{"aria-label": "Togli lo stato fissato dal confronto"},
                                            ),
                                            html.Div(id="copy-status", className="visually-hidden",
                                                     role="status", **{"aria-live": "polite"}),
                                        ],
                                    ),
                                ],
                            ),
                            _unit_bar(),
                            html.P(id="dome-note", className="dome-note"),
                            _data_table(
                                backend_bridge.PROPERTIES, second=True,
                                caption="Proprietà di stato del fluido alle condizioni richieste.",
                                head=html.Tr(id="dome-head", className="dome-head", role="row"),
                            ),
                            html.Div(
                                id="sat-section",
                                children=[
                                    html.H2("Saturazione a questa temperatura",
                                            className="datablock-title sub"),
                                    html.P(id="sat-note", className="range-note"),
                                    _data_table(
                                        backend_bridge.SATURATION_PROPERTIES,
                                        caption="Rugiada e bolla alla temperatura richiesta.",
                                    ),
                                ],
                            ),
                            html.Div(
                                id="scan-section", style={"display": "none"},
                                children=[
                                    html.Div(
                                        className="datablock-head is-sub",
                                        children=[
                                            html.Div(
                                                className="datablock-identity",
                                                children=[
                                                    html.H2("Scansione", id="scan-title",
                                                            className="datablock-title sub"),
                                                ],
                                            ),
                                            html.Div(
                                                className="datablock-actions",
                                                children=[
                                                    html.Button(
                                                        "COPIA", id="scan-copy-button", n_clicks=0,
                                                        className="action action-text",
                                                        title="Copia la scansione negli appunti",
                                                        **{"aria-label": "Copia la tabella di scansione negli appunti"},
                                                    ),
                                                    html.Button(
                                                        "CSV", id="scan-csv-button", n_clicks=0,
                                                        className="action action-text",
                                                        title="Scarica la scansione in formato CSV",
                                                        **{"aria-label": "Scarica la tabella di scansione in formato CSV"},
                                                    ),
                                                    html.Button(
                                                        "CHIUDI", id="scan-clear-button", n_clicks=0,
                                                        className="action action-text",
                                                        title="Chiudi la scansione",
                                                        **{"aria-label": "Chiudi la tabella di scansione"},
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    html.P(id="scan-note", className="range-note"),
                                    html.Div(className="scan-scroll",
                                             children=html.Table(id="scan-table",
                                                                 className="scan-grid",
                                                                 role="table")),
                                ],
                            ),
                        ],
                    ),
                ],
            ),

            html.Div(id="live-announce", className="visually-hidden",
                     role="status", **{"aria-live": "polite"}),

            html.Footer(
                className="colophon",
                children=[
                    html.P([
                        "Ogni valore viene dall'equazione di stato di Helmholtz in forma ridotta, "
                        "risolta simbolicamente. Nessun valore è tabulato o interpolato."
                    ]),
                    html.P(id="colophon-ref", children=_reference_text(lim)),
                ],
            ),
        ],
    )


def _model_line(lim):
    formula = [html.Sub(text) if is_sub else text for text, is_sub in lim["formula"]]
    return [
        html.Span(formula, className="model-formula"),
        html.Span(lim["reference"], className="model-ref"),
    ]


def _reference_text(lim):
    return [html.Span(lim["reference"] + " — "), html.Em(lim["reference_detail"])]


def _range_text(lim, t_unit, p_unit):
    def show(kind, value):
        return fmt.plain(units.from_si(kind, p_unit if kind == "pressure" else t_unit,
                                       value), 1)

    return (f"Validità: da {show('temperature', lim['t_min_K'])} a "
            f"{show('temperature', lim['t_max_K'])} {units.label('temperature', t_unit)}, "
            f"da {show('pressure', max(lim['p_min_Pa'], 1.0))} a "
            f"{show('pressure', lim['p_max_Pa'])} {units.label('pressure', p_unit)}.")


def _phase_chip(phase):
    label = backend_bridge.PHASE_LABELS.get(phase, "—")
    return html.Span(label, className="chip", **{"data-phase": phase or "none"})


def _chart_caption(lim, state, phase, t_unit, p_unit, scan=None):
    label = (lim or {}).get("label", "fluido selezionato").lower()
    lines = [
        f"Carta pressione-temperatura per {label}: regioni di fase — vapore, liquido, gas, "
        f"supercritico e solido — curva di saturazione, curva di fusione e famiglia di "
        f"isocore. Asse della temperatura logaritmico in kelvin, asse della pressione "
        f"logaritmico."
    ]

    if phase == "two-phase":
        lines.append("Lo stato richiesto cade nella regione bifase: a questa temperatura "
                     "la pressione non individua un solo stato, e la tabella riporta il "
                     "liquido saturo e il vapore saturo affiancati.")
    elif state:
        t = fmt.plain(units.from_si("temperature", t_unit, state.get("temperature_K")), 3)
        p = fmt.plain(units.from_si("pressure", p_unit, state.get("pressure_Pa")), 3)
        name = backend_bridge.PHASE_LABELS.get(phase, "non determinata").lower()
        lines.append(f"Stato corrente: {t} {units.label('temperature', t_unit)}, "
                     f"{p} {units.label('pressure', p_unit)}, fase {name}.")
    else:
        lines.append("Nessuno stato risolto al momento.")

    if scan and scan.get("rows"):
        rows = scan["rows"]
        kind = "isoterma" if scan["axis"] == "isotherm" else "isobara"
        lines.append(f"Sul piano è tracciata una {kind} di {len(rows)} punti; "
                     f"i valori sono nella sezione Scansione.")

    lines.append("Il piano si può usare da tastiera: portandovi il fuoco, le frecce "
                 "spostano lo stato lungo i due assi e Maiusc allarga il passo. I tasti "
                 "I e B tracciano rispettivamente un'isoterma e un'isobara passanti per "
                 "lo stato corrente; con il mouse, lo stesso si ottiene trascinando sul "
                 "piano. Gli stessi valori si possono digitare nei campi Temperatura e "
                 "Pressione. I valori numerici completi sono nella sezione Stato "
                 "termodinamico.")
    return " ".join(lines)

app.layout = serve_layout


@app.callback(
    Output("in-p-label", "children"),
    Output("in-p-unit", "options"),
    Output("in-p-unit", "value"),
    Output("in-p", "value"),
    Output("mode-note", "children"),
    Input("mode", "value"),
    State("in-p-unit", "value"), State("in-p", "value"),
    State("in-t", "value"), State("in-t-unit", "value"),
    State("fluid", "value"),
    prevent_initial_call=True,
)
def sync_second_field(mode, current_unit, second_raw, t_raw, t_unit, fluid):
    fluid = _one_of(fluid, backend_bridge.FLUIDS, backend_bridge.DEFAULT_FLUID)
    mode = _one_of(mode, ("tp", "trho"), "tp")
    t_raw, second_raw = _number(t_raw), _number(second_raw)

    kind = "density" if mode == "trho" else "pressure"
    label = "Densità" if kind == "density" else "Pressione"
    options = units.options(kind)
    unit = _one_of(current_unit, units.UNITS[kind]["options"], units.DEFAULTS[kind])

    previous_kind = "pressure" if kind == "density" else "density"
    t_unit = _one_of(t_unit, units.UNITS["temperature"]["options"],
                     units.DEFAULTS["temperature"])
    t_si = units.to_si("temperature", t_unit, t_raw)
    previous_unit = _one_of(current_unit, units.UNITS[previous_kind]["options"], None)
    old_si = units.to_si(previous_kind, previous_unit, second_raw) if previous_unit else None

    if old_si is None:
        return label, options, unit, dash.no_update, ""

    if t_si is None:
        return label, options, unit, dash.no_update, ""

    try:
        state = backend_bridge.state(
            fluid or backend_bridge.DEFAULT_FLUID, t_si,
            p_Pa=old_si if previous_kind == "pressure" else None,
            rho_kg_m3=old_si if previous_kind == "density" else None,
        )
        carried = state.get("density_kg_m3" if kind == "density" else "pressure_Pa")
    except backend_bridge.TwoPhaseState:
        return (label, options, unit, None,
                "Dentro la campana una pressione non individua una densità: "
                "scegli quale dei due stati saturi vuoi leggere.")
    except backend_bridge.DomainError:
        carried = None

    if carried is None:
        return (label, options, unit, None,
                "Lo stato precedente non si converte in questa grandezza: inserisci un valore.")

    converted = units.from_si(kind, unit, carried)
    return label, options, unit, round(converted, 6), ""


@app.callback(
    Output("in-t", "value", allow_duplicate=True),
    Output("in-p", "value", allow_duplicate=True),
    Output("input-units", "data"),
    Input("in-t-unit", "value"), Input("in-p-unit", "value"),
    State("in-t", "value"), State("in-p", "value"),
    State("input-units", "data"), State("mode", "value"),
    prevent_initial_call=True,
)
def convert_on_unit_change(t_unit, p_unit, t_raw, p_raw, memory, mode):
    memory = memory if isinstance(memory, dict) else {}
    mode = _one_of(mode, ("tp", "trho"), "tp")
    second_kind = "density" if mode == "trho" else "pressure"
    t_raw, p_raw = _number(t_raw), _number(p_raw)

    def convert(kind, value, was, now):
        if value is None or was is None or was == now:
            return dash.no_update
        if _one_of(was, units.UNITS[kind]["options"], None) is None:
            return dash.no_update
        si = units.to_si(kind, was, value)
        return round(units.from_si(kind, now, si), 6) if si is not None else dash.no_update

    return (
        convert("temperature", t_raw, memory.get("t"), t_unit),
        convert(second_kind, p_raw, memory.get("p"), p_unit),
        {"t": _one_of(t_unit, units.UNITS["temperature"]["options"],
                      units.DEFAULTS["temperature"]),
         "p": _one_of(p_unit, units.UNITS[second_kind]["options"],
                      units.DEFAULTS[second_kind])},
    )


@app.callback(
    Output("fluid", "value"), Output("mode", "value"),
    Output("in-t", "value"), Output("in-p", "value"),
    Output("in-t-unit", "value"),
    Output("in-p-unit", "value", allow_duplicate=True),
    Output("restored", "data"),
    Input("url", "search"),
    State("restored", "data"),
    prevent_initial_call="initial_duplicate",
)
def restore_from_url(search, restored):
    if restored:
        raise dash.exceptions.PreventUpdate
    if not search:
        return (dash.no_update,) * 6 + (True,)

    if not isinstance(search, str):
        raise dash.exceptions.PreventUpdate
    args = urllib.parse.parse_qs(search.lstrip("?"))

    def one(key):
        got = args.get(key)
        return got[0] if got else None

    def number(key):
        try:
            return float(one(key))
        except (TypeError, ValueError):
            return dash.no_update

    fluid = one("fluid")
    mode = one("mode")
    t_unit = one("tu")
    p_unit = one("pu")
    second_kind = "density" if mode == "trho" else "pressure"

    return (
        fluid if fluid in backend_bridge.FLUIDS else dash.no_update,
        mode if mode in ("tp", "trho") else dash.no_update,
        number("t"), number("p"),
        t_unit if t_unit in units.UNITS["temperature"]["options"] else dash.no_update,
        p_unit if p_unit in units.UNITS[second_kind]["options"] else units.DEFAULTS[second_kind],
        True,
    )

app.clientside_callback(
    """
    function (query) {
        if (typeof query === "string" && window.history && window.history.replaceState) {
            window.history.replaceState(
                window.history.state, "", query || window.location.pathname);
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("url-sink", "data"),
    Input("url-query", "data"),
    prevent_initial_call=True,
)

ALL_PROPERTIES = backend_bridge.PROPERTIES + backend_bridge.SATURATION_PROPERTIES

VALUE_OUTPUTS = [Output(f"val-{p['key']}", "children") for p in ALL_PROPERTIES]

VALUE2_OUTPUTS = [Output(f"val2-{p['key']}", "children")
                  for p in backend_bridge.PROPERTIES]

UNIT_LABEL_OUTPUTS = [Output(f"unit-label-{p['key']}", "children") for p in ALL_PROPERTIES]


@app.callback(
    [Output("chart", "figure"), Output("base-key", "data"),
     Output("status", "children"), Output("phase-badge", "children"),
     Output("masthead-model", "children"), Output("range-note", "children"),
     Output("sat-note", "children"),
     Output("colophon-ref", "children"), Output("url-query", "data"),
     Output("datablock", "className"), Output("dome-head", "children"),
     Output("dome-note", "children"), Output("sat-section", "style"),
     Output("table-tsv", "data"), Output("table-csv", "data"),
     Output("announce", "data"), Output("chart-caption", "children"),
     Output("current-state", "data"), Output("invalid-field", "data"),
     Output("scan-section", "style"), Output("scan-title", "children"),
     Output("scan-note", "children"), Output("scan-table", "children"),
     Output("scan-tsv", "data"), Output("scan-csv", "data"),
     Output("unpin-button", "className")]
    + VALUE_OUTPUTS + VALUE2_OUTPUTS + UNIT_LABEL_OUTPUTS,
    Input("fluid", "value"), Input("mode", "value"),
    Input("in-t", "value"), Input("in-p", "value"),
    Input("in-t-unit", "value"), Input("in-p-unit", "value"),
    Input("unit-density", "value"), Input("unit-specific_energy", "value"),
    Input("unit-specific_entropy", "value"), Input("unit-pressure", "value"),
    Input("scan-request", "value"), Input("pinned", "data"),
    State("base-key", "data"),
)
def recompute(fluid, mode, t_raw, second_raw, t_unit, second_unit,
              u_density, u_energy, u_entropy, u_pressure,
              scan_raw, pinned, base_key_prev):
    fluid = _one_of(fluid, backend_bridge.FLUIDS, backend_bridge.DEFAULT_FLUID)
    mode = _one_of(mode, ("tp", "trho"), "tp")
    second_kind = "density" if mode == "trho" else "pressure"

    display = {
        kind: _one_of(chosen, units.UNITS[kind]["options"], units.DEFAULTS[kind])
        for kind, chosen in (
            ("density", u_density),
            ("specific_energy", u_energy),
            ("specific_entropy", u_entropy),
            ("pressure", u_pressure),
        )
    }
    display["dimensionless"] = "—"

    t_unit = _one_of(t_unit, units.UNITS["temperature"]["options"],
                     units.DEFAULTS["temperature"])
    second_unit = _one_of(second_unit, units.UNITS[second_kind]["options"],
                          units.DEFAULTS[second_kind])
    t_raw = _number(t_raw)
    second_raw = _number(second_raw)
    pinned = _clean_pin(pinned)
    p_unit = second_unit if mode == "tp" else display["pressure"]

    lim = backend_bridge.limits(fluid)

    t_si = units.to_si("temperature", t_unit, t_raw) if t_raw is not None else None
    second_si = units.to_si(second_kind, second_unit, second_raw) if second_raw is not None else None

    state = None
    pair = {}
    two_phase = None
    phase = None
    status = []
    invalid = None
    if t_si is None or second_si is None:
        status = [html.Span("In attesa di un valore.", className="status-wait")]
    else:
        try:
            state = backend_bridge.state(
                fluid, t_si,
                p_Pa=second_si if mode == "tp" else None,
                rho_kg_m3=second_si if mode == "trho" else None,
            )
            phase = state["phase"]
        except backend_bridge.TwoPhaseState as exc:
            pair = exc.pair or {}
            phase = "two-phase"
            two_phase = exc
        except backend_bridge.DomainError as exc:
            status = [html.Span(
                _domain_message(exc, lim, t_unit, second_kind, second_unit),
                className="status-error")]
            quantity = getattr(exc, "quantity", None)
            invalid = ("in-t" if quantity == "temperature"
                       else "in-p" if quantity == second_kind else None)

    if state and not status:
        notes = []
        if state.get("extrapolated"):
            notes.append(html.Span(_extrapolation_note(state, lim, p_unit),
                                   className="status-error"))
        if state.get("pressure_is_derived"):
            notes.append(html.Span("Pressione ricavata dallo stato, non imposta.",
                                   className="status-note"))
        status = notes

    marker = state
    if marker is None and t_si is not None and mode == "tp" and second_si:
        marker = {"temperature_K": t_si, "pressure_Pa": second_si,
                  "unresolved": True, "phase": phase}

    dome = None
    if two_phase is not None and t_si is not None:
        dome = {"temperature_K": t_si,
                "dew_Pa": two_phase.dew_pressure_Pa,
                "bubble_Pa": two_phase.bubble_pressure_Pa}

    scan = _resolve_scan(scan_raw, fluid)

    floor = chart.view_floor(fluid, (marker or {}).get("pressure_Pa"))

    base_key = f"{fluid}|{t_unit}|{p_unit}|{floor:g}|{'dome' if two_phase else 'open'}"
    previous = base_key_prev if isinstance(base_key_prev, dict) else {}
    previous_traces = previous.get("traces")
    if not isinstance(previous_traces, int) or isinstance(previous_traces, bool):
        previous_traces = None
    if previous.get("key") == base_key and previous_traces:
        figure = Patch()
        total = previous_traces
        for offset, (tx, ty) in enumerate(chart.state_traces(marker, dome, p_unit, scan)):
            index = total - chart.MARKER_TRACES + offset
            figure["data"][index]["x"] = tx
            figure["data"][index]["y"] = ty
        base_key = previous
    else:
        built = chart.build(fluid, t_unit, p_unit, marker=marker, dome=dome, scan=scan)
        figure = built
        base_key = {"key": base_key, "traces": len(built.data)}

    liquid = pair.get("liquid") or {}
    vapor = pair.get("vapor") or {}
    in_dome = bool(pair)
    pin = (pinned or {}) if not in_dome else {}
    pinned_values = pin.get("values") or {}
    second_column = in_dome or bool(pinned_values)

    values, values2, unit_labels, export_rows = [], [], [], []
    for prop in ALL_PROPERTIES:
        kind = prop["kind"]
        unit = display[kind]
        unit_labels.append("—" if kind == "dimensionless" else units.label(kind, unit))
        primary = (liquid if in_dome else (state or {})).get(prop["key"])
        primary_display = units.from_si(kind, unit, primary)
        decimals = fmt.significant_decimals(primary_display)
        values.append(_value_cell(primary_display, decimals))

        secondary_display = None
        if prop in backend_bridge.PROPERTIES:
            if in_dome:
                secondary = vapor.get(prop["key"])
            else:
                secondary = pinned_values.get(prop["key"])
            secondary_display = units.from_si(kind, unit, secondary)
            values2.append(_value_cell(secondary_display))

        if in_dome and prop not in backend_bridge.PROPERTIES:
            continue

        row = [prop["symbol"], prop["name"], primary_display]
        if second_column:
            row.append(secondary_display)
        row.append(units.label(kind, unit))
        export_rows.append(row)

    query = urllib.parse.urlencode({
        "fluid": fluid, "mode": mode, "tu": t_unit, "pu": second_unit,
        **({"t": f"{t_raw:g}"} if isinstance(t_raw, (int, float)) else {}),
        **({"p": f"{second_raw:g}"} if isinstance(second_raw, (int, float)) else {}),
    })
    address = "?" + query if dash.callback_context.triggered_id else dash.no_update

    block_class = "datablock"
    if in_dome:
        block_class = "datablock has-second is-dome"
    elif pinned_values:
        block_class = "datablock has-second is-pinned"

    scan_shown = bool(scan and scan.get("rows"))

    return [figure, base_key, status,
            _phase_chip(phase),
            _model_line(lim), _range_text(lim, t_unit, second_unit if mode == "tp" else p_unit),
            _sat_note(lim, t_si, t_unit),
            _reference_text(lim), address,
            block_class,
            _dome_head(liquid, vapor, p_unit) if in_dome
            else (_pin_head(pin, state, t_unit, display["pressure"]) if pinned_values else []),
            _dome_note(two_phase, lim, second_si, p_unit, mode) if in_dome else "",
            {"display": "none"} if in_dome else {},
            _export_text(lim, export_rows, in_dome, liquid, vapor,
                         t_raw, t_unit, second_raw, second_unit, mode, "\t", ".",
                         pin if pinned_values else None, t_unit, display["pressure"]),
            _export_text(lim, export_rows, in_dome, liquid, vapor,
                         t_raw, t_unit, second_raw, second_unit, mode, ";", ",",
                         pin if pinned_values else None, t_unit, display["pressure"]),
            _announcement(state, pair, status, display["density"]),
            _chart_caption(lim, state, phase, t_unit, p_unit, scan),
            _pinnable(state, phase), invalid,
            {} if scan_shown else {"display": "none"},
            _scan_title(scan), _scan_note(scan, lim, t_unit, display["pressure"]),
            _scan_rows(scan, display, t_unit, display["pressure"]),
            _scan_export(scan, lim, display, t_unit, display["pressure"], "\t", "."),
            _scan_export(scan, lim, display, t_unit, display["pressure"], ";", ","),
            "action action-text" if pinned_values else "action action-text is-hidden",
            ] + values + values2 + unit_labels


def _pinnable(state, phase):
    if not state or phase == "two-phase":
        return None
    return {
        "temperature_K": state.get("temperature_K"),
        "pressure_Pa": state.get("pressure_Pa"),
        "phase": state.get("phase"),
        "phase_label": state.get("phase_label"),
        "extrapolated": bool(state.get("extrapolated")),
        "values": {p["key"]: state.get(p["key"]) for p in backend_bridge.PROPERTIES},
    }


def _announcement(state, pair, status, density_unit):
    refusal = " ".join(
        node.children for node in status
        if getattr(node, "className", "") == "status-error"
        and isinstance(getattr(node, "children", None), str)
    )
    if refusal:
        return refusal
    if pair:
        return ("Bifase: liquido e vapore coesistono. "
                "Due colonne, liquido saturo e vapore saturo.")
    if not state:
        return ""
    value = units.from_si("density", density_unit, state.get("density_kg_m3"))
    return (f"{state.get('phase_label', '')}. "
            f"Densità {fmt.plain(value, fmt.significant_decimals(value))} "
            f"{units.label('density', density_unit)}.")


def _extrapolation_note(state, lim, p_unit):
    p_melt = state.get("melting_pressure_Pa")
    where = ""
    if p_melt:
        shown = fmt.plain(units.from_si("pressure", p_unit, p_melt), 4)
        where = f", che a questa temperatura cade a {shown} {units.label('pressure', p_unit)},"
    return (f"Sopra la curva di fusione{where} il fluido è solido. L'equazione di stato per "
            f"{lim['label'].lower()} non descrive la fase solida: i valori qui sotto sono "
            f"l'estrapolazione del ramo liquido, non proprietà del solido.")

_QUANTITY_ARTICLE = {"temperature": "La temperatura",
                     "pressure": "La pressione",
                     "density": "La densità"}


def _domain_message(exc, lim, t_unit, second_kind, second_unit):
    kind = getattr(exc, "quantity", None)
    if kind == "temperature":
        unit = t_unit
    elif kind is not None and kind == second_kind:
        unit = second_unit
    else:
        return str(exc)

    label = units.label(kind, unit)

    def show(si):
        if si is None or not isinstance(si, (int, float)) or not math.isfinite(si):
            return None
        value = units.from_si(kind, unit, si)
        p = fmt.parts(value, fmt.significant_decimals(value))
        if p["absent"]:
            return None
        fraction = p["fraction"].rstrip("0")
        return p["integer"] + (f".{fraction}" if fraction else "") + p["exponent"]

    low, high, value = show(exc.low), show(exc.high), show(exc.value)
    if value is None:
        return str(exc)
    asked = f"Hai chiesto {value} {label}."

    if kind == "temperature" and low is not None and high is not None:
        return (f"L'equazione di stato per {lim['label'].lower()} copre da {low} a "
                f"{high} {label}. {asked}")

    exclusive = getattr(exc, "bound", "inclusive") == "above-low"
    name = _QUANTITY_ARTICLE.get(kind, "Il valore")
    if exclusive and high is not None:
        return (f"{name} deve essere maggiore di {low} e non superare "
                f"{high} {label}. {asked}")
    if exclusive and low is not None:
        return f"{name} deve essere maggiore di {low} {label}. {asked}"
    if low is not None and high is not None:
        return f"{name} deve stare fra {low} e {high} {label}. {asked}"
    return str(exc)


def _export_text(lim, rows, in_dome, liquid, vapor,
                 t_raw, t_unit, second_raw, second_unit, mode, sep, decimal,
                 pin=None, pin_t_unit=None, pin_p_unit=None):
    if not rows:
        return ""

    def cell(value):
        if value is None or isinstance(value, (int, float)):
            text = fmt.export(value, decimal)
        else:
            text = str(value)
        if sep in text or '"' in text or "\n" in text:
            return '"' + text.replace('"', '""') + '"'
        return text

    def line(cells):
        return sep.join(cell(c) for c in cells)

    second_label = "Densità" if mode == "trho" else "Pressione"
    out = [
        line(["CryoCalculator", lim["label"]]),
        line(["Modello", lim["reference"]]),
        line(["Validità", f"{lim['t_min_K']:g}–{lim['t_max_K']:g} K",
              f"≤ {lim['p_max_Pa'] / 1e6:g} MPa"]),
        line(["Temperatura", t_raw,
              units.label("temperature", t_unit)]),
        line([second_label, second_raw,
              units.label("density" if mode == "trho" else "pressure", second_unit)]),
        "",
    ]

    if in_dome:
        out.append(line(["Stato", "bifase: liquido e vapore coesistono"]))
        out.append(line(["Titolo di vapore", "non determinato da (T, P)"]))
        out.append(line(["Simbolo", "Grandezza", "Liquido saturo", "Vapore saturo", "Unità"]))
    elif pin:
        pinned_t = units.from_si("temperature", pin_t_unit, pin.get("temperature_K"))
        pinned_p = units.from_si("pressure", pin_p_unit, pin.get("pressure_Pa"))
        out.append(line(["Stato fissato", pinned_t, units.label("temperature", pin_t_unit),
                         pinned_p, units.label("pressure", pin_p_unit)]))
        out.append(line(["Simbolo", "Grandezza", "Corrente", "Fissato", "Unità"]))
    else:
        out.append(line(["Simbolo", "Grandezza", "Valore", "Unità"]))

    out.extend(line(r) for r in rows)
    return "\n".join(out)


def _dome_head(liquid, vapor, p_unit):
    unit = units.label("pressure", p_unit)

    def column(entry, css, key):
        pressure = units.from_si("pressure", p_unit, entry.get("pressure_Pa"))
        label = entry.get("phase_label", "—")
        rho = entry.get("density_kg_m3")
        described = (f"Leggi lo stato del {label.lower()} come stato unico, "
                     f"a densità {fmt.plain(rho, 6)} kg/m³") if rho else \
                    f"Leggi lo stato del {label.lower()} come stato unico"
        return html.Th(
            className=f"dome-col {css}", scope="col", role="columnheader",
            children=html.Button(
                id=f"pick-{key}", n_clicks=0, className="dome-pick",
                **{"aria-label": described}, title=described,
                children=[
                    html.Span(label, className="dome-col-name"),
                    html.Span(f"{fmt.plain(pressure, 4)} {unit}", className="dome-col-pressure"),
                ],
            ),
        )

    def spacer(name):
        return html.Th("", scope="col", className="dome-col-spacer",
                       role="columnheader", **{"aria-label": name})

    return [
        spacer("Grandezza"),
        column(liquid, "is-liquid", "liquid"),
        column(vapor, "is-vapor", "vapor"),
        spacer("Unità"),
    ]


def _dome_note(exc, lim, requested_p_Pa, p_unit, mode):
    unit = units.label("pressure", p_unit)
    dew = fmt.plain(units.from_si("pressure", p_unit, exc.dew_pressure_Pa), 4) if exc else "—"
    bub = fmt.plain(units.from_si("pressure", p_unit, exc.bubble_pressure_Pa), 4) if exc else "—"

    lead = html.Span("Liquido e vapore coesistono.", className="dome-flag")

    if lim["mixture"]:
        body = (f"L'aria è una miscela, quindi rugiada e bolla cadono a pressioni diverse: "
                f"{dew} e {bub} {unit}. Nessuna delle due colonne sta alla pressione che hai "
                f"chiesto, e la coppia (T, P) non fissa quanto liquido e quanto vapore hai.")
    else:
        body = (f"A questa temperatura la saturazione è una sola pressione, {dew} {unit}, "
                f"e le due colonne la condividono. La coppia (T, P) non fissa quanto liquido "
                f"e quanto vapore hai.")

    tail = ("Clicca una delle due colonne per leggerne lo stato completo."
            if mode == "tp" else "")

    return [lead, html.Span(body, className="dome-body"),
            html.Span(tail, className="dome-tail")] if tail else [lead, html.Span(body, className="dome-body")]


def _pin_head(pin, current, t_unit, p_unit):
    t_label = units.label("temperature", t_unit)
    p_label = units.label("pressure", p_unit)

    def coordinates(entry):
        t = units.from_si("temperature", t_unit, (entry or {}).get("temperature_K"))
        p = units.from_si("pressure", p_unit, (entry or {}).get("pressure_Pa"))
        if t is None or p is None:
            return [html.Span("—", className="dome-col-line")]
        return [
            html.Span(f"{fmt.plain(t, 3)} {t_label}", className="dome-col-line"),
            html.Span(f"{fmt.plain(p, 4)} {p_label}", className="dome-col-line"),
        ]

    def column(name, entry, css):
        return html.Th(
            className=f"dome-col {css}", scope="col", role="columnheader",
            children=[
                html.Span(name, className="dome-col-name"),
                html.Span(coordinates(entry), className="dome-col-pressure"),
            ],
        )

    def spacer(name):
        return html.Th("", scope="col", className="dome-col-spacer",
                       role="columnheader", **{"aria-label": name})

    return [
        spacer("Grandezza"),
        column("Corrente", current, "is-current"),
        column("Fissato", pin, "is-pinned-col"),
        spacer("Unità"),
    ]

SCAN_COLUMNS = (
    {"key": "density_kg_m3", "symbol": "ρ", "kind": "density"},
    {"key": "compressibility_factor", "symbol": "Z", "kind": "dimensionless"},
    {"key": "enthalpy_J_kg", "symbol": "h", "kind": "specific_energy"},
    {"key": "entropy_J_kg_K", "symbol": "s", "kind": "specific_entropy"},
)


def _resolve_scan(raw, fluid):
    if not raw:
        return None
    try:
        req = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(req, dict):
        return None

    axis, p_unit = req.get("axis"), req.get("pu")
    if axis not in ("isotherm", "isobar"):
        return None
    if p_unit not in units.UNITS["pressure"]["options"]:
        return None
    try:
        fixed, lo, hi = float(req["fixed"]), float(req["lo"]), float(req["hi"])
    except (KeyError, TypeError, ValueError):
        return None

    if axis == "isotherm":
        lo = units.to_si("pressure", p_unit, lo)
        hi = units.to_si("pressure", p_unit, hi)
    else:
        fixed = units.to_si("pressure", p_unit, fixed)

    if not (fixed > 0 and lo > 0 and hi > 0):
        return None
    return backend_bridge.scan(fluid, axis, fixed, lo, hi)


def _swept(scan):
    if scan and scan["axis"] == "isotherm":
        return {"key": "pressure_Pa", "symbol": "P", "kind": "pressure"}
    return {"key": "temperature_K", "symbol": "T", "kind": "temperature"}


def _scan_title(scan):
    if not scan or not scan.get("rows"):
        return "Scansione"
    return "Isoterma" if scan["axis"] == "isotherm" else "Isobara"


def _scan_note(scan, lim, t_unit, p_unit):
    if not scan or not scan.get("rows"):
        return ""

    rows = scan["rows"]
    t_label, p_label = units.label("temperature", t_unit), units.label("pressure", p_unit)

    if scan["axis"] == "isotherm":
        fixed = f"{fmt.plain(units.from_si('temperature', t_unit, scan['fixed_si']), 3)} {t_label}"
        lo = fmt.plain(units.from_si("pressure", p_unit, scan["lo_si"]), 4)
        hi = fmt.plain(units.from_si("pressure", p_unit, scan["hi_si"]), 4)
        span = f"da {lo} a {hi} {p_label}"
    else:
        fixed = f"{fmt.plain(units.from_si('pressure', p_unit, scan['fixed_si']), 4)} {p_label}"
        lo = fmt.plain(units.from_si("temperature", t_unit, scan["lo_si"]), 3)
        hi = fmt.plain(units.from_si("temperature", t_unit, scan["hi_si"]), 3)
        span = f"da {lo} a {hi} {t_label}"

    head = (f"{lim['label']} a {fixed}, {span}. {len(rows)} punti a passo logaritmico.")

    tally = {}
    for row in rows:
        if row["status"] != "ok":
            tally[row["status"]] = tally.get(row["status"], 0) + 1
    if not tally:
        return head

    said = {
        "two-phase": "dentro la campana bifase, dove (T, P) non individua uno stato",
        "out-of-range": "fuori dal campo di validità dichiarato",
        "extrapolated": "sopra la curva di fusione, dove i valori sono un'estrapolazione "
                        "del ramo liquido",
    }
    parts = [f"{count} {'punto' if count == 1 else 'punti'} {said[key]}"
             for key, count in tally.items() if key in said]
    return f"{head} {'; '.join(parts).capitalize()}."


def _scan_rows(scan, display, t_unit, p_unit):
    if not scan or not scan.get("rows"):
        return []

    swept = _swept(scan)
    swept_unit = t_unit if swept["kind"] == "temperature" else p_unit

    def unit_for(kind):
        if kind == "temperature":
            return t_unit
        if kind == "pressure":
            return p_unit
        return display[kind]

    header = html.Thead(role="rowgroup", children=html.Tr(
        className="scan-row scan-head", role="row",
        children=[html.Th(
            scope="col", role="columnheader", className="scan-cell",
            children=[html.Span(column["symbol"], className="scan-symbol"),
                      html.Span(units.label(column["kind"], unit_for(column["kind"]))
                                if column["kind"] != "dimensionless" else "—",
                                className="scan-unit")],
        ) for column in (swept,) + SCAN_COLUMNS],
    ))

    def column_values(column):
        unit = unit_for(column["kind"])
        return [units.from_si(column["kind"], unit, row.get(column["key"]))
                for row in scan["rows"] if row["status"] in ("ok", "extrapolated")]

    decimals = {}
    for column in (swept,) + SCAN_COLUMNS:
        seen = [units.from_si(swept["kind"], swept_unit, row[swept["key"]])
                for row in scan["rows"]] if column is swept else column_values(column)
        decimals[column["symbol"]] = max(
            (fmt.significant_decimals(v) for v in seen if v is not None), default=4)

    flagged = any(row["status"] == "extrapolated" for row in scan["rows"])

    body = []
    for row in scan["rows"]:
        shown = units.from_si(swept["kind"], swept_unit, row[swept["key"]])
        head = []
        if flagged:
            head.append(html.Span("solido" if row["status"] == "extrapolated" else "",
                                  className="scan-flag"))
        head += _value_cell(shown, decimals[swept["symbol"]])
        cells = [html.Th(head, scope="row", role="rowheader",
                         className="scan-cell scan-swept")]
        if row["status"] == "ok" or row["status"] == "extrapolated":
            for column in SCAN_COLUMNS:
                value = units.from_si(column["kind"], unit_for(column["kind"]),
                                      row.get(column["key"]))
                cells.append(html.Td(_value_cell(value, decimals[column["symbol"]]),
                                     role="cell", className="scan-cell"))
        else:
            cells.append(html.Td(SCAN_STATUS[row["status"]], role="cell",
                                 colSpan=len(SCAN_COLUMNS),
                                 className="scan-cell scan-absent"))
        body.append(html.Tr(cells, role="row",
                            className="scan-row" + (f" is-{row['status']}"
                                                    if row["status"] != "ok" else "")))

    return [html.Caption("Scansione dello stato lungo l'asse trascinato.",
                         className="visually-hidden"),
            header, html.Tbody(body, role="rowgroup")]


def _scan_export(scan, lim, display, t_unit, p_unit, sep, decimal):
    if not scan or not scan.get("rows"):
        return ""

    swept = _swept(scan)
    swept_unit = t_unit if swept["kind"] == "temperature" else p_unit

    def unit_for(kind):
        if kind == "temperature":
            return t_unit
        if kind == "pressure":
            return p_unit
        return display[kind]

    def cell(value):
        text = fmt.export(value, decimal) if (value is None or isinstance(value, (int, float))) \
            else str(value)
        if sep in text or '"' in text or "\n" in text:
            return '"' + text.replace('"', '""') + '"'
        return text

    def line(cells):
        return sep.join(cell(c) for c in cells)

    kind_label = "Isoterma" if scan["axis"] == "isotherm" else "Isobara"
    fixed_kind = "temperature" if scan["axis"] == "isotherm" else "pressure"
    fixed_unit = t_unit if fixed_kind == "temperature" else p_unit

    out = [
        line(["CryoCalculator", lim["label"], kind_label]),
        line(["Modello", lim["reference"]]),
        line([kind_label + " a", units.from_si(fixed_kind, fixed_unit, scan["fixed_si"]),
              units.label(fixed_kind, fixed_unit)]),
        "",
        line([swept["symbol"]] + [c["symbol"] for c in SCAN_COLUMNS] + ["Nota"]),
        line([units.label(swept["kind"], swept_unit)]
             + [units.label(c["kind"], unit_for(c["kind"])) if c["kind"] != "dimensionless"
                else "—" for c in SCAN_COLUMNS] + [""]),
    ]

    for row in scan["rows"]:
        values = [units.from_si(swept["kind"], swept_unit, row[swept["key"]])]
        if row["status"] in ("ok", "extrapolated"):
            values += [units.from_si(c["kind"], unit_for(c["kind"]), row.get(c["key"]))
                       for c in SCAN_COLUMNS]
        else:
            values += [None] * len(SCAN_COLUMNS)
        values.append(SCAN_STATUS.get(row["status"], ""))
        out.append(line(values))

    return "\n".join(out)


@app.callback(
    Output("mode", "value", allow_duplicate=True),
    Output("in-p-unit", "value", allow_duplicate=True),
    Output("in-p", "value", allow_duplicate=True),
    Input("pick-liquid", "n_clicks"),
    Input("pick-vapor", "n_clicks"),
    State("fluid", "value"), State("in-t", "value"), State("in-t-unit", "value"),
    prevent_initial_call=True,
)
def pick_saturated_column(n_liquid, n_vapor, fluid, t_raw, t_unit):
    trigger = dash.callback_context.triggered_id
    clicks = {"pick-liquid": n_liquid, "pick-vapor": n_vapor}
    stay = (dash.no_update, dash.no_update, dash.no_update)

    if not clicks.get(trigger):
        return stay

    fluid = _one_of(fluid, backend_bridge.FLUIDS, backend_bridge.DEFAULT_FLUID)
    t_unit = _one_of(t_unit, units.UNITS["temperature"]["options"],
                     units.DEFAULTS["temperature"])

    t_si = units.to_si("temperature", t_unit, _number(t_raw))
    if t_si is None:
        return stay

    pair = backend_bridge.saturated_pair(fluid, t_si)
    side = "liquid" if trigger == "pick-liquid" else "vapor"
    rho = (pair or {}).get(side, {}).get("density_kg_m3")
    if not rho:
        return stay

    return "trho", "kg/m3", units.from_si("density", "kg/m3", rho)

app.clientside_callback(
    """
    function (clicks, text) {
        var noUpdate = window.dash_clientside.no_update;
        if (!clicks || !text) { return [noUpdate, noUpdate, noUpdate]; }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text);
            return ["Tabella copiata negli appunti.", "COPIATO", false];
        }
        return ["Copia non disponibile in questo browser: seleziona la tabella e copiala.",
                noUpdate, noUpdate];
    }
    """,
    Output("copy-status", "children"),
    Output("copy-button", "children"),
    Output("copy-reset", "disabled"),
    Input("copy-button", "n_clicks"),
    State("table-tsv", "data"),
    prevent_initial_call=True,
)


@app.callback(
    Output("copy-button", "children", allow_duplicate=True),
    Output("copy-reset", "disabled", allow_duplicate=True),
    Input("copy-reset", "n_intervals"),
    prevent_initial_call=True,
)
def restore_copy_label(_ticks):
    return "COPIA", True

app.clientside_callback(
    """
    function (clicks, text) {
        if (!clicks || !text) { return window.dash_clientside.no_update; }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text);
            return "Scansione copiata negli appunti.";
        }
        return "Copia non disponibile in questo browser: seleziona la tabella e copiala.";
    }
    """,
    Output("copy-status", "children", allow_duplicate=True),
    Input("scan-copy-button", "n_clicks"),
    State("scan-tsv", "data"),
    prevent_initial_call=True,
)


@app.callback(
    Output("csv-download", "data", allow_duplicate=True),
    Input("scan-csv-button", "n_clicks"),
    State("scan-csv", "data"), State("fluid", "value"),
    prevent_initial_call=True,
)
def download_scan_csv(_clicks, text, fluid):
    if not isinstance(text, str) or not text:
        raise dash.exceptions.PreventUpdate
    fluid = _one_of(fluid, backend_bridge.FLUIDS, backend_bridge.DEFAULT_FLUID)
    label = backend_bridge.FLUIDS[fluid]["label"].lower()
    return dict(content="\ufeff" + text,
                filename=f"cryocalculator-{label}-scansione.csv")


@app.callback(
    Output("scan-request", "value"),
    Input("scan-clear-button", "n_clicks"),
    Input("fluid", "value"),
    prevent_initial_call=True,
)
def clear_scan(_clicks, _fluid):
    return ""


@app.callback(
    Output("pinned", "data"),
    Input("pin-button", "n_clicks"), Input("unpin-button", "n_clicks"),
    Input("fluid", "value"),
    State("current-state", "data"),
    prevent_initial_call=True,
)
def pin_state(_pin, _unpin, _fluid, current):
    trigger = dash.callback_context.triggered_id
    if trigger in ("unpin-button", "fluid"):
        return None
    if not isinstance(current, dict) or not current:
        raise dash.exceptions.PreventUpdate
    return _clean_pin(current)

app.clientside_callback(
    """
    function (text) {
        if (window.__cryoAnnounce) { window.clearTimeout(window.__cryoAnnounce); }
        window.__cryoAnnounce = window.setTimeout(function () {
            var node = document.getElementById("live-announce");
            if (node) { node.textContent = text || ""; }
        }, 450);
        return window.dash_clientside.no_update;
    }
    """,
    Output("announce-sink", "data"),
    Input("announce", "data"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function (invalid) {
        ["in-t", "in-p"].forEach(function (id) {
            var input = document.getElementById(id);
            if (!input) { return; }
            var wrong = id === invalid;
            input.setAttribute("aria-invalid", wrong ? "true" : "false");
            var box = input.closest(".field");
            if (box) { box.classList.toggle("is-invalid", wrong); }
        });
        return window.dash_clientside.no_update;
    }
    """,
    Output("invalid-sink", "data"),
    Input("invalid-field", "data"),
)

app.clientside_callback(
    """
    function (clicks, fluid) {
        if (!clicks) { return window.dash_clientside.no_update; }
        var gd = document.querySelector("#chart .js-plotly-plot");
        if (!gd || !window.Plotly || !window.Plotly.downloadImage) {
            return "Esportazione della carta non disponibile in questo browser.";
        }
        window.Plotly.downloadImage(gd, {
            format: "svg",
            width: 1400,
            height: 900,
            filename: "cryocalculator-" + (fluid || "carta")
        });
        return "Carta esportata in SVG.";
    }
    """,
    Output("copy-status", "children", allow_duplicate=True),
    Input("svg-button", "n_clicks"),
    State("fluid", "value"),
    prevent_initial_call=True,
)


@app.callback(
    Output("csv-download", "data"),
    Input("csv-button", "n_clicks"),
    State("table-csv", "data"), State("fluid", "value"),
    prevent_initial_call=True,
)
def download_csv(_clicks, text, fluid):
    if not isinstance(text, str) or not text:
        raise dash.exceptions.PreventUpdate
    fluid = _one_of(fluid, backend_bridge.FLUIDS, backend_bridge.DEFAULT_FLUID)
    label = backend_bridge.FLUIDS[fluid]["label"].lower()
    return dict(content="\ufeff" + text, filename=f"cryocalculator-{label}.csv")


def _sat_note(lim, t_si, t_unit):
    if t_si is None:
        return ""
    if t_si < lim["t_min_K"] or t_si > lim["t_max_K"]:
        return ""
    if t_si > lim["t_critical_K"]:
        t_c = fmt.plain(units.from_si("temperature", t_unit, lim["t_critical_K"]), 3)
        return (f"Sopra la temperatura critica ({t_c} {units.label('temperature', t_unit)}) "
                f"liquido e vapore non si distinguono: non esiste saturazione da riportare.")
    if lim["mixture"]:
        return ("L'aria è una miscela, quindi rugiada e bolla cadono a pressioni diverse: "
                "fra le due il fluido è bifase.")
    return ("Fluido puro: rugiada e bolla coincidono, e insieme sono la tensione di vapore "
            "a questa temperatura.")

for _key in backend_bridge.FLUIDS:
    try:
        backend_bridge.state(_key, 300.0, p_Pa=101325.0)
    except Exception:
        pass

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=int(os.environ.get("PORT", 8050)))
