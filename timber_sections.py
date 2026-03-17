from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TimberSection:
    name: str
    timber_type: str  # "lamellare" oppure "massiccio"
    b_cm: float
    h_cm: float
    area_cm2: float
    W_cm3: float
    I_cm4: float


def _rect_props(b_cm: float, h_cm: float) -> tuple[float, float, float]:
    area_cm2 = b_cm * h_cm
    W_cm3 = b_cm * (h_cm ** 2) / 6.0
    I_cm4 = b_cm * (h_cm ** 3) / 12.0
    return area_cm2, W_cm3, I_cm4


def _make_section(name: str, timber_type: str, b_cm: float, h_cm: float) -> TimberSection:
    area_cm2, W_cm3, I_cm4 = _rect_props(b_cm, h_cm)
    return TimberSection(
        name=name,
        timber_type=timber_type,
        b_cm=b_cm,
        h_cm=h_cm,
        area_cm2=area_cm2,
        W_cm3=W_cm3,
        I_cm4=I_cm4,
    )


TIMBER_SECTIONS: List[TimberSection] = [
    # Lamellare
    _make_section("GL 10x24", "lamellare", 10, 24),
    _make_section("GL 12x28", "lamellare", 12, 28),
    _make_section("GL 14x32", "lamellare", 14, 32),
    _make_section("GL 16x36", "lamellare", 16, 36),
    _make_section("GL 18x40", "lamellare", 18, 40),
    _make_section("GL 20x44", "lamellare", 20, 44),
    _make_section("GL 22x48", "lamellare", 22, 48),
    _make_section("GL 24x52", "lamellare", 24, 52),

    # Massiccio
    _make_section("MS 8x20", "massiccio", 8, 20),
    _make_section("MS 10x24", "massiccio", 10, 24),
    _make_section("MS 12x28", "massiccio", 12, 28),
    _make_section("MS 14x32", "massiccio", 14, 32),
    _make_section("MS 16x36", "massiccio", 16, 36),
    _make_section("MS 18x40", "massiccio", 18, 40),
    _make_section("MS 20x44", "massiccio", 20, 44),
]


def get_sections_by_type(timber_type: str) -> List[TimberSection]:
    return [section for section in TIMBER_SECTIONS if section.timber_type == timber_type]


def get_all_sections() -> List[TimberSection]:
    return list(TIMBER_SECTIONS)