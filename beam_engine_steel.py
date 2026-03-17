import math
from dataclasses import dataclass
from typing import List, Optional

from presets import get_usage_preset
from steel_sections import SteelSection, get_all_sections


@dataclass
class SteelBeamInput:
    span_m: float
    support_type: str  # "simply_supported" oppure "continuous"
    usage_key: str
    load_mode: str  # "automatic" oppure "manual"
    tributary_width_m: Optional[float] = None
    manual_line_load_kN_m: Optional[float] = None
    max_height_mm: Optional[float] = None


@dataclass
class SteelBeamResult:
    element: str
    material: str
    usage: str
    span_m: float
    support_type: str
    load_mode: str
    section_name: str
    section_family: str
    section_height_mm: float
    section_width_mm: float
    self_weight_kN_m: float
    adopted_line_load_kN_m: float
    max_moment_kNm: float
    max_shear_kN: float
    required_W_cm3: float
    section_W_cm3: float
    section_I_cm4: float
    estimated_deflection_mm: float
    status: str
    note: str
    warnings: List[str]


def _validate_input(data: SteelBeamInput) -> None:
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

    if data.max_height_mm is not None and data.max_height_mm <= 0:
        raise ValueError("L'altezza massima deve essere maggiore di zero.")


def _calc_line_load_from_surface(usage_key: str, tributary_width_m: float) -> float:
    preset = get_usage_preset(usage_key)
    structural_dead_load_kN_m2 = 3.0
    total_surface_load = (
        structural_dead_load_kN_m2
        + preset.dead_load_non_structural_kN_m2
        + preset.live_load_kN_m2
    )
    return total_surface_load * tributary_width_m


def _calc_internal_forces(span_m: float, line_load_kN_m: float, support_type: str) -> tuple[float, float]:
    if support_type == "simply_supported":
        max_moment_kNm = line_load_kN_m * span_m**2 / 8.0
        max_shear_kN = line_load_kN_m * span_m / 2.0
    else:
        max_moment_kNm = line_load_kN_m * span_m**2 / 12.0
        max_shear_kN = line_load_kN_m * span_m / 2.0

    return max_moment_kNm, max_shear_kN


def _required_W_cm3(max_moment_kNm: float) -> float:
    """
    Stima molto semplificata:
    Wreq = M / sigma_amm
    con sigma_amm preliminare prudenziale ~ 160 MPa
    """
    sigma_amm_N_mm2 = 160.0
    moment_Nmm = max_moment_kNm * 1_000_000.0
    w_req_mm3 = moment_Nmm / sigma_amm_N_mm2
    return w_req_mm3 / 1000.0  # mm3 -> cm3


def _estimate_deflection_mm(
    span_m: float,
    line_load_kN_m: float,
    section_I_cm4: float,
    support_type: str,
) -> float:
    """
    Stima preliminare deformabilità.
    E acciaio = 210000 N/mm²
    q convertito in N/mm
    I convertito in mm4
    """
    E = 210_000.0
    q_N_mm = line_load_kN_m
    L_mm = span_m * 1000.0
    I_mm4 = section_I_cm4 * 10_000.0

    if support_type == "simply_supported":
        delta = (5 * q_N_mm * (L_mm**4)) / (384 * E * I_mm4)
    else:
        delta = (q_N_mm * (L_mm**4)) / (185 * E * I_mm4)

    return delta


def _section_weight_to_kN_m(weight_kg_m: float) -> float:
    return weight_kg_m * 9.81 / 1000.0


def _select_section(
    sections: List[SteelSection],
    required_W_cm3: float,
    max_height_mm: Optional[float],
) -> Optional[SteelSection]:
    for section in sections:
        if max_height_mm is not None and section.h_mm > max_height_mm:
            continue
        if section.W_cm3 >= required_W_cm3:
            return section
    return None


def _classify_result(
    section: SteelSection,
    max_height_mm: Optional[float],
    estimated_deflection_mm: float,
    span_m: float,
) -> tuple[str, str, List[str]]:
    warnings: List[str] = []

    if max_height_mm is not None and section.h_mm > max_height_mm:
        return (
            "Non compatibile geometricamente",
            "Il profilo selezionato supera il limite di altezza disponibile.",
            [f"Profilo {section.name} con altezza {section.h_mm:.0f} mm > limite disponibile {max_height_mm:.0f} mm."],
        )

    limit_mm = (span_m * 1000.0) / 300.0

    if estimated_deflection_mm <= limit_mm:
        return (
            "Plausibile",
            "Ordine di grandezza coerente per uno studio preliminare.",
            warnings,
        )

    if estimated_deflection_mm <= (span_m * 1000.0) / 250.0:
        warnings.append("Deformabilità da verificare con maggiore attenzione.")
        return (
            "Da verificare con attenzione",
            "Profilo possibile ma con deformabilità relativamente sensibile.",
            warnings,
        )

    warnings.append("Deformabilità eccessiva rispetto a una stima preliminare cautelativa.")
    return (
        "Fuori scala / non consigliato",
        "Profilo troppo cedevole per un predimensionamento prudente.",
        warnings,
    )


def calculate_steel_beam_preliminary(data: SteelBeamInput) -> SteelBeamResult:
    _validate_input(data)

    preset = get_usage_preset(data.usage_key)

    if data.load_mode == "automatic":
        line_load_kN_m = _calc_line_load_from_surface(
            usage_key=data.usage_key,
            tributary_width_m=data.tributary_width_m or 0.0,
        )
    else:
        line_load_kN_m = data.manual_line_load_kN_m or 0.0

    max_moment_kNm, max_shear_kN = _calc_internal_forces(
        span_m=data.span_m,
        line_load_kN_m=line_load_kN_m,
        support_type=data.support_type,
    )

    required_w_cm3 = _required_W_cm3(max_moment_kNm)

    sections = get_all_sections()
    section = _select_section(
        sections=sections,
        required_W_cm3=required_w_cm3,
        max_height_mm=data.max_height_mm,
    )

    if section is None:
        raise ValueError("Nessun profilo disponibile soddisfa i criteri preliminari impostati.")

    self_weight_kN_m = _section_weight_to_kN_m(section.weight_kg_m)
    adopted_line_load_kN_m = line_load_kN_m + self_weight_kN_m

    max_moment_kNm, max_shear_kN = _calc_internal_forces(
        span_m=data.span_m,
        line_load_kN_m=adopted_line_load_kN_m,
        support_type=data.support_type,
    )

    required_w_cm3 = _required_W_cm3(max_moment_kNm)

    section = _select_section(
        sections=sections,
        required_W_cm3=required_w_cm3,
        max_height_mm=data.max_height_mm,
    )

    if section is None:
        raise ValueError("Nessun profilo disponibile soddisfa i criteri preliminari impostati dopo il ricalcolo del peso proprio.")

    self_weight_kN_m = _section_weight_to_kN_m(section.weight_kg_m)
    adopted_line_load_kN_m = line_load_kN_m + self_weight_kN_m

    max_moment_kNm, max_shear_kN = _calc_internal_forces(
        span_m=data.span_m,
        line_load_kN_m=adopted_line_load_kN_m,
        support_type=data.support_type,
    )

    required_w_cm3 = _required_W_cm3(max_moment_kNm)

    estimated_deflection_mm = _estimate_deflection_mm(
        span_m=data.span_m,
        line_load_kN_m=adopted_line_load_kN_m,
        section_I_cm4=section.I_cm4,
        support_type=data.support_type,
    )

    status, note, warnings = _classify_result(
        section=section,
        max_height_mm=data.max_height_mm,
        estimated_deflection_mm=estimated_deflection_mm,
        span_m=data.span_m,
    )

    return SteelBeamResult(
        element="Trave",
        material="Acciaio",
        usage=preset.label,
        span_m=round(data.span_m, 2),
        support_type=data.support_type,
        load_mode=data.load_mode,
        section_name=section.name,
        section_family=section.family,
        section_height_mm=section.h_mm,
        section_width_mm=section.b_mm,
        self_weight_kN_m=round(self_weight_kN_m, 2),
        adopted_line_load_kN_m=round(adopted_line_load_kN_m, 2),
        max_moment_kNm=round(max_moment_kNm, 2),
        max_shear_kN=round(max_shear_kN, 2),
        required_W_cm3=round(required_w_cm3, 2),
        section_W_cm3=section.W_cm3,
        section_I_cm4=section.I_cm4,
        estimated_deflection_mm=round(estimated_deflection_mm, 2),
        status=status,
        note=note,
        warnings=warnings,
    )