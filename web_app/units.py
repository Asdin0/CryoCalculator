UNITS = {
    "temperature": {
        "si": "K",
        "options": {
            "K": {"label": "K", "name": "kelvin", "to_si": lambda v: v, "from_si": lambda v: v, "decimals": 3},
            "C": {"label": "°C", "name": "grado Celsius", "to_si": lambda v: v + 273.15, "from_si": lambda v: v - 273.15, "decimals": 3},
        },
    },
    "pressure": {
        "si": "Pa",
        "options": {
            "Pa": {"label": "Pa", "name": "pascal", "to_si": lambda v: v, "from_si": lambda v: v, "decimals": 1},
            "kPa": {"label": "kPa", "name": "kilopascal", "to_si": lambda v: v * 1e3, "from_si": lambda v: v / 1e3, "decimals": 4},
            "bar": {"label": "bar", "name": "bar", "to_si": lambda v: v * 1e5, "from_si": lambda v: v / 1e5, "decimals": 5},
            "MPa": {"label": "MPa", "name": "megapascal", "to_si": lambda v: v * 1e6, "from_si": lambda v: v / 1e6, "decimals": 6},
        },
    },
    "density": {
        "si": "kg/m3",
        "options": {
            "kg/m3": {"label": "kg/m³", "name": "chilogrammo al metro cubo", "to_si": lambda v: v, "from_si": lambda v: v, "decimals": 4},
            "g/cm3": {"label": "g/cm³", "name": "grammo al centimetro cubo", "to_si": lambda v: v * 1e3, "from_si": lambda v: v / 1e3, "decimals": 7},
        },
    },
    "specific_energy": {
        "si": "J/kg",
        "options": {
            "J/kg": {"label": "J/kg", "name": "joule al chilogrammo", "to_si": lambda v: v, "from_si": lambda v: v, "decimals": 2},
            "kJ/kg": {"label": "kJ/kg", "name": "kilojoule al chilogrammo", "to_si": lambda v: v * 1e3, "from_si": lambda v: v / 1e3, "decimals": 5},
        },
    },
    "specific_entropy": {
        "si": "J/(kg*K)",
        "options": {
            "J/(kg*K)": {"label": "J/kg·K", "name": "joule al chilogrammo kelvin", "to_si": lambda v: v, "from_si": lambda v: v, "decimals": 3},
            "kJ/(kg*K)": {"label": "kJ/kg·K", "name": "kilojoule al chilogrammo kelvin", "to_si": lambda v: v * 1e3, "from_si": lambda v: v / 1e3, "decimals": 6},
        },
    },
    "dimensionless": {
        "si": "—",
        "options": {"—": {"label": "—", "name": "adimensionale", "to_si": lambda v: v, "from_si": lambda v: v, "decimals": 5}},
    },
}

DEFAULTS = {
    "temperature": "K",
    "pressure": "bar",
    "density": "kg/m3",
    "specific_energy": "kJ/kg",
    "specific_entropy": "kJ/(kg*K)",
    "dimensionless": "—",
}


def spec(kind: str, unit: str) -> dict:
    group = UNITS[kind]
    try:
        chosen = group["options"].get(unit)
    except TypeError:
        chosen = None
    return chosen or group["options"][DEFAULTS[kind]]


def to_si(kind: str, unit: str, value):
    if value is None:
        return None
    return spec(kind, unit)["to_si"](value)


def from_si(kind: str, unit: str, value):
    if value is None:
        return None
    return spec(kind, unit)["from_si"](value)


def label(kind: str, unit: str) -> str:
    return spec(kind, unit)["label"]


def decimals(kind: str, unit: str) -> int:
    return spec(kind, unit)["decimals"]


def options(kind: str) -> list:
    return [{"label": o["label"], "value": key} for key, o in UNITS[kind]["options"].items()]
