import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from presets import get_usage_preset


MIN_COLUMN_SIDE_CM = 25


@dataclass
class ColumnInput:
    """
    Input semplificato per predimensionamento pilastro in c.a.
    """
    free_height_m: float
    usage_key: str
    load_mode: str  # "tributary_area" oppure "manual"
    tributary_area_m2: Optional[float] = None
    floors_supported: int = 1
    manual_axial_load_kN: Optional[float] = None
    max_section_cm: Optional[float] = None
    concrete_density_kN_m3: float = 25.0


@dataclass
class ColumnResult:
    element: str
    material: str
    usage: str
    free_height_m: float
    load_mode: str
    floors_supported: int
    section_width_cm: int
    section_depth_cm: int
    self_weight_kN: float
    adopted_axial_load_kN: float
    estimated_surface_load_kN_m2: float
    manual_axial_load_kN: float
    slenderness_ratio: float
    stress_kN_m2: float
    status: str
    note: str
    warnings: List[str]


def _round_up_to_5(value_cm: float) -> int:
    return int(math.ceil(value_cm / 5.0) * 5)


def _validate_input(data: ColumnInput) -> None:
    if data.free_height_m <= 0:
        raise ValueError("L'altezza libera deve essere maggiore di zero.")

    if data.load_mode not in {"tributary_area", "manual"}:
        raise ValueError("load_mode deve essere 'tributary_area' oppure 'manual'.")

    if data.floors_supported < 1:
        raise ValueError("Il numero di piani caricanti deve essere almeno 1.")

    if data.load_mode == "tributary_area":
        if data.tributary_area_m2 is None or data.tributary_area_m2 <= 0:
            raise ValueError("In modalità area tributaria devi inserire una superficie > 0.")
    else:
        if data.manual_axial_load_kN is None or data.manual_axial_load_kN <= 0:
            raise ValueError("In modalità manuale devi inserire un carico assiale > 0.")

    if data.max_section_cm is not None and data.max_section_cm <= 0:
        raise ValueError("La sezione massima deve essere maggiore di zero.")

    if data.concrete_density_kN_m3 <= 0:
        raise ValueError("La densità del calcestruzzo deve essere maggiore di zero.")


def _estimate_surface_load_from_usage(usage_key: str) -> float:
    """
    Somma semplificata dei carichi superficiali da preset.
    Aggiunge una quota strutturale prudenziale.
    """
    preset = get_usage_preset(usage_key)
    structural_dead_load_kN_m2 = 3.5
    return (
        structural_dead_load_kN_m2
        + preset.dead_load_non_structural_kN_m2
        + preset.live_load_kN_m2
    )


def _estimate_initial_section_cm(adopted_axial_load_kN: float) -> int:
    """
    Stima molto semplice della sezione quadrata.
    Range prudenziale da studio preliminare.
    """
    if adopted_axial_load_kN <= 250:
        return 30
    if adopted_axial_load_kN <= 500:
        return 35
    if adopted_axial_load_kN <= 800:
        return 40
    if adopted_axial_load_kN <= 1200:
        return 45
    return 50


def _calc_column_self_weight_kN(
    side_cm: float,
    free_height_m: float,
    concrete_density_kN_m3: float,
) -> float:
    side_m = side_cm / 100.0
    volume_m3 = side_m * side_m * free_height_m
    return volume_m3 * concrete_density_kN_m3


def _classify_result(
    free_height_m: float,
    section_width_cm: int,
    section_depth_cm: int,
    adopted_axial_load_kN: float,
    max_section_cm: Optional[float],
) -> Dict[str, Any]:
    warnings: List[str] = []

    min_side_cm = min(section_width_cm, section_depth_cm)
    area_m2 = (section_width_cm / 100.0) * (section_depth_cm / 100.0)
    stress_kN_m2 = adopted_axial_load_kN / area_m2

    slenderness_ratio = (free_height_m * 100.0) / min_side_cm

    status = "Plausibile"
    note = "Ordine di grandezza coerente per uno studio preliminare."

    if max_section_cm is not None and max(section_width_cm, section_depth_cm) > max_section_cm:
        status = "Fuori scala / non consigliato"
        note = "La sezione preliminare supera il limite geometrico impostato."
        warnings.append(
            f"Sezione proposta {section_width_cm} x {section_depth_cm} cm > limite disponibile {max_section_cm:.0f} cm."
        )
        return {
            "status": status,
            "note": note,
            "warnings": warnings,
            "slenderness_ratio": round(slenderness_ratio, 2),
            "stress_kN_m2": round(stress_kN_m2, 2),
        }

    if slenderness_ratio > 14:
        status = "Da verificare con attenzione"
        note = "Pilastro relativamente snello per una stima preliminare."
        warnings.append("Rapporto di snellezza da verificare con maggiore attenzione.")
    elif slenderness_ratio > 18:
        status = "Fuori scala / non consigliato"
        note = "Pilastro troppo snello per un predimensionamento prudente."
        warnings.append("Snellezza eccessiva rispetto a una stima cautelativa.")

    if min_side_cm < MIN_COLUMN_SIDE_CM:
        status = "Fuori scala / non consigliato"
        note = "Sezione troppo ridotta per un pilastro in c.a. ordinario."
        warnings.append("Lato minimo pilastro inferiore alla soglia minima prudenziale.")

    return {
        "status": status,
        "note": note,
        "warnings": warnings,
        "slenderness_ratio": round(slenderness_ratio, 2),
        "stress_kN_m2": round(stress_kN_m2, 2),
    }


def calculate_column_preliminary(data: ColumnInput) -> ColumnResult:
    _validate_input(data)

    preset = get_usage_preset(data.usage_key)

    estimated_surface_load_kN_m2 = 0.0
    manual_axial_load_kN = 0.0

    if data.load_mode == "tributary_area":
        estimated_surface_load_kN_m2 = _estimate_surface_load_from_usage(data.usage_key)
        adopted_axial_load_kN = estimated_surface_load_kN_m2 * (data.tributary_area_m2 or 0.0) * data.floors_supported
    else:
        manual_axial_load_kN = data.manual_axial_load_kN or 0.0
        adopted_axial_load_kN = manual_axial_load_kN

    side_cm = _estimate_initial_section_cm(adopted_axial_load_kN)

    if data.max_section_cm is not None and side_cm > data.max_section_cm:
        side_cm = _round_up_to_5(side_cm)

    self_weight_kN = _calc_column_self_weight_kN(
        side_cm=side_cm,
        free_height_m=data.free_height_m,
        concrete_density_kN_m3=data.concrete_density_kN_m3,
    )

    adopted_axial_load_kN += self_weight_kN

    # mini-iterazione dopo aggiunta peso proprio
    side_cm = _estimate_initial_section_cm(adopted_axial_load_kN)
    self_weight_kN = _calc_column_self_weight_kN(
        side_cm=side_cm,
        free_height_m=data.free_height_m,
        concrete_density_kN_m3=data.concrete_density_kN_m3,
    )

    final_axial_load_kN = (
        manual_axial_load_kN + self_weight_kN
        if data.load_mode == "manual"
        else estimated_surface_load_kN_m2 * (data.tributary_area_m2 or 0.0) * data.floors_supported + self_weight_kN
    )

    classification = _classify_result(
        free_height_m=data.free_height_m,
        section_width_cm=side_cm,
        section_depth_cm=side_cm,
        adopted_axial_load_kN=final_axial_load_kN,
        max_section_cm=data.max_section_cm,
    )

    return ColumnResult(
        element="Pilastro",
        material="Calcestruzzo armato",
        usage=preset.label,
        free_height_m=round(data.free_height_m, 2),
        load_mode=data.load_mode,
        floors_supported=data.floors_supported,
        section_width_cm=side_cm,
        section_depth_cm=side_cm,
        self_weight_kN=round(self_weight_kN, 2),
        adopted_axial_load_kN=round(final_axial_load_kN, 2),
        estimated_surface_load_kN_m2=round(estimated_surface_load_kN_m2, 2),
        manual_axial_load_kN=round(manual_axial_load_kN, 2),
        slenderness_ratio=classification["slenderness_ratio"],
        stress_kN_m2=classification["stress_kN_m2"],
        status=classification["status"],
        note=classification["note"],
        warnings=classification["warnings"],
    )