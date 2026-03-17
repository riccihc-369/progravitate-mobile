from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class UsagePreset:
    """
    Preset di carico semplificato per utilizzo.

    Valori in kN/m².
    """
    key: str
    label: str
    dead_load_non_structural_kN_m2: float
    live_load_kN_m2: float
    note: str


USAGE_PRESETS: Dict[str, UsagePreset] = {
    "residential": UsagePreset(
        key="residential",
        label="Abitazione",
        dead_load_non_structural_kN_m2=2.0,
        live_load_kN_m2=2.0,
        note="Uso residenziale ordinario.",
    ),
    "balcony": UsagePreset(
        key="balcony",
        label="Balcone",
        dead_load_non_structural_kN_m2=2.5,
        live_load_kN_m2=4.0,
        note="Balcone o terrazza con carico variabile aumentato.",
    ),
    "roof_walkable": UsagePreset(
        key="roof_walkable",
        label="Copertura praticabile",
        dead_load_non_structural_kN_m2=2.0,
        live_load_kN_m2=2.0,
        note="Copertura praticabile ordinaria.",
    ),
    "roof_not_walkable": UsagePreset(
        key="roof_not_walkable",
        label="Copertura non praticabile",
        dead_load_non_structural_kN_m2=1.5,
        live_load_kN_m2=0.75,
        note="Copertura non praticabile con carichi ridotti.",
    ),
    "light_vehicle": UsagePreset(
        key="light_vehicle",
        label="Carrabile leggera",
        dead_load_non_structural_kN_m2=3.0,
        live_load_kN_m2=5.0,
        note="Area carrabile leggera, da affinare in fase successiva.",
    ),
}


def get_usage_preset(key: str) -> UsagePreset:
    """
    Restituisce il preset associato alla chiave.
    """
    if key not in USAGE_PRESETS:
        available = ", ".join(USAGE_PRESETS.keys())
        raise KeyError(f"Preset '{key}' non trovato. Valori disponibili: {available}")
    return USAGE_PRESETS[key]


def get_usage_labels() -> Dict[str, str]:
    """
    Restituisce mappa {key: label} utile per UI.
    """
    return {key: preset.label for key, preset in USAGE_PRESETS.items()}