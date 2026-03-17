import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from presets import get_usage_preset


MIN_LINTEL_HEIGHT_CM = 20
MIN_LINTEL_WIDTH_CM = 25


@dataclass
class LintelInput:
    """
    Input semplificato per predimensionamento architrave in c.a.
    """
    opening_width_m: float
    usage_key: str
    load_above_mode: str  # "light_wall" oppure "wall_plus_floor"
    available_height_cm: Optional[float] = None
    lintel_width_cm: Optional[float] = None
    concrete_density_kN_m3: float = 25.0


@dataclass
class LintelResult:
    element: str
    material: str
    usage: str
    opening_width_m: float
    load_above_mode: str
    lintel_width_cm: int
    lintel_height_cm: int
    self_weight_kN_m: float
    adopted_line_load_kN_m: float
    max_moment_kNm: float
    opening_to_height_ratio: float
    status: str
    note: str
    warnings: List[str]


def _round_up_to_5(value_cm: float) -> int:
    return int(math.ceil(value_cm / 5.0) * 5)


def _validate_input(data: LintelInput) -> None:
    if data.opening_width_m <= 0:
        raise ValueError("La larghezza apertura deve essere maggiore di zero.")

    if data.load_above_mode not in {"light_wall", "wall_plus_floor"}:
        raise ValueError("load_above_mode deve essere 'light_wall' oppure 'wall_plus_floor'.")

    if data.available_height_cm is not None and data.available_height_cm <= 0:
        raise ValueError("L'altezza disponibile deve essere maggiore di zero.")

    if data.lintel_width_cm is not None and data.lintel_width_cm <= 0:
        raise ValueError("La larghezza architrave deve essere maggiore di zero.")

    if data.concrete_density_kN_m3 <= 0:
        raise ValueError("La densità del calcestruzzo deve essere maggiore di zero.")


def _estimate_initial_height_cm(opening_width_m: float, load_above_mode: str) -> int:
    opening_cm = opening_width_m * 100.0

    if load_above_mode == "light_wall":
        raw_h = opening_cm / 12.0
    else:
        raw_h = opening_cm / 10.0

    raw_h = max(raw_h, MIN_LINTEL_HEIGHT_CM)
    return _round_up_to_5(raw_h)


def _normalize_width_cm(user_width_cm: Optional[float], height_cm: int) -> Dict[str, Any]:
    warnings: List[str] = []

    recommended_min = max(MIN_LINTEL_WIDTH_CM, _round_up_to_5(height_cm / 2.0))

    if user_width_cm is None:
        return {
            "lintel_width_cm": recommended_min,
            "warnings": warnings,
        }

    requested = _round_up_to_5(user_width_cm)

    if requested < recommended_min:
        warnings.append(
            f"Larghezza architrave troppo ridotta ({requested} cm): adottati {recommended_min} cm."
        )
        return {
            "lintel_width_cm": recommended_min,
            "warnings": warnings,
        }

    return {
        "lintel_width_cm": requested,
        "warnings": warnings,
    }


def _estimate_line_load_kN_m(load_above_mode: str, usage_key: str) -> float:
    """
    Stima molto semplificata del carico lineare sopra l'apertura.
    """
    preset = get_usage_preset(usage_key)

    if load_above_mode == "light_wall":
        return 12.0

    floor_related = 6.0 + preset.dead_load_non_structural_kN_m2 + preset.live_load_kN_m2
    return 20.0 + floor_related


def _calc_self_weight_kN_m(width_cm: float, height_cm: float, concrete_density_kN_m3: float) -> float:
    width_m = width_cm / 100.0
    height_m = height_cm / 100.0
    return width_m * height_m * concrete_density_kN_m3


def _calc_max_moment_kNm(opening_width_m: float, line_load_kN_m: float) -> float:
    return line_load_kN_m * opening_width_m**2 / 8.0


def _classify_result(
    opening_width_m: float,
    lintel_height_cm: int,
    available_height_cm: Optional[float],
    existing_warnings: List[str],
) -> Dict[str, Any]:
    warnings = list(existing_warnings)

    opening_cm = opening_width_m * 100.0
    ratio = opening_cm / lintel_height_cm

    status = "Plausibile"
    note = "Ordine di grandezza coerente per uno studio preliminare."

    if available_height_cm is not None and lintel_height_cm > available_height_cm:
        status = "Non compatibile geometricamente"
        note = "L'altezza preliminare supera il limite disponibile sopra l'apertura."
        warnings.append(
            f"Architrave proposto {lintel_height_cm} cm > altezza disponibile {available_height_cm:.0f} cm."
        )
        return {
            "status": status,
            "note": note,
            "warnings": warnings,
            "opening_to_height_ratio": round(ratio, 2),
        }

    if ratio <= 10:
        status = "Plausibile"
        note = "Ordine di grandezza coerente per uno studio preliminare."
    elif ratio <= 12:
        status = "Da verificare con attenzione"
        note = "Architrave possibile ma relativamente tirato."
        warnings.append("Rapporto apertura/altezza vicino a un campo da valutare con maggiore attenzione.")
    else:
        status = "Fuori scala / non consigliato"
        note = "Architrave troppo ridotto per un predimensionamento prudente."
        warnings.append("Rapporto apertura/altezza eccessivo rispetto a una stima cautelativa.")

    return {
        "status": status,
        "note": note,
        "warnings": warnings,
        "opening_to_height_ratio": round(ratio, 2),
    }


def calculate_lintel_preliminary(data: LintelInput) -> LintelResult:
    _validate_input(data)

    preset = get_usage_preset(data.usage_key)

    lintel_height_cm = _estimate_initial_height_cm(data.opening_width_m, data.load_above_mode)

    width_info = _normalize_width_cm(data.lintel_width_cm, lintel_height_cm)
    lintel_width_cm = width_info["lintel_width_cm"]
    geometry_warnings = width_info["warnings"]

    self_weight_kN_m = _calc_self_weight_kN_m(
        width_cm=lintel_width_cm,
        height_cm=lintel_height_cm,
        concrete_density_kN_m3=data.concrete_density_kN_m3,
    )

    line_load_kN_m = _estimate_line_load_kN_m(data.load_above_mode, data.usage_key)
    adopted_line_load_kN_m = line_load_kN_m + self_weight_kN_m

    max_moment_kNm = _calc_max_moment_kNm(data.opening_width_m, adopted_line_load_kN_m)

    if max_moment_kNm > 40:
        lintel_height_cm += 5
    if max_moment_kNm > 60:
        lintel_height_cm += 5

    lintel_height_cm = _round_up_to_5(lintel_height_cm)

    width_info = _normalize_width_cm(data.lintel_width_cm, lintel_height_cm)
    lintel_width_cm = width_info["lintel_width_cm"]
    geometry_warnings = width_info["warnings"]

    self_weight_kN_m = _calc_self_weight_kN_m(
        width_cm=lintel_width_cm,
        height_cm=lintel_height_cm,
        concrete_density_kN_m3=data.concrete_density_kN_m3,
    )
    adopted_line_load_kN_m = line_load_kN_m + self_weight_kN_m
    max_moment_kNm = _calc_max_moment_kNm(data.opening_width_m, adopted_line_load_kN_m)

    classification = _classify_result(
        opening_width_m=data.opening_width_m,
        lintel_height_cm=lintel_height_cm,
        available_height_cm=data.available_height_cm,
        existing_warnings=geometry_warnings,
    )

    return LintelResult(
        element="Architrave",
        material="Calcestruzzo armato",
        usage=preset.label,
        opening_width_m=round(data.opening_width_m, 2),
        load_above_mode=data.load_above_mode,
        lintel_width_cm=lintel_width_cm,
        lintel_height_cm=lintel_height_cm,
        self_weight_kN_m=round(self_weight_kN_m, 2),
        adopted_line_load_kN_m=round(adopted_line_load_kN_m, 2),
        max_moment_kNm=round(max_moment_kNm, 2),
        opening_to_height_ratio=classification["opening_to_height_ratio"],
        status=classification["status"],
        note=classification["note"],
        warnings=classification["warnings"],
    )