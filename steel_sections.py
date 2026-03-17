from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SteelSection:
    name: str
    family: str
    h_mm: float
    b_mm: float
    weight_kg_m: float
    W_cm3: float
    I_cm4: float


STEEL_SECTIONS: List[SteelSection] = [
    # IPE
    SteelSection("IPE 160", "IPE", 160, 82, 15.8, 142, 1130),
    SteelSection("IPE 180", "IPE", 180, 91, 18.8, 194, 1750),
    SteelSection("IPE 200", "IPE", 200, 100, 22.4, 253, 2530),
    SteelSection("IPE 220", "IPE", 220, 110, 26.2, 317, 3490),
    SteelSection("IPE 240", "IPE", 240, 120, 30.7, 392, 4700),
    SteelSection("IPE 270", "IPE", 270, 135, 36.1, 508, 6860),
    SteelSection("IPE 300", "IPE", 300, 150, 42.2, 628, 9420),
    SteelSection("IPE 330", "IPE", 330, 160, 49.1, 771, 12700),
    SteelSection("IPE 360", "IPE", 360, 170, 57.1, 925, 16600),

    # HEA
    SteelSection("HEA 160", "HEA", 152, 160, 30.4, 311, 2360),
    SteelSection("HEA 180", "HEA", 171, 180, 35.5, 426, 3640),
    SteelSection("HEA 200", "HEA", 190, 200, 42.3, 554, 5260),
    SteelSection("HEA 220", "HEA", 210, 220, 50.5, 712, 7470),
    SteelSection("HEA 240", "HEA", 230, 240, 60.3, 891, 10200),
    SteelSection("HEA 260", "HEA", 250, 260, 68.2, 1048, 13100),
    SteelSection("HEA 280", "HEA", 270, 280, 76.4, 1223, 16500),
    SteelSection("HEA 300", "HEA", 290, 300, 88.3, 1426, 20700),

    # HEB
    SteelSection("HEB 160", "HEB", 160, 160, 42.6, 450, 3600),
    SteelSection("HEB 180", "HEB", 180, 180, 51.2, 604, 5430),
    SteelSection("HEB 200", "HEB", 200, 200, 61.3, 781, 7810),
    SteelSection("HEB 220", "HEB", 220, 220, 71.5, 990, 10900),
    SteelSection("HEB 240", "HEB", 240, 240, 83.2, 1227, 14700),
    SteelSection("HEB 260", "HEB", 260, 260, 93.0, 1459, 19000),
    SteelSection("HEB 280", "HEB", 280, 280, 103.0, 1709, 23900),
    SteelSection("HEB 300", "HEB", 300, 300, 117.0, 2000, 30300),
]


def get_sections_by_family(family: str) -> List[SteelSection]:
    return [section for section in STEEL_SECTIONS if section.family == family]


def get_all_sections() -> List[SteelSection]:
    return list(STEEL_SECTIONS)