import math
import typing

ABSENT = "—"

SIGNIFICANT = 6

MAX_DECIMALS = 5


def significant_decimals(value: typing.Optional[float],
                         significant: int = SIGNIFICANT,
                         cap: int = MAX_DECIMALS) -> int:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value) or value == 0:
        return min(significant - 1, cap)
    exponent = math.floor(math.log10(abs(value)))
    return max(0, min(cap, significant - 1 - exponent))


def parts(value: typing.Optional[float], decimals: int = 4) -> dict:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return {"integer": ABSENT, "fraction": "", "exponent": "", "absent": True}

    magnitude = abs(value)
    if magnitude and (magnitude >= 1e6 or magnitude < 1e-3):
        mantissa, exponent = f"{value:.{max(decimals - 2, 2)}e}".split("e")
        integer, _, fraction = mantissa.partition(".")
        return {
            "integer": integer,
            "fraction": fraction,
            "exponent": f"×10{_superscript(int(exponent))}",
            "absent": False,
        }

    text = f"{value:.{decimals}f}"
    integer, _, fraction = text.partition(".")
    return {"integer": integer, "fraction": fraction, "exponent": "", "absent": False}


def plain(value: typing.Optional[float], decimals: int = 4) -> str:
    p = parts(value, decimals)
    if p["absent"]:
        return ABSENT
    fraction = f".{p['fraction']}" if p["fraction"] else ""
    return f"{p['integer']}{fraction}{p['exponent']}"


def export(value: typing.Optional[float], decimal: str = ".") -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return ""
    text = f"{value:.{SIGNIFICANT}g}"
    return text if decimal == "." else text.replace(".", decimal)

_SUPERSCRIPT = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def _superscript(n: int) -> str:
    return str(n).translate(_SUPERSCRIPT)
