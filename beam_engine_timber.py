import math
from dataclasses import dataclass
from typing import List, Optional

from presets import get_usage_preset
from timber_sections import TimberSection, get_all_sections


@dataclass
class TimberBeamInput:
    span_m: float
    support_type: str  # "simply_supported" oppure "continuous"
    usage_key: str
    load_mode: str  # "automatic" oppure "manual"
    tributary_width_m: Optional[float] = None
    manual_line_load_kN_m: Optional[float] = None
    max_height_cm: Optional[float] = None


@dataclass
class TimberBeamResult:
    element: str
    material: str
    timber_type: str
    usage: str
    span_m: float
    support_type: str
    load_mode: str
    section_name: str
    section_b_cm: float
    section_h_cm: float
    self_weight_kN_m: float
    adopted_line_load_kN_m: float
    max_moment_kNm: float
    max_shear_kN: float
    required_W_cm3: float
    section_W_cm3: float
    section_I_cm4: float
    estimated_deflection_mm: float
    slenderness_ratio_l_over_h: float
    status: str
    note: str
    warnings: List[str]


def _validate_input(data: TimberBeamInput) -> None:
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

    if data.max_height_cm is not None and data.max_height_cm <= 0:
        raise ValueError("L'altezza massima deve essere maggiore di zero.")


def _timber_density_kN_m3(timber_type: str) -> float:
    if timber_type == "lamellare":
        return 4.5
    return 5.0


def _timber_sigma_amm_N_mm2(timber_type: str) -> float:
    if timber_type == "lamellare":
        return 16.0
    return 12.0


def _timber_E_N_mm2(timber_type: str) -> float:
    if timber_type == "lamellare":
        return 11000.0
    return 9000.0


def _calc_line_load_from_surface(usage_key: str, tributary_width_m: float) -> float:
    preset = get_usage_preset(usage_key)
    structural_dead_load_kN_m2 = 2.5
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


def _required_W_cm3(max_moment_kNm: float, timber_type: str) -> float:
    sigma_amm_N_mm2 = _timber_sigma_amm_N_mm2(timber_type)
    moment_Nmm = max_moment_kNm * 1_000_000.0
    w_req_mm3 = moment_Nmm / sigma_amm_N_mm2
    return w_req_mm3 / 1000.0  # mm3 -> cm3


def _calc_self_weight_kN_m(section: TimberSection) -> float:
    density = _timber_density_kN_m3(section.timber_type)
    area_m2 = section.area_cm2 / 10_000.0
    return area_m2 * density


def _estimate_deflection_mm(
    span_m: float,
    line_load_kN_m: float,
    section: TimberSection,
    support_type: str,
) -> float:
    E = _timber_E_N_mm2(section.timber_type)
    q_N_mm = line_load_kN_m
    L_mm = span_m * 1000.0
    I_mm4 = section.I_cm4 * 10_000.0

    if support_type == "simply_supported":
        delta = (5 * q_N_mm * (L_mm**4)) / (384 * E * I_mm4)
    else:
        delta = (q_N_mm * (L_mm**4)) / (185 * E * I_mm4)

    return delta


def _allowed_deflection_mm(span_m: float) -> float:
    return (span_m * 1000.0) / 300.0


def _sort_sections_for_selection(sections: List[TimberSection]) -> List[TimberSection]:
    order = {"lamellare": 0, "massiccio": 1}
    return sorted(
        sections,
        key=lambda s: (order.get(s.timber_type, 99), s.h_cm, s.b_cm),
    )


def _select_section(
    sections: List[TimberSection],
    span_m: float,
    support_type: str,
    base_line_load_kN_m: float,
    max_height_cm: Optional[float],
) -> Optional[tuple[TimberSection, float, float, float, float]]:
    """
    Restituisce la prima sezione che soddisfa:
    - modulo resistente richiesto
    - altezza massima, se presente
    - deformabilità preliminare
    """
    ordered_sections = _sort_sections_for_selection(sections)

    for section in ordered_sections:
        if max_height_cm is not None and section.h_cm > max_height_cm:
            continue

        self_weight_kN_m = _calc_self_weight_kN_m(section)
        adopted_line_load_kN_m = base_line_load_kN_m + self_weight_kN_m

        max_moment_kNm, max_shear_kN = _calc_internal_forces(
            span_m=span_m,
            line_load_kN_m=adopted_line_load_kN_m,
            support_type=support_type,
        )

        required_w_cm3 = _required_W_cm3(
            max_moment_kNm=max_moment_kNm,
            timber_type=section.timber_type,
        )

        if section.W_cm3 < required_w_cm3:
            continue

        estimated_deflection_mm = _estimate_deflection_mm(
            span_m=span_m,
            line_load_kN_m=adopted_line_load_kN_m,
            section=section,
            support_type=support_type,
        )

        if estimated_deflection_mm <= _allowed_deflection_mm(span_m):
            return (
                section,
                self_weight_kN_m,
                adopted_line_load_kN_m,
                max_moment_kNm,
                max_shear_kN,
            )

    return None


def _fallback_section_by_strength(
    sections: List[TimberSection],
    span_m: float,
    support_type: str,
    base_line_load_kN_m: float,
    max_height_cm: Optional[float],
) -> Optional[tuple[TimberSection, float, float, float, float, float]]:
    """
    Se nessuna sezione passa anche la deformabilità, restituisce la prima che passa la flessione.
    """
    ordered_sections = _sort_sections_for_selection(sections)

    for section in ordered_sections:
        if max_height_cm is not None and section.h_cm > max_height_cm:
            continue

        self_weight_kN_m = _calc_self_weight_kN_m(section)
        adopted_line_load_kN_m = base_line_load_kN_m + self_weight_kN_m

        max_moment_kNm, max_shear_kN = _calc_internal_forces(
            span_m=span_m,
            line_load_kN_m=adopted_line_load_kN_m,
            support_type=support_type,
        )

        required_w_cm3 = _required_W_cm3(
            max_moment_kNm=max_moment_kNm,
            timber_type=section.timber_type,
        )

        if section.W_cm3 < required_w_cm3:
            continue

        estimated_deflection_mm = _estimate_deflection_mm(
            span_m=span_m,
            line_load_kN_m=adopted_line_load_kN_m,
            section=section,
            support_type=support_type,
        )

        return (
            section,
            self_weight_kN_m,
            adopted_line_load_kN_m,
            max_moment_kNm,
            max_shear_kN,
            estimated_deflection_mm,
        )

    return None


def _classify_result(
    section: TimberSection,
    max_height_cm: Optional[float],
    estimated_deflection_mm: float,
    span_m: float,
) -> tuple[str, str, List[str], float]:
    warnings: List[str] = []

    if max_height_cm is not None and section.h_cm > max_height_cm:
        return (
            "Non compatibile geometricamente",
            "La sezione selezionata supera il limite di altezza disponibile.",
            [f"Sezione {section.name} con altezza {section.h_cm:.0f} cm > limite disponibile {max_height_cm:.0f} cm."],
            round((span_m * 100.0) / section.h_cm, 2),
        )

    limit_mm = _allowed_deflection_mm(span_m)
    slenderness_ratio = (span_m * 100.0) / section.h_cm

    if estimated_deflection_mm <= limit_mm:
        return (
            "Plausibile",
            "Ordine di grandezza coerente per uno studio preliminare.",
            warnings,
            round(slenderness_ratio, 2),
        )

    if estimated_deflection_mm <= (span_m * 1000.0) / 250.0:
        warnings.append("Deformabilità da verificare con maggiore attenzione.")
        return (
            "Da verificare con attenzione",
            "Sezione possibile ma con deformabilità relativamente sensibile.",
            warnings,
            round(slenderness_ratio, 2),
        )

    warnings.append("Deformabilità eccessiva rispetto a una stima preliminare cautelativa.")
    return (
        "Fuori scala / non consigliato",
        "Sezione troppo cedevole per un predimensionamento prudente.",
        warnings,
        round(slenderness_ratio, 2),
    )


def calculate_timber_beam_preliminary(data: TimberBeamInput) -> TimberBeamResult:
    _validate_input(data)

    preset = get_usage_preset(data.usage_key)

    if data.load_mode == "automatic":
        base_line_load_kN_m = _calc_line_load_from_surface(
            usage_key=data.usage_key,
            tributary_width_m=data.tributary_width_m or 0.0,
        )
    else:
        base_line_load_kN_m = data.manual_line_load_kN_m or 0.0

    sections = get_all_sections()

    selected = _select_section(
        sections=sections,
        span_m=data.span_m,
        support_type=data.support_type,
        base_line_load_kN_m=base_line_load_kN_m,
        max_height_cm=data.max_height_cm,
    )

    if selected is not None:
        section, self_weight_kN_m, adopted_line_load_kN_m, max_moment_kNm, max_shear_kN = selected
        estimated_deflection_mm = _estimate_deflection_mm(
            span_m=data.span_m,
            line_load_kN_m=adopted_line_load_kN_m,
            section=section,
            support_type=data.support_type,
        )
    else:
        fallback = _fallback_section_by_strength(
            sections=sections,
            span_m=data.span_m,
            support_type=data.support_type,
            base_line_load_kN_m=base_line_load_kN_m,
            max_height_cm=data.max_height_cm,
        )

        if fallback is None:
            raise ValueError("Nessuna sezione in legno disponibile soddisfa i criteri preliminari impostati.")

        section, self_weight_kN_m, adopted_line_load_kN_m, max_moment_kNm, max_shear_kN, estimated_deflection_mm = fallback

    required_w_cm3 = _required_W_cm3(
        max_moment_kNm=max_moment_kNm,
        timber_type=section.timber_type,
    )

    status, note, warnings, slenderness_ratio = _classify_result(
        section=section,
        max_height_cm=data.max_height_cm,
        estimated_deflection_mm=estimated_deflection_mm,
        span_m=data.span_m,
    )

    material_label = "Legno"
    timber_type_label = "Lamellare" if section.timber_type == "lamellare" else "Massiccio"

    return TimberBeamResult(
        element="Trave",
        material=material_label,
        timber_type=timber_type_label,
        usage=preset.label,
        span_m=round(data.span_m, 2),
        support_type=data.support_type,
        load_mode=data.load_mode,
        section_name=section.name,
        section_b_cm=section.b_cm,
        section_h_cm=section.h_cm,
        self_weight_kN_m=round(self_weight_kN_m, 2),
        adopted_line_load_kN_m=round(adopted_line_load_kN_m, 2),
        max_moment_kNm=round(max_moment_kNm, 2),
        max_shear_kN=round(max_shear_kN, 2),
        required_W_cm3=round(required_w_cm3, 2),
        section_W_cm3=round(section.W_cm3, 2),
        section_I_cm4=round(section.I_cm4, 2),
        estimated_deflection_mm=round(estimated_deflection_mm, 2),
        slenderness_ratio_l_over_h=slenderness_ratio,
        status=status,
        note=note,
        warnings=warnings,
    )