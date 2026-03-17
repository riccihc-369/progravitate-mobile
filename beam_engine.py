import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from presets import get_usage_preset


MIN_BEAM_WIDTH_CM = 25
PREFERRED_MIN_BEAM_WIDTH_CM = 30


@dataclass
class BeamInput:
    """
    Input semplificato per predimensionamento trave in c.a.
    """
    span_m: float
    support_type: str  # "simply_supported" oppure "continuous"
    usage_key: str
    load_mode: str  # "automatic" oppure "manual"
    tributary_width_m: Optional[float] = None
    manual_line_load_kN_m: Optional[float] = None
    beam_width_cm: Optional[float] = None
    max_height_cm: Optional[float] = None
    structural_dead_load_kN_m2: float = 3.5
    concrete_density_kN_m3: float = 25.0


@dataclass
class BeamResult:
    element: str
    material: str
    usage: str
    span_m: float
    support_type: str
    load_mode: str
    beam_width_cm: int
    beam_height_cm: int
    self_weight_kN_m: float
    adopted_line_load_kN_m: float
    line_load_from_surface_kN_m: float
    manual_line_load_kN_m: float
    max_moment_kNm: float
    max_shear_kN: float
    slenderness_ratio_l_over_h: float
    width_to_height_ratio: float
    status: str
    note: str
    warnings: List[str]


def _validate_input(data: BeamInput) -> None:
    if data.span_m <= 0:
        raise ValueError("La luce deve essere maggiore di zero.")

    if data.support_type not in {"simply_supported", "continuous"}:
        raise ValueError("support_type deve essere 'simply_supported' oppure 'continuous'.")

    if data.load_mode not in {"automatic", "manual"}:
        raise ValueError("load_mode deve essere 'automatic' oppure 'manual'.")

    if data.load_mode == "automatic":
        if data.tributary_width_m is None or data.tributary_width_m <= 0:
            raise ValueError("In modalità automatica devi inserire una larghezza tributaria > 0.")
    else:
        if data.manual_line_load_kN_m is None or data.manual_line_load_kN_m <= 0:
            raise ValueError("In modalità manuale devi inserire un carico lineare > 0.")

    if data.tributary_width_m is not None and data.tributary_width_m < 0:
        raise ValueError("La larghezza tributaria non può essere negativa.")

    if data.manual_line_load_kN_m is not None and data.manual_line_load_kN_m < 0:
        raise ValueError("Il carico lineare manuale non può essere negativo.")

    if data.beam_width_cm is not None and data.beam_width_cm <= 0:
        raise ValueError("La larghezza trave deve essere maggiore di zero.")

    if data.max_height_cm is not None and data.max_height_cm <= 0:
        raise ValueError("L'altezza massima deve essere maggiore di zero.")

    if data.structural_dead_load_kN_m2 < 0:
        raise ValueError("Il carico permanente strutturale non può essere negativo.")

    if data.concrete_density_kN_m3 <= 0:
        raise ValueError("La densità del calcestruzzo deve essere maggiore di zero.")


def _round_up_to_5(value_cm: float) -> int:
    return int(math.ceil(value_cm / 5.0) * 5)


def _estimate_initial_height_cm(span_m: float, support_type: str) -> int:
    span_cm = span_m * 100.0

    if support_type == "simply_supported":
        raw_h = span_cm / 10.0
    else:
        raw_h = span_cm / 12.0

    raw_h = max(raw_h, 25.0)
    return _round_up_to_5(raw_h)


def _default_beam_width_cm(height_cm: float) -> int:
    if height_cm <= 60:
        return 30
    if height_cm <= 80:
        return 35
    return 40


def _recommended_min_width_from_height(height_cm: float) -> int:
    """
    Regola semplice per evitare travi troppo strette:
    - almeno 25 cm assoluti
    - almeno circa h/2, arrotondato a 5 cm
    - mai sotto 30 cm come soglia preferibile per casi ordinari
    """
    from_height = _round_up_to_5(height_cm / 2.0)
    return max(MIN_BEAM_WIDTH_CM, PREFERRED_MIN_BEAM_WIDTH_CM, from_height)


def _normalize_beam_width_cm(user_width_cm: Optional[float], height_cm: int) -> Dict[str, Any]:
    warnings: List[str] = []

    recommended_min = _recommended_min_width_from_height(height_cm)

    if user_width_cm is None:
        width_cm = max(_default_beam_width_cm(height_cm), recommended_min)
        return {
            "beam_width_cm": width_cm,
            "warnings": warnings,
        }

    requested_width = _round_up_to_5(user_width_cm)

    if requested_width < MIN_BEAM_WIDTH_CM:
        warnings.append(
            f"Larghezza inserita troppo ridotta ({requested_width} cm): adottato minimo tecnico di {recommended_min} cm."
        )
        width_cm = recommended_min
    elif requested_width < recommended_min:
        warnings.append(
            f"Larghezza inserita {requested_width} cm considerata troppo bassa rispetto all'altezza della trave: adottati {recommended_min} cm."
        )
        width_cm = recommended_min
    else:
        width_cm = requested_width

    return {
        "beam_width_cm": width_cm,
        "warnings": warnings,
    }


def _calc_self_weight_kN_m(
    beam_width_cm: float,
    beam_height_cm: float,
    concrete_density_kN_m3: float,
) -> float:
    width_m = beam_width_cm / 100.0
    height_m = beam_height_cm / 100.0
    area_m2 = width_m * height_m
    return area_m2 * concrete_density_kN_m3


def _calc_line_load_from_surface(
    structural_dead_load_kN_m2: float,
    non_structural_dead_load_kN_m2: float,
    live_load_kN_m2: float,
    tributary_width_m: float,
) -> float:
    total_surface_load = (
        structural_dead_load_kN_m2
        + non_structural_dead_load_kN_m2
        + live_load_kN_m2
    )
    return total_surface_load * tributary_width_m


def _calc_internal_forces(
    span_m: float,
    line_load_kN_m: float,
    support_type: str,
) -> Dict[str, float]:
    if support_type == "simply_supported":
        max_moment_kNm = line_load_kN_m * span_m**2 / 8.0
        max_shear_kN = line_load_kN_m * span_m / 2.0
    else:
        max_moment_kNm = line_load_kN_m * span_m**2 / 12.0
        max_shear_kN = line_load_kN_m * span_m / 2.0

    return {
        "max_moment_kNm": max_moment_kNm,
        "max_shear_kN": max_shear_kN,
    }


def _classify_result(
    span_m: float,
    beam_width_cm: int,
    beam_height_cm: int,
    max_height_cm: Optional[float],
    support_type: str,
    existing_warnings: List[str],
) -> Dict[str, Any]:
    warnings = list(existing_warnings)

    span_cm = span_m * 100.0
    slenderness = span_cm / beam_height_cm
    width_to_height_ratio = beam_width_cm / beam_height_cm

    if support_type == "simply_supported":
        plausible_limit = 10.5
        attention_limit = 12.0
    else:
        plausible_limit = 12.5
        attention_limit = 14.0

    status = "Plausibile"
    note = "Predimensionamento preliminare da affinare in fase di verifica strutturale."

    if max_height_cm is not None and beam_height_cm > max_height_cm:
        overflow = beam_height_cm - max_height_cm
        status = "Fuori scala / non consigliato"
        note = "L'altezza preliminare supera il limite geometrico impostato."
        warnings.append(
            f"Altezza proposta {beam_height_cm} cm > limite disponibile {max_height_cm:.0f} cm."
        )
        if overflow >= 10:
            warnings.append(
                "La differenza è significativa: valutare schema statico, materiale o appoggio intermedio."
            )
        return {
            "status": status,
            "note": note,
            "warnings": warnings,
            "slenderness_ratio_l_over_h": round(slenderness, 2),
            "width_to_height_ratio": round(width_to_height_ratio, 2),
        }

    if width_to_height_ratio < 0.40:
        warnings.append(
            "Base trave ridotta rispetto all'altezza: valutare una sezione più equilibrata."
        )
        if status == "Plausibile":
            status = "Da verificare con attenzione"

    if slenderness <= plausible_limit:
        if status == "Plausibile":
            note = "Ordine di grandezza coerente per uno studio preliminare."
    elif slenderness <= attention_limit:
        status = "Da verificare con attenzione"
        note = "La sezione appare possibile ma relativamente tirata."
        warnings.append(
            "Rapporto luce/altezza vicino a un campo da valutare con maggiore attenzione."
        )
    else:
        status = "Fuori scala / non consigliato"
        note = "La sezione risulta troppo tirata per un predimensionamento prudente."
        warnings.append(
            "Rapporto luce/altezza eccessivo rispetto a una stima preliminare cautelativa."
        )

    return {
        "status": status,
        "note": note,
        "warnings": warnings,
        "slenderness_ratio_l_over_h": round(slenderness, 2),
        "width_to_height_ratio": round(width_to_height_ratio, 2),
    }


def calculate_beam_preliminary(data: BeamInput) -> BeamResult:
    _validate_input(data)

    preset = get_usage_preset(data.usage_key)

    estimated_height_cm = _estimate_initial_height_cm(data.span_m, data.support_type)

    width_info = _normalize_beam_width_cm(data.beam_width_cm, estimated_height_cm)
    beam_width_cm = width_info["beam_width_cm"]
    geometry_warnings = width_info["warnings"]

    self_weight_kN_m = _calc_self_weight_kN_m(
        beam_width_cm=beam_width_cm,
        beam_height_cm=estimated_height_cm,
        concrete_density_kN_m3=data.concrete_density_kN_m3,
    )

    line_load_from_surface_kN_m = 0.0
    manual_line_load_kN_m = 0.0

    if data.load_mode == "automatic":
        line_load_from_surface_kN_m = _calc_line_load_from_surface(
            structural_dead_load_kN_m2=data.structural_dead_load_kN_m2,
            non_structural_dead_load_kN_m2=preset.dead_load_non_structural_kN_m2,
            live_load_kN_m2=preset.live_load_kN_m2,
            tributary_width_m=data.tributary_width_m or 0.0,
        )
    else:
        manual_line_load_kN_m = data.manual_line_load_kN_m or 0.0

    adopted_line_load_kN_m = line_load_from_surface_kN_m + manual_line_load_kN_m + self_weight_kN_m

    internal_forces = _calc_internal_forces(
        span_m=data.span_m,
        line_load_kN_m=adopted_line_load_kN_m,
        support_type=data.support_type,
    )

    adjusted_height_cm = estimated_height_cm
    if internal_forces["max_moment_kNm"] > 250:
        adjusted_height_cm += 10
    elif internal_forces["max_moment_kNm"] > 180:
        adjusted_height_cm += 5

    adjusted_height_cm = _round_up_to_5(adjusted_height_cm)

    if adjusted_height_cm != estimated_height_cm:
        width_info = _normalize_beam_width_cm(data.beam_width_cm, adjusted_height_cm)
        beam_width_cm = width_info["beam_width_cm"]
        geometry_warnings = width_info["warnings"]

        self_weight_kN_m = _calc_self_weight_kN_m(
            beam_width_cm=beam_width_cm,
            beam_height_cm=adjusted_height_cm,
            concrete_density_kN_m3=data.concrete_density_kN_m3,
        )
        adopted_line_load_kN_m = line_load_from_surface_kN_m + manual_line_load_kN_m + self_weight_kN_m
        internal_forces = _calc_internal_forces(
            span_m=data.span_m,
            line_load_kN_m=adopted_line_load_kN_m,
            support_type=data.support_type,
        )

    classification = _classify_result(
        span_m=data.span_m,
        beam_width_cm=beam_width_cm,
        beam_height_cm=adjusted_height_cm,
        max_height_cm=data.max_height_cm,
        support_type=data.support_type,
        existing_warnings=geometry_warnings,
    )

    return BeamResult(
        element="Trave",
        material="Calcestruzzo armato",
        usage=preset.label,
        span_m=round(data.span_m, 2),
        support_type=data.support_type,
        load_mode=data.load_mode,
        beam_width_cm=beam_width_cm,
        beam_height_cm=adjusted_height_cm,
        self_weight_kN_m=round(self_weight_kN_m, 2),
        adopted_line_load_kN_m=round(adopted_line_load_kN_m, 2),
        line_load_from_surface_kN_m=round(line_load_from_surface_kN_m, 2),
        manual_line_load_kN_m=round(manual_line_load_kN_m, 2),
        max_moment_kNm=round(internal_forces["max_moment_kNm"], 2),
        max_shear_kN=round(internal_forces["max_shear_kN"], 2),
        slenderness_ratio_l_over_h=classification["slenderness_ratio_l_over_h"],
        width_to_height_ratio=classification["width_to_height_ratio"],
        status=classification["status"],
        note=classification["note"],
        warnings=classification["warnings"],
    )


def result_to_dict(result: BeamResult) -> Dict[str, Any]:
    return asdict(result)