from __future__ import annotations

import inspect
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from presets import get_usage_labels

from beam_engine_steel import SteelBeamInput, calculate_steel_beam_preliminary
from beam_engine_timber import TimberBeamInput, calculate_timber_beam_preliminary


# =========================================================
# Input / Output
# =========================================================

@dataclass(frozen=True)
class SystemLightInput:
    length_m: float
    width_m: float
    floor_type: str                     # manual | timber | concrete
    slab_dead_load_kN_m2: float
    usage_key: str

    beam_material: str                  # steel | timber | concrete
    column_material: str = "concrete"   # concrete | steel | timber

    beam_max_height_mm: Optional[float] = None
    beam_max_height_cm: Optional[float] = None

    column_max_section_cm: Optional[float] = None


@dataclass(frozen=True)
class SystemBeamResult:
    material_label: str
    section_name: str
    family_label: str
    dimensions_label: str

    span_m: float
    tributary_width_m: float
    surface_line_load_kN_m: float
    self_weight_kN_m: float
    adopted_line_load_kN_m: float

    max_moment_kNm: float
    max_shear_kN: float

    status: str
    note: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SystemColumnResult:
    material_label: str
    section_name: str
    family_label: str
    dimensions_label: str

    axial_load_per_column_kN: float
    self_weight_kN: float

    slenderness_ratio: float
    stress_or_utilization: float

    status: str
    note: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SystemLightResult:
    usage: str
    floor_label: str
    beam_material_label: str
    column_material_label: str

    length_m: float
    width_m: float
    area_m2: float

    slab_dead_load_kN_m2: float
    non_structural_dead_load_kN_m2: float
    live_load_kN_m2: float
    total_surface_load_kN_m2: float
    total_load_kN: float

    long_beams: SystemBeamResult
    short_beams: SystemBeamResult
    columns: SystemColumnResult

    status: str
    note: str
    warnings: list[str] = field(default_factory=list)


# =========================================================
# Presets
# =========================================================

USAGE_LABELS = get_usage_labels()

USAGE_SURFACE_LOADS = {
    "residential": {
        "non_structural_dead_load_kN_m2": 2.00,
        "live_load_kN_m2": 2.00,
    },
    "balcony": {
        "non_structural_dead_load_kN_m2": 2.00,
        "live_load_kN_m2": 4.00,
    },
    "roof_walkable": {
        "non_structural_dead_load_kN_m2": 1.50,
        "live_load_kN_m2": 2.00,
    },
    "roof_not_walkable": {
        "non_structural_dead_load_kN_m2": 1.50,
        "live_load_kN_m2": 0.75,
    },
    "light_vehicle": {
        "non_structural_dead_load_kN_m2": 2.00,
        "live_load_kN_m2": 5.00,
    },
}

FLOOR_LABELS = {
    "manual": "Peso manuale equivalente",
    "timber": "Piano leggero in legno",
    "concrete": "Soletta in calcestruzzo armato",
}

BEAM_MATERIAL_LABELS = {
    "steel": "Acciaio",
    "timber": "Legno",
    "concrete": "Calcestruzzo armato",
}

COLUMN_MATERIAL_LABELS = {
    "steel": "Acciaio",
    "timber": "Legno",
    "concrete": "Calcestruzzo armato",
}


# Catalogo iniziale colonne acciaio (semplice e robusto)
STEEL_COLUMN_SECTIONS = [
    {"name": "HEA 100", "family": "HEA", "b_mm": 100, "h_mm": 96, "area_m2": 21.2e-4},
    {"name": "HEA 120", "family": "HEA", "b_mm": 120, "h_mm": 114, "area_m2": 25.3e-4},
    {"name": "HEA 140", "family": "HEA", "b_mm": 140, "h_mm": 133, "area_m2": 31.4e-4},
    {"name": "HEA 160", "family": "HEA", "b_mm": 160, "h_mm": 152, "area_m2": 38.8e-4},
    {"name": "HEA 180", "family": "HEA", "b_mm": 180, "h_mm": 171, "area_m2": 45.3e-4},
    {"name": "HEA 200", "family": "HEA", "b_mm": 200, "h_mm": 190, "area_m2": 53.8e-4},
    {"name": "HEA 220", "family": "HEA", "b_mm": 220, "h_mm": 210, "area_m2": 64.3e-4},
    {"name": "HEA 240", "family": "HEA", "b_mm": 240, "h_mm": 230, "area_m2": 76.8e-4},
]

# Catalogo iniziale colonne legno
TIMBER_COLUMN_SECTIONS = [
    {"name": "GL 14x14", "family": "Lamellare", "b_cm": 14, "h_cm": 14},
    {"name": "GL 16x16", "family": "Lamellare", "b_cm": 16, "h_cm": 16},
    {"name": "GL 18x18", "family": "Lamellare", "b_cm": 18, "h_cm": 18},
    {"name": "GL 20x20", "family": "Lamellare", "b_cm": 20, "h_cm": 20},
    {"name": "GL 22x22", "family": "Lamellare", "b_cm": 22, "h_cm": 22},
    {"name": "GL 24x24", "family": "Lamellare", "b_cm": 24, "h_cm": 24},
    {"name": "GL 26x26", "family": "Lamellare", "b_cm": 26, "h_cm": 26},
    {"name": "GL 28x28", "family": "Lamellare", "b_cm": 28, "h_cm": 28},
    {"name": "GL 30x30", "family": "Lamellare", "b_cm": 30, "h_cm": 30},
]


# =========================================================
# Helpers
# =========================================================

def _round_up(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step)


def _build_dataclass_input(cls: Any, candidate_kwargs: dict[str, Any]) -> Any:
    sig = inspect.signature(cls)
    accepted = {k: v for k, v in candidate_kwargs.items() if k in sig.parameters}
    return cls(**accepted)


def _status_family_from_text(status: str, note: str, warnings: list[str]) -> str:
    text = " ".join([status, note] + warnings).lower()

    if "limite geometrico" in text or "supera il limite" in text or "altezza disponibile" in text:
        return "Non compatibile geometricamente"
    if "fuori scala" in text:
        return "Fuori scala / non consigliato"
    if "da verificare" in text:
        return "Possibile ma da verificare"
    if "plausibile" in text:
        return "Plausibile"
    return status


def _system_status_from_parts(parts: list[str]) -> str:
    joined = " | ".join(parts).lower()

    if "non compatibile" in joined or "limite geometrico" in joined:
        return "Non compatibile geometricamente"
    if "fuori scala" in joined:
        return "Fuori scala / non consigliato"
    if "da verificare" in joined:
        return "Possibile ma da verificare"
    return "Plausibile"


# =========================================================
# Beam adapters
# =========================================================

def _calculate_steel_beam_for_system(
    usage_key: str,
    span_m: float,
    tributary_width_m: float,
    surface_line_load_kN_m: float,
    max_height_mm: Optional[float],
) -> SystemBeamResult:
    input_obj = _build_dataclass_input(
        SteelBeamInput,
        {
            "span_m": span_m,
            "support_type": "simply_supported",
            "usage_key": usage_key,
            "load_mode": "manual",
            "tributary_width_m": None,
            "manual_line_load_kN_m": surface_line_load_kN_m,
            "max_height_mm": max_height_mm,
        },
    )

    result = calculate_steel_beam_preliminary(input_obj)

    warnings = list(getattr(result, "warnings", []))
    status = _status_family_from_text(
        getattr(result, "status", "Plausibile"),
        getattr(result, "note", ""),
        warnings,
    )

    section_name = getattr(result, "section_name", "Profilo non definito")
    family = getattr(result, "family", getattr(result, "family_label", "Acciaio"))

    section_width_mm = getattr(result, "section_width_mm", None)
    section_height_mm = getattr(result, "section_height_mm", None)
    if section_width_mm is not None and section_height_mm is not None:
        dimensions_label = f"{section_width_mm:.0f} x {section_height_mm:.0f} mm"
    else:
        dimensions_label = section_name

    return SystemBeamResult(
        material_label="Acciaio",
        section_name=section_name,
        family_label=str(family),
        dimensions_label=dimensions_label,
        span_m=span_m,
        tributary_width_m=tributary_width_m,
        surface_line_load_kN_m=surface_line_load_kN_m,
        self_weight_kN_m=float(getattr(result, "self_weight_kN_m", 0.0)),
        adopted_line_load_kN_m=float(
            getattr(result, "adopted_line_load_kN_m", surface_line_load_kN_m)
        ),
        max_moment_kNm=float(getattr(result, "max_moment_kNm", 0.0)),
        max_shear_kN=float(getattr(result, "max_shear_kN", 0.0)),
        status=status,
        note=str(getattr(result, "note", "")),
        warnings=warnings,
    )


def _calculate_timber_beam_for_system(
    usage_key: str,
    span_m: float,
    tributary_width_m: float,
    surface_line_load_kN_m: float,
    max_height_cm: Optional[float],
) -> SystemBeamResult:
    input_obj = _build_dataclass_input(
        TimberBeamInput,
        {
            "span_m": span_m,
            "support_type": "simply_supported",
            "usage_key": usage_key,
            "load_mode": "manual",
            "tributary_width_m": None,
            "manual_line_load_kN_m": surface_line_load_kN_m,
            "max_height_cm": max_height_cm,
        },
    )

    result = calculate_timber_beam_preliminary(input_obj)

    warnings = list(getattr(result, "warnings", []))
    status = _status_family_from_text(
        getattr(result, "status", "Plausibile"),
        getattr(result, "note", ""),
        warnings,
    )

    section_name = getattr(result, "section_name", "Sezione non definita")
    timber_type = getattr(result, "timber_type", getattr(result, "family_label", "Legno"))

    b_cm = getattr(result, "section_b_cm", None)
    h_cm = getattr(result, "section_h_cm", None)
    if b_cm is not None and h_cm is not None:
        dimensions_label = f"{b_cm:.0f} x {h_cm:.0f} cm"
    else:
        dimensions_label = section_name

    return SystemBeamResult(
        material_label="Legno",
        section_name=section_name,
        family_label=str(timber_type),
        dimensions_label=dimensions_label,
        span_m=span_m,
        tributary_width_m=tributary_width_m,
        surface_line_load_kN_m=surface_line_load_kN_m,
        self_weight_kN_m=float(getattr(result, "self_weight_kN_m", 0.0)),
        adopted_line_load_kN_m=float(
            getattr(result, "adopted_line_load_kN_m", surface_line_load_kN_m)
        ),
        max_moment_kNm=float(getattr(result, "max_moment_kNm", 0.0)),
        max_shear_kN=float(getattr(result, "max_shear_kN", 0.0)),
        status=status,
        note=str(getattr(result, "note", "")),
        warnings=warnings,
    )


def _calculate_concrete_beam_for_system(
    span_m: float,
    tributary_width_m: float,
    surface_line_load_kN_m: float,
    max_height_cm: Optional[float],
) -> SystemBeamResult:
    warnings: list[str] = []

    h_req_cm = max(30, _round_up((span_m * 100.0) / 10.0, 5))
    b_req_cm = max(30, _round_up(h_req_cm * 0.50, 5))

    adopted_h_cm = h_req_cm
    if max_height_cm is not None and adopted_h_cm > max_height_cm:
        warnings.append(
            f"Altezza richiesta {h_req_cm} cm > altezza disponibile {max_height_cm:.0f} cm."
        )
        adopted_h_cm = int(max_height_cm)

    adopted_b_cm = max(30, _round_up(adopted_h_cm * 0.50, 5))

    self_weight_kN_m = 25.0 * (adopted_b_cm / 100.0) * (adopted_h_cm / 100.0)
    adopted_line_load_kN_m = surface_line_load_kN_m + self_weight_kN_m

    max_moment_kNm = adopted_line_load_kN_m * span_m**2 / 8.0
    max_shear_kN = adopted_line_load_kN_m * span_m / 2.0

    slenderness_ratio = span_m * 100.0 / adopted_h_cm if adopted_h_cm > 0 else 0.0
    base_height_ratio = adopted_b_cm / adopted_h_cm if adopted_h_cm > 0 else 0.0

    if max_height_cm is not None and h_req_cm > max_height_cm:
        status = "Non compatibile geometricamente"
        note = "La sezione preliminare supera il limite geometrico impostato."
    elif slenderness_ratio > 12.0:
        status = "Possibile ma da verificare"
        note = "Rapporto luce/altezza relativamente sensibile."
    else:
        status = "Plausibile"
        note = "Ordine di grandezza coerente per uno studio preliminare."

    return SystemBeamResult(
        material_label="Calcestruzzo armato",
        section_name=f"{adopted_b_cm}x{adopted_h_cm} cm",
        family_label="Trave in c.a.",
        dimensions_label=f"{adopted_b_cm} x {adopted_h_cm} cm",
        span_m=span_m,
        tributary_width_m=tributary_width_m,
        surface_line_load_kN_m=surface_line_load_kN_m,
        self_weight_kN_m=self_weight_kN_m,
        adopted_line_load_kN_m=adopted_line_load_kN_m,
        max_moment_kNm=max_moment_kNm,
        max_shear_kN=max_shear_kN,
        status=status,
        note=(
            f"{note} "
            f"Rapporto luce/altezza = {slenderness_ratio:.2f}. "
            f"Rapporto base/altezza = {base_height_ratio:.2f}."
        ),
        warnings=warnings,
    )


# =========================================================
# Column internal calculators
# =========================================================

def _calculate_concrete_columns_for_system(
    axial_load_per_column_kN: float,
    clear_height_m: float = 3.0,
    max_section_cm: Optional[float] = None,
) -> SystemColumnResult:
    warnings: list[str] = []

    target_stress_kN_m2 = 3500.0
    req_area_m2 = axial_load_per_column_kN / target_stress_kN_m2
    req_side_cm = _round_up(math.sqrt(req_area_m2) * 100.0, 5)
    req_side_cm = max(25, req_side_cm)

    adopted_side_cm = req_side_cm
    if max_section_cm is not None and adopted_side_cm > max_section_cm:
        warnings.append(
            f"Sezione proposta {req_side_cm} x {req_side_cm} cm > limite disponibile {max_section_cm:.0f} cm."
        )
        adopted_side_cm = int(max_section_cm)

    area_m2 = (adopted_side_cm / 100.0) ** 2
    stress_kN_m2 = axial_load_per_column_kN / area_m2 if area_m2 > 0 else 0.0

    slenderness_ratio = (clear_height_m * 100.0) / adopted_side_cm if adopted_side_cm > 0 else 0.0

    self_weight_kN = 25.0 * area_m2 * clear_height_m

    if max_section_cm is not None and req_side_cm > max_section_cm:
        status = "Non compatibile geometricamente"
        note = "La sezione preliminare supera il limite geometrico impostato."
    elif stress_kN_m2 > 3500.0 or slenderness_ratio > 15.0:
        status = "Possibile ma da verificare"
        note = "Pilastri da verificare con maggiore attenzione."
    else:
        status = "Plausibile"
        note = "Ordine di grandezza coerente per uno studio rapido."

    return SystemColumnResult(
        material_label="Calcestruzzo armato",
        section_name=f"{adopted_side_cm}x{adopted_side_cm} cm",
        family_label="Pilastro in c.a.",
        dimensions_label=f"{adopted_side_cm} x {adopted_side_cm} cm",
        axial_load_per_column_kN=axial_load_per_column_kN,
        self_weight_kN=self_weight_kN,
        slenderness_ratio=slenderness_ratio,
        stress_or_utilization=stress_kN_m2,
        status=status,
        note=note,
        warnings=warnings,
    )


def _calculate_steel_columns_for_system(
    axial_load_per_column_kN: float,
    clear_height_m: float = 3.0,
    max_section_cm: Optional[float] = None,
) -> SystemColumnResult:
    warnings: list[str] = []

    design_capacity_stress_kN_m2 = 120000.0  # molto semplificato per predimensionamento rapido

    selected = None
    for sec in STEEL_COLUMN_SECTIONS:
        max_dim_cm = max(sec["b_mm"], sec["h_mm"]) / 10.0
        if max_section_cm is not None and max_dim_cm > max_section_cm:
            continue

        capacity_kN = sec["area_m2"] * design_capacity_stress_kN_m2
        if capacity_kN >= axial_load_per_column_kN:
            selected = sec
            break

    if selected is None:
        selected = STEEL_COLUMN_SECTIONS[-1]
        max_dim_cm = max(selected["b_mm"], selected["h_mm"]) / 10.0
        if max_section_cm is not None and max_dim_cm > max_section_cm:
            warnings.append(
                f"Profilo proposto {selected['name']} > limite disponibile {max_section_cm:.0f} cm."
            )
        status = "Non compatibile geometricamente" if max_section_cm is not None else "Possibile ma da verificare"
        note = "Il profilo richiesto supera i limiti geometrici o di catalogo impostati."
    else:
        status = "Plausibile"
        note = "Ordine di grandezza coerente per uno studio rapido."

    area_m2 = selected["area_m2"]
    stress_kN_m2 = axial_load_per_column_kN / area_m2 if area_m2 > 0 else 0.0
    slenderness_ratio = (clear_height_m * 100.0) / (selected["h_mm"] / 10.0) if selected["h_mm"] > 0 else 0.0
    self_weight_kN = 78.5 * area_m2 * clear_height_m

    if slenderness_ratio > 20.0 and status == "Plausibile":
        status = "Possibile ma da verificare"
        note = "Snellezza preliminare da verificare con maggiore attenzione."

    return SystemColumnResult(
        material_label="Acciaio",
        section_name=selected["name"],
        family_label=selected["family"],
        dimensions_label=f"{selected['b_mm']} x {selected['h_mm']} mm",
        axial_load_per_column_kN=axial_load_per_column_kN,
        self_weight_kN=self_weight_kN,
        slenderness_ratio=slenderness_ratio,
        stress_or_utilization=stress_kN_m2,
        status=status,
        note=note,
        warnings=warnings,
    )


def _calculate_timber_columns_for_system(
    axial_load_per_column_kN: float,
    clear_height_m: float = 3.0,
    max_section_cm: Optional[float] = None,
) -> SystemColumnResult:
    warnings: list[str] = []

    design_capacity_stress_kN_m2 = 18000.0  # semplificato, rapido

    selected = None
    for sec in TIMBER_COLUMN_SECTIONS:
        max_dim_cm = max(sec["b_cm"], sec["h_cm"])
        if max_section_cm is not None and max_dim_cm > max_section_cm:
            continue

        area_m2 = (sec["b_cm"] / 100.0) * (sec["h_cm"] / 100.0)
        capacity_kN = area_m2 * design_capacity_stress_kN_m2
        if capacity_kN >= axial_load_per_column_kN:
            selected = sec
            break

    if selected is None:
        selected = TIMBER_COLUMN_SECTIONS[-1]
        max_dim_cm = max(selected["b_cm"], selected["h_cm"])
        if max_section_cm is not None and max_dim_cm > max_section_cm:
            warnings.append(
                f"Sezione proposta {selected['b_cm']} x {selected['h_cm']} cm > limite disponibile {max_section_cm:.0f} cm."
            )
        status = "Non compatibile geometricamente" if max_section_cm is not None else "Possibile ma da verificare"
        note = "La sezione richiesta supera i limiti geometrici o di catalogo impostati."
    else:
        status = "Plausibile"
        note = "Ordine di grandezza coerente per uno studio rapido."

    area_m2 = (selected["b_cm"] / 100.0) * (selected["h_cm"] / 100.0)
    stress_kN_m2 = axial_load_per_column_kN / area_m2 if area_m2 > 0 else 0.0
    slenderness_ratio = (clear_height_m * 100.0) / selected["h_cm"] if selected["h_cm"] > 0 else 0.0
    self_weight_kN = 5.0 * area_m2 * clear_height_m

    if slenderness_ratio > 18.0 and status == "Plausibile":
        status = "Possibile ma da verificare"
        note = "Snellezza preliminare da verificare con maggiore attenzione."

    return SystemColumnResult(
        material_label="Legno",
        section_name=selected["name"],
        family_label=selected["family"],
        dimensions_label=f"{selected['b_cm']} x {selected['h_cm']} cm",
        axial_load_per_column_kN=axial_load_per_column_kN,
        self_weight_kN=self_weight_kN,
        slenderness_ratio=slenderness_ratio,
        stress_or_utilization=stress_kN_m2,
        status=status,
        note=note,
        warnings=warnings,
    )


# =========================================================
# Main system calculation
# =========================================================

def calculate_system_light(data: SystemLightInput) -> SystemLightResult:
    if data.length_m <= 0 or data.width_m <= 0:
        raise ValueError("Le dimensioni del sistema devono essere > 0.")

    if data.usage_key not in USAGE_SURFACE_LOADS:
        raise ValueError(f"Uso non gestito: {data.usage_key}")

    if data.floor_type not in FLOOR_LABELS:
        raise ValueError(f"Tipologia piano non gestita: {data.floor_type}")

    if data.beam_material not in BEAM_MATERIAL_LABELS:
        raise ValueError(f"Materiale travi non gestito: {data.beam_material}")

    if data.column_material not in COLUMN_MATERIAL_LABELS:
        raise ValueError(f"Materiale pilastri non gestito: {data.column_material}")

    usage_label = USAGE_LABELS.get(data.usage_key, data.usage_key)
    floor_label = FLOOR_LABELS[data.floor_type]
    beam_material_label = BEAM_MATERIAL_LABELS[data.beam_material]
    column_material_label = COLUMN_MATERIAL_LABELS[data.column_material]

    area_m2 = data.length_m * data.width_m

    non_structural_dead_load_kN_m2 = USAGE_SURFACE_LOADS[data.usage_key]["non_structural_dead_load_kN_m2"]
    live_load_kN_m2 = USAGE_SURFACE_LOADS[data.usage_key]["live_load_kN_m2"]

    total_surface_load_kN_m2 = (
        data.slab_dead_load_kN_m2
        + non_structural_dead_load_kN_m2
        + live_load_kN_m2
    )
    total_load_kN = total_surface_load_kN_m2 * area_m2

    # piattaforma rettangolare su 4 travi perimetrali appoggiate e 4 pilastri angolari
    long_span_m = data.length_m
    short_span_m = data.width_m

    long_tributary_width_m = data.width_m / 2.0
    short_tributary_width_m = data.length_m / 2.0

    long_surface_line_load_kN_m = total_surface_load_kN_m2 * long_tributary_width_m
    short_surface_line_load_kN_m = total_surface_load_kN_m2 * short_tributary_width_m

    # -------- beams
    if data.beam_material == "steel":
        long_beams = _calculate_steel_beam_for_system(
            usage_key=data.usage_key,
            span_m=long_span_m,
            tributary_width_m=long_tributary_width_m,
            surface_line_load_kN_m=long_surface_line_load_kN_m,
            max_height_mm=data.beam_max_height_mm,
        )
        short_beams = _calculate_steel_beam_for_system(
            usage_key=data.usage_key,
            span_m=short_span_m,
            tributary_width_m=short_tributary_width_m,
            surface_line_load_kN_m=short_surface_line_load_kN_m,
            max_height_mm=data.beam_max_height_mm,
        )

    elif data.beam_material == "timber":
        long_beams = _calculate_timber_beam_for_system(
            usage_key=data.usage_key,
            span_m=long_span_m,
            tributary_width_m=long_tributary_width_m,
            surface_line_load_kN_m=long_surface_line_load_kN_m,
            max_height_cm=data.beam_max_height_cm,
        )
        short_beams = _calculate_timber_beam_for_system(
            usage_key=data.usage_key,
            span_m=short_span_m,
            tributary_width_m=short_tributary_width_m,
            surface_line_load_kN_m=short_surface_line_load_kN_m,
            max_height_cm=data.beam_max_height_cm,
        )

    else:
        concrete_hmax_cm = data.beam_max_height_cm
        if concrete_hmax_cm is None and data.beam_max_height_mm is not None:
            concrete_hmax_cm = data.beam_max_height_mm / 10.0

        long_beams = _calculate_concrete_beam_for_system(
            span_m=long_span_m,
            tributary_width_m=long_tributary_width_m,
            surface_line_load_kN_m=long_surface_line_load_kN_m,
            max_height_cm=concrete_hmax_cm,
        )
        short_beams = _calculate_concrete_beam_for_system(
            span_m=short_span_m,
            tributary_width_m=short_tributary_width_m,
            surface_line_load_kN_m=short_surface_line_load_kN_m,
            max_height_cm=concrete_hmax_cm,
        )

    # -------- columns
    axial_load_per_column_kN = (
        0.5 * long_beams.adopted_line_load_kN_m * long_span_m
        + 0.5 * short_beams.adopted_line_load_kN_m * short_span_m
    )

    if data.column_material == "steel":
        columns = _calculate_steel_columns_for_system(
            axial_load_per_column_kN=axial_load_per_column_kN,
            clear_height_m=3.0,
            max_section_cm=data.column_max_section_cm,
        )
    elif data.column_material == "timber":
        columns = _calculate_timber_columns_for_system(
            axial_load_per_column_kN=axial_load_per_column_kN,
            clear_height_m=3.0,
            max_section_cm=data.column_max_section_cm,
        )
    else:
        columns = _calculate_concrete_columns_for_system(
            axial_load_per_column_kN=axial_load_per_column_kN,
            clear_height_m=3.0,
            max_section_cm=data.column_max_section_cm,
        )

    all_warnings = list(long_beams.warnings) + list(short_beams.warnings) + list(columns.warnings)

    overall_status = _system_status_from_parts(
        [
            long_beams.status,
            short_beams.status,
            columns.status,
            long_beams.note,
            short_beams.note,
            columns.note,
        ]
    )

    if "Non compatibile" in overall_status:
        overall_note = "Uno o più elementi non risultano compatibili con i limiti geometrici impostati."
    elif "Fuori scala" in overall_status:
        overall_note = "Uno o più elementi risultano fuori scala per il sistema assunto."
    elif "verificare" in overall_status.lower():
        overall_note = "Sistema possibile ma da verificare con maggiore attenzione."
    else:
        overall_note = "Sistema preliminarmente coerente per uno studio rapido."

    return SystemLightResult(
        usage=usage_label,
        floor_label=floor_label,
        beam_material_label=beam_material_label,
        column_material_label=column_material_label,
        length_m=data.length_m,
        width_m=data.width_m,
        area_m2=area_m2,
        slab_dead_load_kN_m2=data.slab_dead_load_kN_m2,
        non_structural_dead_load_kN_m2=non_structural_dead_load_kN_m2,
        live_load_kN_m2=live_load_kN_m2,
        total_surface_load_kN_m2=total_surface_load_kN_m2,
        total_load_kN=total_load_kN,
        long_beams=long_beams,
        short_beams=short_beams,
        columns=columns,
        status=overall_status,
        note=overall_note,
        warnings=all_warnings,
    )