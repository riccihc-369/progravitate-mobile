from dataclasses import dataclass
from typing import List, Optional

from presets import get_usage_preset
from beam_engine_steel import SteelBeamInput, calculate_steel_beam_preliminary
from beam_engine_timber import TimberBeamInput, calculate_timber_beam_preliminary
from column_engine import ColumnInput, calculate_column_preliminary


@dataclass
class SystemLightInput:
    length_m: float
    width_m: float

    floor_type: str  # "manual", "timber", "concrete"
    slab_dead_load_kN_m2: float

    usage_key: str

    beam_material: str = "steel"   # "steel" oppure "timber"
    column_material: str = "steel"

    beam_max_height_mm: Optional[float] = None
    beam_max_height_cm: Optional[float] = None
    column_max_section_cm: Optional[float] = None


@dataclass
class SystemLightBeamSummary:
    label: str
    count: int
    material: str
    span_m: float
    tributary_width_m: float
    line_load_kN_m: float

    section_name: str
    section_family: str

    section_height_mm: float
    section_width_mm: float

    max_moment_kNm: float
    max_shear_kN: float
    status: str
    note: str
    warnings: List[str]


@dataclass
class SystemLightColumnSummary:
    count: int
    axial_load_per_column_kN: float
    section_width_cm: int
    section_depth_cm: int
    slenderness_ratio: float
    status: str
    note: str
    warnings: List[str]


@dataclass
class SystemLightResult:
    system_type: str
    usage: str

    length_m: float
    width_m: float
    area_m2: float

    floor_type: str
    floor_label: str
    slab_dead_load_kN_m2: float

    beam_material: str
    beam_material_label: str

    non_structural_dead_load_kN_m2: float
    live_load_kN_m2: float
    total_surface_load_kN_m2: float
    total_load_kN: float

    long_beams: SystemLightBeamSummary
    short_beams: SystemLightBeamSummary
    columns: SystemLightColumnSummary

    status: str
    note: str
    warnings: List[str]


def _validate_input(data: SystemLightInput) -> None:
    if data.length_m <= 0:
        raise ValueError("La lunghezza deve essere maggiore di zero.")

    if data.width_m <= 0:
        raise ValueError("La larghezza deve essere maggiore di zero.")

    if data.floor_type not in {"manual", "timber", "concrete"}:
        raise ValueError("floor_type deve essere 'manual', 'timber' oppure 'concrete'.")

    if data.slab_dead_load_kN_m2 <= 0:
        raise ValueError("Il peso proprio del piano/soletta deve essere maggiore di zero.")

    if data.beam_material not in {"steel", "timber"}:
        raise ValueError("beam_material deve essere 'steel' oppure 'timber'.")

    if data.column_material != "steel":
        raise ValueError("Questa versione supporta solo pilastri nel motore attuale.")

    if data.beam_max_height_mm is not None and data.beam_max_height_mm <= 0:
        raise ValueError("L'altezza massima trave in mm deve essere maggiore di zero.")

    if data.beam_max_height_cm is not None and data.beam_max_height_cm <= 0:
        raise ValueError("L'altezza massima trave in cm deve essere maggiore di zero.")

    if data.column_max_section_cm is not None and data.column_max_section_cm <= 0:
        raise ValueError("La sezione massima pilastro deve essere maggiore di zero.")


def _resolve_floor_label(floor_type: str) -> str:
    if floor_type == "manual":
        return "Peso manuale equivalente"
    if floor_type == "timber":
        return "Piano leggero in legno"
    return "Soletta in calcestruzzo armato"


def _resolve_beam_material_label(beam_material: str) -> str:
    if beam_material == "steel":
        return "Acciaio"
    return "Legno"


def _surface_load_components(
    usage_key: str,
    slab_dead_load_kN_m2: float,
) -> tuple[float, float, float, float]:
    preset = get_usage_preset(usage_key)
    non_structural = preset.dead_load_non_structural_kN_m2
    live = preset.live_load_kN_m2
    total = slab_dead_load_kN_m2 + non_structural + live
    return slab_dead_load_kN_m2, non_structural, live, total


def _build_steel_beam_summary(
    label: str,
    count: int,
    span_m: float,
    tributary_width_m: float,
    usage_key: str,
    beam_max_height_mm: Optional[float],
) -> SystemLightBeamSummary:
    result = calculate_steel_beam_preliminary(
        SteelBeamInput(
            span_m=span_m,
            support_type="simply_supported",
            usage_key=usage_key,
            load_mode="automatic",
            tributary_width_m=tributary_width_m,
            max_height_mm=beam_max_height_mm,
        )
    )

    return SystemLightBeamSummary(
        label=label,
        count=count,
        material="Acciaio",
        span_m=round(span_m, 2),
        tributary_width_m=round(tributary_width_m, 2),
        line_load_kN_m=round(result.adopted_line_load_kN_m, 2),
        section_name=result.section_name,
        section_family=result.section_family,
        section_height_mm=result.section_height_mm,
        section_width_mm=result.section_width_mm,
        max_moment_kNm=result.max_moment_kNm,
        max_shear_kN=result.max_shear_kN,
        status=result.status,
        note=result.note,
        warnings=result.warnings,
    )


def _build_timber_beam_summary(
    label: str,
    count: int,
    span_m: float,
    tributary_width_m: float,
    usage_key: str,
    beam_max_height_cm: Optional[float],
) -> SystemLightBeamSummary:
    result = calculate_timber_beam_preliminary(
        TimberBeamInput(
            span_m=span_m,
            support_type="simply_supported",
            usage_key=usage_key,
            load_mode="automatic",
            tributary_width_m=tributary_width_m,
            max_height_cm=beam_max_height_cm,
        )
    )

    return SystemLightBeamSummary(
        label=label,
        count=count,
        material="Legno",
        span_m=round(span_m, 2),
        tributary_width_m=round(tributary_width_m, 2),
        line_load_kN_m=round(result.adopted_line_load_kN_m, 2),
        section_name=result.section_name,
        section_family=result.timber_type,
        section_height_mm=result.section_h_cm * 10.0,
        section_width_mm=result.section_b_cm * 10.0,
        max_moment_kNm=result.max_moment_kNm,
        max_shear_kN=result.max_shear_kN,
        status=result.status,
        note=result.note,
        warnings=result.warnings,
    )


def _build_beam_summary(
    label: str,
    count: int,
    span_m: float,
    tributary_width_m: float,
    usage_key: str,
    beam_material: str,
    beam_max_height_mm: Optional[float],
    beam_max_height_cm: Optional[float],
) -> SystemLightBeamSummary:
    if beam_material == "steel":
        return _build_steel_beam_summary(
            label=label,
            count=count,
            span_m=span_m,
            tributary_width_m=tributary_width_m,
            usage_key=usage_key,
            beam_max_height_mm=beam_max_height_mm,
        )

    return _build_timber_beam_summary(
        label=label,
        count=count,
        span_m=span_m,
        tributary_width_m=tributary_width_m,
        usage_key=usage_key,
        beam_max_height_cm=beam_max_height_cm,
    )


def _column_axial_load_from_perimeter_beams(
    long_beam_line_load_kN_m: float,
    long_beam_span_m: float,
    short_beam_line_load_kN_m: float,
    short_beam_span_m: float,
) -> float:
    long_reaction = long_beam_line_load_kN_m * long_beam_span_m / 2.0
    short_reaction = short_beam_line_load_kN_m * short_beam_span_m / 2.0
    return long_reaction + short_reaction


def _build_column_summary(
    axial_load_per_column_kN: float,
    column_max_section_cm: Optional[float],
) -> SystemLightColumnSummary:
    column_result = calculate_column_preliminary(
        ColumnInput(
            free_height_m=3.0,
            usage_key="residential",
            load_mode="manual",
            manual_axial_load_kN=axial_load_per_column_kN,
            floors_supported=1,
            max_section_cm=column_max_section_cm,
        )
    )

    return SystemLightColumnSummary(
        count=4,
        axial_load_per_column_kN=round(axial_load_per_column_kN, 2),
        section_width_cm=column_result.section_width_cm,
        section_depth_cm=column_result.section_depth_cm,
        slenderness_ratio=column_result.slenderness_ratio,
        status=column_result.status,
        note=column_result.note,
        warnings=column_result.warnings,
    )


def _combine_statuses(statuses: List[str]) -> str:
    joined = " | ".join(statuses).lower()

    if "non compatibile geometricamente" in joined:
        return "Non compatibile geometricamente"
    if "fuori scala" in joined:
        return "Fuori scala / non consigliato"
    if "da verificare" in joined:
        return "Da verificare con attenzione"
    return "Plausibile"


def calculate_system_light(data: SystemLightInput) -> SystemLightResult:
    _validate_input(data)

    preset = get_usage_preset(data.usage_key)

    floor_label = _resolve_floor_label(data.floor_type)
    beam_material_label = _resolve_beam_material_label(data.beam_material)

    slab_dead, non_structural, live, total_surface = _surface_load_components(
        usage_key=data.usage_key,
        slab_dead_load_kN_m2=data.slab_dead_load_kN_m2,
    )

    area_m2 = data.length_m * data.width_m
    total_load_kN = total_surface * area_m2

    long_beams = _build_beam_summary(
        label="Travi lunghe",
        count=2,
        span_m=data.length_m,
        tributary_width_m=data.width_m / 2.0,
        usage_key=data.usage_key,
        beam_material=data.beam_material,
        beam_max_height_mm=data.beam_max_height_mm,
        beam_max_height_cm=data.beam_max_height_cm,
    )

    short_beams = _build_beam_summary(
        label="Travi corte",
        count=2,
        span_m=data.width_m,
        tributary_width_m=data.length_m / 2.0,
        usage_key=data.usage_key,
        beam_material=data.beam_material,
        beam_max_height_mm=data.beam_max_height_mm,
        beam_max_height_cm=data.beam_max_height_cm,
    )

    axial_load_per_column_kN = _column_axial_load_from_perimeter_beams(
        long_beam_line_load_kN_m=long_beams.line_load_kN_m,
        long_beam_span_m=long_beams.span_m,
        short_beam_line_load_kN_m=short_beams.line_load_kN_m,
        short_beam_span_m=short_beams.span_m,
    )

    columns = _build_column_summary(
        axial_load_per_column_kN=axial_load_per_column_kN,
        column_max_section_cm=data.column_max_section_cm,
    )

    warnings: List[str] = []
    warnings.extend([f"{long_beams.label}: {w}" for w in long_beams.warnings])
    warnings.extend([f"{short_beams.label}: {w}" for w in short_beams.warnings])
    warnings.extend([f"Pilastri: {w}" for w in columns.warnings])

    status = _combine_statuses(
        [
            long_beams.status,
            short_beams.status,
            columns.status,
        ]
    )

    if status == "Plausibile":
        note = "Sistema preliminarmente coerente per uno studio rapido."
    elif status == "Da verificare con attenzione":
        note = "Sistema possibile ma con alcuni elementi da approfondire."
    elif status == "Non compatibile geometricamente":
        note = "Uno o più elementi superano i limiti geometrici impostati."
    else:
        note = "Uno o più elementi risultano fuori scala per una stima prudente."

    return SystemLightResult(
        system_type="Piattaforma rettangolare su 4 travi perimetrali e 4 pilastri",
        usage=preset.label,
        length_m=round(data.length_m, 2),
        width_m=round(data.width_m, 2),
        area_m2=round(area_m2, 2),
        floor_type=data.floor_type,
        floor_label=floor_label,
        slab_dead_load_kN_m2=round(slab_dead, 2),
        beam_material=data.beam_material,
        beam_material_label=beam_material_label,
        non_structural_dead_load_kN_m2=round(non_structural, 2),
        live_load_kN_m2=round(live, 2),
        total_surface_load_kN_m2=round(total_surface, 2),
        total_load_kN=round(total_load_kN, 2),
        long_beams=long_beams,
        short_beams=short_beams,
        columns=columns,
        status=status,
        note=note,
        warnings=warnings,
    )