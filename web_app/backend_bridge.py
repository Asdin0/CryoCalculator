import functools
import math
import os
import sys
import typing

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _sub in ("general_class", "fluid_list"):
    _path = os.path.join(_ROOT, "StateFunctionCalculator", _sub)
    if _path not in sys.path:
        sys.path.insert(0, _path)

_EFFICIENCY = os.path.join(_ROOT, "EfficiencyCalculator")
if _EFFICIENCY not in sys.path:
    sys.path.insert(0, _EFFICIENCY)


class DomainError(Exception):
    def __init__(self, message, quantity=None, low=None, high=None, value=None,
                 bound="inclusive"):
        super().__init__(message)
        self.quantity = quantity
        self.low = low
        self.high = high
        self.value = value
        self.bound = bound


class TwoPhaseState(Exception):
    def __init__(self, dew_pressure_Pa, bubble_pressure_Pa, pair=None):
        self.dew_pressure_Pa = dew_pressure_Pa
        self.bubble_pressure_Pa = bubble_pressure_Pa
        self.pair = pair or {}
        super().__init__("two-phase")

FLUIDS = {
    "nitrogen": {
        "key": "nitrogen",
        "label": "Azoto",
        "formula": [("N", False), ("2", True)],
        "module": "nitrogen",
        "cls": "Nitrogen",
        "reference": "Span, Lemmon, Jacobsen, Wagner & Yokozeki (2000)",
        "reference_detail": (
            "A Reference Equation of State for the Thermodynamic Properties of "
            "Nitrogen for Temperatures from 63.151 to 1000 K and Pressures to 2200 MPa"
        ),
        "mixture": False,
    },
    "air": {
        "key": "air",
        "label": "Aria",
        "formula": [("Aria secca", False)],
        "module": "air",
        "cls": "Air",
        "reference": "Lemmon, Jacobsen, Penoncello & Friend (2000)",
        "reference_detail": (
            "Thermodynamic Properties of Air and Mixtures of Nitrogen, Argon, and "
            "Oxygen from 60 to 2000 K at Pressures to 2000 MPa"
        ),
        "mixture": True,
    },
}

DEFAULT_FLUID = "nitrogen"

PROPERTIES = (
    {"key": "density_kg_m3", "symbol": "ρ", "name": "Densità", "unit": "kg/m³", "kind": "density"},
    {"key": "compressibility_factor", "symbol": "Z", "name": "Fattore di comprimibilità", "unit": "—", "kind": "dimensionless"},
    {"key": "internal_energy_J_kg", "symbol": "u", "name": "Energia interna", "unit": "J/kg", "kind": "specific_energy"},
    {"key": "enthalpy_J_kg", "symbol": "h", "name": "Entalpia", "unit": "J/kg", "kind": "specific_energy"},
    {"key": "entropy_J_kg_K", "symbol": "s", "name": "Entropia", "unit": "J/(kg·K)", "kind": "specific_entropy"},
)

SATURATION_PROPERTIES = (
    {"key": "dew_point_pressure_Pa", "symbol": "P_dew", "name": "Pressione di rugiada", "unit": "Pa", "kind": "pressure"},
    {"key": "bubble_point_pressure_Pa", "symbol": "P_bub", "name": "Pressione di bolla", "unit": "Pa", "kind": "pressure"},
    {"key": "dew_point_density_kg_m3", "symbol": "ρ_dew", "name": "Densità vapore saturo", "unit": "kg/m³", "kind": "density"},
    {"key": "bubble_point_density_kg_m3", "symbol": "ρ_bub", "name": "Densità liquido saturo", "unit": "kg/m³", "kind": "density"},
)

PHASE_LABELS = {
    "gas": "Gas",
    "vapor": "Vapore",
    "liquid": "Liquido",
    "supercritical": "Supercritico",
    "two-phase": "Bifase",
    "solid": "Solido",
}

MODELLED_PHASES = frozenset({"gas", "vapor", "liquid", "supercritical"})


@functools.lru_cache(maxsize=None)
def _instance(fluid_key: str):
    spec = FLUIDS[fluid_key]
    module = __import__(spec["module"])
    return getattr(module, spec["cls"])()


@functools.lru_cache(maxsize=None)
def limits(fluid_key: str) -> dict:
    f = _instance(fluid_key)
    spec = FLUIDS[fluid_key]
    c, a = f.constants, f.acceptable_parameters
    return {
        "key": fluid_key,
        "label": spec["label"],
        "formula": spec["formula"],
        "reference": spec["reference"],
        "reference_detail": spec["reference_detail"],
        "mixture": spec["mixture"],
        "t_min_K": a.T_minimum_value_K,
        "t_max_K": a.T_maximum_value_K,
        "p_min_Pa": max(a.P_minimum_value_Pa, 1.0),
        "p_max_Pa": a.P_maximum_value_Pa,
        "t_critical_K": c.critical_temperature_K,
        "p_critical_Pa": c.critical_pressure_Pa,
        "rho_critical_kg_m3": c.critical_density_kg_m3,
        "t_triple_K": c.triplepoint_temperature_K,
        "p_triple_Pa": c.triplepoint_pressure_Pa,
        "t_melting_K": c.melting_temperature_K,
        "p_melting_Pa": c.melting_pressure_Pa,
        "molar_mass_kg_mol": c.molar_mass_kg_mol,
        "acentric_factor": c.acentric_factor,
    }


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None

_TWO_PHASE_MARKER = "two-phase condition"


@functools.lru_cache(maxsize=512)
def saturated_pair(fluid_key: str, t_K: float) -> typing.Optional[dict]:
    f = _instance(fluid_key)
    lim = limits(fluid_key)
    if t_K > lim["t_critical_K"]:
        return None

    sides = (
        ("liquid", "Liquido saturo", f.bubblepoint_pressure, f.bubblepoint_density),
        ("vapor", "Vapore saturo", f.dewpoint_pressure, f.dewpoint_density),
    )

    pair = {}
    for key, label, pressure_fn, density_fn in sides:
        rho = _safe(density_fn, t_K)
        pressure = _safe(pressure_fn, t_K)
        if rho is None or pressure is None or rho <= 0:
            return None
        try:
            result = f.calculated_functions(t=t_K, density=rho)
        except Exception:
            return None

        entry = {
            "fluid": fluid_key,
            "temperature_K": t_K,
            "pressure_Pa": pressure,
            "phase": key,
            "phase_label": label,
        }
        for prop in PROPERTIES:
            entry[prop["key"]] = getattr(result, prop["key"], None)
        pair[key] = entry

    return pair


def _phase_of(f, t: float, p: float) -> typing.Optional[str]:
    try:
        return f.phases(t, p)
    except Exception:
        return None


def state(fluid_key: str, t_K: float, p_Pa: typing.Optional[float] = None,
          rho_kg_m3: typing.Optional[float] = None) -> dict:
    f = _instance(fluid_key)
    lim = limits(fluid_key)

    if t_K is None or not math.isfinite(t_K):
        raise DomainError("Serve una temperatura.")
    if t_K < lim["t_min_K"] or t_K > lim["t_max_K"]:
        raise DomainError(
            f"L'equazione di stato per {lim['label'].lower()} copre da "
            f"{lim['t_min_K']:g} K a {lim['t_max_K']:g} K. "
            f"Hai chiesto {t_K:g} K.",
            quantity="temperature", low=lim["t_min_K"], high=lim["t_max_K"], value=t_K,
        )

    if p_Pa is not None:
        if not math.isfinite(p_Pa):
            raise DomainError("Serve una pressione.")
        if p_Pa <= 0 or p_Pa > lim["p_max_Pa"]:
            raise DomainError(
                f"La pressione deve essere maggiore di zero e non superare "
                f"{lim['p_max_Pa']:g} Pa ({lim['p_max_Pa'] / 1e6:g} MPa). "
                f"Hai chiesto {p_Pa:g} Pa.",
                quantity="pressure", low=0.0, high=lim["p_max_Pa"], value=p_Pa,
                bound="above-low",
            )
        if _phase_of(f, t_K, p_Pa) == "two-phase":
            raise _two_phase(f, fluid_key, t_K)

    if rho_kg_m3 is not None and (not math.isfinite(rho_kg_m3) or rho_kg_m3 <= 0):
        raise DomainError("La densità deve essere maggiore di zero.",
                          quantity="density", low=0.0, value=rho_kg_m3,
                          bound="above-low")

    try:
        result = f.calculated_functions(t=t_K, p=p_Pa, density=rho_kg_m3)
    except TwoPhaseState:
        raise
    except ValueError as exc:
        if _TWO_PHASE_MARKER in str(exc):
            raise _two_phase(f, fluid_key, t_K) from exc
        raise DomainError(_readable(exc, lim, t_K, p_Pa)) from exc
    except ZeroDivisionError as exc:
        raise DomainError(
            "Il calcolo non converge a questo stato. Prova a spostarti di poco "
            "dalla curva di saturazione."
        ) from exc

    out = {
        "fluid": fluid_key,
        "temperature_K": result.temperature_input_K,
        "pressure_Pa": result.pressure_input_Pa,
        "phase": result.phase,
        "phase_label": PHASE_LABELS.get(result.phase, "—"),
    }
    for prop in PROPERTIES + SATURATION_PROPERTIES:
        out[prop["key"]] = getattr(result, prop["key"], None)

    if out["pressure_Pa"] is None and out.get("density_kg_m3") and out.get("compressibility_factor"):
        r_specific = 8.314472 / lim["molar_mass_kg_mol"]
        out["pressure_Pa"] = (out["compressibility_factor"] * out["density_kg_m3"]
                              * r_specific * out["temperature_K"])
        out["pressure_is_derived"] = True
        if out["pressure_Pa"] <= 0:
            out["pressure_Pa"] = None
            out["pressure_is_derived"] = False
        elif out["phase"] is None:
            out["phase"] = _phase_of(f, t_K, out["pressure_Pa"])
            out["phase_label"] = PHASE_LABELS.get(out["phase"], "—")
    else:
        out["pressure_is_derived"] = False

    out["extrapolated"] = out["phase"] is not None and out["phase"] not in MODELLED_PHASES
    out["melting_pressure_Pa"] = _safe(f.meltingpoint_pressure, t_K) if out["extrapolated"] else None

    return out


def _two_phase(f, fluid_key: str, t_K: float) -> TwoPhaseState:
    return TwoPhaseState(
        _safe(f.dewpoint_pressure, t_K),
        _safe(f.bubblepoint_pressure, t_K),
        saturated_pair(fluid_key, t_K),
    )


def _readable(exc: ValueError, lim: dict, t_K: float, p_Pa: typing.Optional[float]) -> str:
    text = str(exc)
    if "temperature must be" in text or "pressure must be" in text:
        return (
            f"Stato fuori dal campo di validità: da {lim['t_min_K']:g} K a "
            f"{lim['t_max_K']:g} K, fino a {lim['p_max_Pa'] / 1e6:g} MPa."
        )
    return (
        "L'algoritmo di bisezione non riesce a chiudere su una densità a questo "
        "stato. Succede sulla curva di saturazione, dove liquido e vapore coesistono: "
        "specifica la densità invece della pressione per scegliere quale dei due."
    )


@functools.lru_cache(maxsize=None)
def saturation_curve(fluid_key: str, steps: int = 260) -> dict:
    f = _instance(fluid_key)
    lim = limits(fluid_key)
    t_start = lim["t_triple_K"] or lim["t_min_K"]
    t_start = max(t_start, lim["t_min_K"])
    t_end = lim["t_critical_K"]

    temps, dew, bubble = [], [], []
    for i in range(steps + 1):
        t = t_start + (t_end - t_start) * i / steps
        try:
            d = f.dewpoint_pressure(t)
            b = f.bubblepoint_pressure(t)
        except Exception:
            continue
        if d is None or b is None or d <= 0 or b <= 0:
            continue
        temps.append(t)
        dew.append(d)
        bubble.append(b)

    widest = max(((b - d) / b for d, b in zip(dew, bubble) if b), default=0.0)
    return {
        "temperature_K": temps,
        "dew_Pa": dew,
        "bubble_Pa": bubble,
        "has_band": widest > 0.001,
        "widest_gap": widest,
    }


@functools.lru_cache(maxsize=None)
def melting_curve(fluid_key: str, steps: int = 120) -> dict:
    f = _instance(fluid_key)
    lim = limits(fluid_key)
    t_start = lim["t_min_K"]
    t_end = lim["t_critical_K"]
    temps, pressures = [], []
    for i in range(steps + 1):
        t = t_start + (t_end - t_start) * i / steps
        p = _safe(f.meltingpoint_pressure, t)
        if p is not None and not (0 < p <= lim["p_max_Pa"]):
            p = None
        temps.append(t)
        pressures.append(p)
    return {"temperature_K": temps, "pressure_Pa": pressures}


def melting_pressure_at(fluid_key: str, temperatures) -> list:
    f = _instance(fluid_key)
    return [_safe(f.meltingpoint_pressure, t) for t in temperatures]


@functools.lru_cache(maxsize=None)
def isochores(fluid_key: str, count: int = 7, steps: int = 44) -> list:
    f = _instance(fluid_key)
    lim = limits(fluid_key)
    rho_c = lim["rho_critical_kg_m3"]

    fractions = [0.004, 0.02, 0.08, 0.3, 1.0, 2.0, 2.8][:count]
    t_lo, t_hi = lim["t_min_K"], lim["t_max_K"]

    family = []
    for frac in fractions:
        rho = rho_c * frac
        temps, pressures = [], []
        for i in range(steps + 1):
            t = t_lo * (t_hi / t_lo) ** (i / steps)
            p = None
            try:
                z = f.calculated_functions(t=t, density=rho).compressibility_factor
                if z is not None and math.isfinite(z):
                    candidate = z * rho * (8.314472 / lim["molar_mass_kg_mol"]) * t
                    if math.isfinite(candidate) and 0 < candidate <= lim["p_max_Pa"]:
                        p = candidate
            except Exception:
                p = None
            temps.append(t)
            pressures.append(p)

        if sum(1 for p in pressures if p is not None) > 3:
            family.append({"rho_kg_m3": rho, "temperature_K": temps, "pressure_Pa": pressures})
    return family

SCAN_POINTS = 21


@functools.lru_cache(maxsize=32)
def scan(fluid_key: str, axis: str, fixed_si: float, lo_si: float, hi_si: float,
         points: int = SCAN_POINTS) -> dict:
    lo, hi = (lo_si, hi_si) if lo_si <= hi_si else (hi_si, lo_si)
    if not (lo > 0 and hi > lo) or points < 2:
        return {"axis": axis, "fluid": fluid_key, "rows": []}

    rows = []
    for i in range(points):
        step = lo * (hi / lo) ** (i / (points - 1))
        t_K = fixed_si if axis == "isotherm" else step
        p_Pa = step if axis == "isotherm" else fixed_si

        row = {"temperature_K": t_K, "pressure_Pa": p_Pa, "status": "ok", "phase": None}
        try:
            resolved = state(fluid_key, t_K, p_Pa=p_Pa)
        except TwoPhaseState:
            row.update(status="two-phase", phase="two-phase")
        except DomainError:
            row.update(status="out-of-range")
        else:
            row["phase"] = resolved.get("phase")
            if resolved.get("extrapolated"):
                row["status"] = "extrapolated"
            for prop in PROPERTIES:
                row[prop["key"]] = resolved.get(prop["key"])
        rows.append(row)

    return {"axis": axis, "fluid": fluid_key, "fixed_si": fixed_si,
            "lo_si": lo, "hi_si": hi, "rows": rows}


def exchanger(arrangement: str, **kwargs) -> dict:
    import HeatExchanger

    cls = HeatExchanger.CfHeatExchanger if arrangement == "counterflow" else HeatExchanger.EqHeatExchanger
    out = {}
    for name, fn in (("lmtd", cls.logarithmic_mean_temperature_difference),
                     ("epsilon", cls.epsilon), ("ntu", cls.ntu)):
        try:
            out[name] = fn(**{k: v for k, v in kwargs.items()
                              if k in fn.__code__.co_varnames})
        except Exception:
            out[name] = None
    return out
