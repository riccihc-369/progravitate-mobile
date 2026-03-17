import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from presets import get_usage_preset


MIN_SLAB_THICKNESS_CM = 12


@dataclass
class SlabInput:
    """
    Input semplificato per predimensionamento soletta in c.a.
    """
    span_m: float
    slab_type: str  # "one_way" oppure "two_way"
    usage_key: str
    max_thickness_cm: Optional[float] = None
    structural_dead_load_kN_m2: float = 3.0
    concrete_density_kN_m3: float = 25.0


@dataclass
class SlabResult:
    element: str
    material: str
    usage: str
    span_m: float
    slab_type: str
    thickness_cm: int
    self_weight_kN_m2: float
    adopted_surface_load_kN_m2: float
    max_moment_kNm_per_m: float
    span_to_thickness_ratio: float
    status: str
    note: str
    warnings: List[str]


def _round_up_to_2(value_cm: float) -> int:
    return int(math.ceil(value_cm / 2.0) * 2)


def _validate_input(data: SlabInput) -> None:
    if data.span_m <= 0:
        raise ValueError("La luce deve essere maggiore di zero.")

    if data.slab_type not in {"one_way", "two_way"}:
        raise ValueError("slab_type deve essere 'one_way' oppure 'two_way'.")

    if data.max_thickness_cm is not None and data.max_thickness_cm <= 0:
        raise ValueError("Lo spessore massimo deve essere maggiore di zero.")

    if data.structural_dead_load_kN_m2 < 0:
        raise ValueError("Il carico permanente strutturale non può essere negativo.")

    if data.concrete_density_kN_m3 <= 0:
        raise ValueError("La densità del calcestruzzo deve essere maggiore di zero.")


def _estimate_initial_thickness_cm(span_m: float, slab_type: str) -> int:
    """
    Regola preliminare semplice:
    - soletta monodirezionale: circa L/28
    - soletta bidirezionale: circa L/32
    """
    span_cm = span_m * 100.0

    if slab_type == "one_way":
        raw_t = span_cm / 28.0
    else:
        raw_t = span_cm / 32.0

    raw_t = max(raw_t, MIN_SLAB_THICKNESS_CM)
    return _round_up_to_2(raw_t)


def _calc_self_weight_kN_m2(thickness_cm: float, concrete_density_kN_m3: float) -> float:
    thickness_m = thickness_cm / 100.0
    return thickness_m * concrete_density_kN_m3


def _calc_surface_load_kN_m2(
    structural_dead_load_kN_m2: float,
    non_structural_dead_load_kN_m2: float,
    live_load_kN_m2: float,
    self_weight_kN_m2: float,
) -> float:
    return (
        structural_dead_load_kN_m2
        + non_structural_dead_load_kN_m2
        + live_load_kN_m2
        + self_weight_kN_m2
    )


def _calc_max_moment_kNm_per_m(span_m: float, surface_load_kN_m2: float, slab_type: str) -> float:
    """
    Calcolo semplificato per striscia da 1 m:
    - monodirezionale: M = qL²/8
    - bidirezionale: coefficiente ridotto semplificato ~ qL²/16
    """
    if slab_type == "one_way":
        return surface_load_kN_m2 * span_m**2 / 8.0
    return surface_load_kN_m2 * span_m**2 / 16.0


def _classify_result(
    span_m: float,
    thickness_cm: int,
    max_thickness_cm: Optional[float],
    slab_type: str,
) -> Dict[str, Any]:
    warnings: List[str] = []

    span_cm = span_m * 100.0
    ratio = span_cm / thickness_cm

    if slab_type == "one_way":
        plausible_limit = 28.0
        attention_limit = 32.0
    else:
        plausible_limit = 32.0
        attention_limit = 36.0

    status = "Plausibile"
    note = "Ordine di grandezza coerente per uno studio preliminare."

    if max_thickness_cm is not None and thickness_cm > max_thickness_cm:
        status = "Fuori scala / non consigliato"
        note = "Lo spessore preliminare supera il limite geometrico impostato."
        warnings.append(
            f"Spessore proposto {thickness_cm} cm > limite disponibile {max_thickness_cm:.0f} cm."
        )
        return {
            "status": status,
            "note": note,
            "warnings": warnings,
            "span_to_thickness_ratio": round(ratio, 2),
        }

    if ratio <= plausible_limit:
        status = "Plausibile"
        note = "Ordine di grandezza coerente per uno studio preliminare."
    elif ratio <= attention_limit:
        status = "Da verificare con attenzione"
        note = "Spessore possibile ma relativamente tirato."
        warnings.append("Rapporto luce/spessore vicino a un campo da valutare con più attenzione.")
    else:
        status = "Fuori scala / non consigliato"
        note = "Spessore troppo ridotto per un predimensionamento prudente."
        warnings.append("Rapporto luce/spessore eccessivo rispetto a una stima cautelativa.")

    return {
        "status": status,
        "note": note,
        "warnings": warnings,
        "span_to_thickness_ratio": round(ratio, 2),
    }


def calculate_slab_preliminary(data: SlabInput) -> SlabResult:
    _validate_input(data)

    preset = get_usage_preset(data.usage_key)

    thickness_cm = _estimate_initial_thickness_cm(data.span_m, data.slab_type)

    self_weight_kN_m2 = _calc_self_weight_kN_m2(
        thickness_cm=thickness_cm,
        concrete_density_kN_m3=data.concrete_density_kN_m3,
    )

    adopted_surface_load_kN_m2 = _calc_surface_load_kN_m2(
        structural_dead_load_kN_m2=data.structural_dead_load_kN_m2,
        non_structural_dead_load_kN_m2=preset.dead_load_non_structural_kN_m2,
        live_load_kN_m2=preset.live_load_kN_m2,
        self_weight_kN_m2=self_weight_kN_m2,
    )

    max_moment_kNm_per_m = _calc_max_moment_kNm_per_m(
        span_m=data.span_m,
        surface_load_kN_m2=adopted_surface_load_kN_m2,
        slab_type=data.slab_type,
    )

    if max_moment_kNm_per_m > 35:
        thickness_cm += 2
    if max_moment_kNm_per_m > 50:
        thickness_cm += 2

    thickness_cm = _round_up_to_2(thickness_cm)

    self_weight_kN_m2 = _calc_self_weight_kN_m2(
        thickness_cm=thickness_cm,
        concrete_density_kN_m3=data.concrete_density_kN_m3,
    )

    adopted_surface_load_kN_m2 = _calc_surface_load_kN_m2(
        structural_dead_load_kN_m2=data.structural_dead_load_kN_m2,
        non_structural_dead_load_kN_m2=preset.dead_load_non_structural_kN_m2,
        live_load_kN_m2=preset.live_load_kN_m2,
        self_weight_kN_m2=self_weight_kN_m2,
    )

    max_moment_kNm_per_m = _calc_max_moment_kNm_per_m(
        span_m=data.span_m,
        surface_load_kN_m2=adopted_surface_load_kN_m2,
        slab_type=data.slab_type,
    )

    classification = _classify_result(
        span_m=data.span_m,
        thickness_cm=thickness_cm,
        max_thickness_cm=data.max_thickness_cm,
        slab_type=data.slab_type,
    )

    return SlabResult(
        element="Soletta",
        material="Calcestruzzo armato",
        usage=preset.label,
        span_m=round(data.span_m, 2),
        slab_type=data.slab_type,
        thickness_cm=thickness_cm,
        self_weight_kN_m2=round(self_weight_kN_m2, 2),
        adopted_surface_load_kN_m2=round(adopted_surface_load_kN_m2, 2),
        max_moment_kNm_per_m=round(max_moment_kNm_per_m, 2),
        span_to_thickness_ratio=classification["span_to_thickness_ratio"],
        status=classification["status"],
        note=classification["note"],
        warnings=classification["warnings"],
    )