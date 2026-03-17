import streamlit as st

from beam_engine import BeamInput, calculate_beam_preliminary
from beam_engine_steel import SteelBeamInput, calculate_steel_beam_preliminary
from beam_engine_timber import TimberBeamInput, calculate_timber_beam_preliminary
from slab_engine import SlabInput, calculate_slab_preliminary
from column_engine import ColumnInput, calculate_column_preliminary
from lintel_engine import LintelInput, calculate_lintel_preliminary
from system_light_engine import SystemLightInput, calculate_system_light
from presets import get_usage_labels


st.set_page_config(
    page_title="PROGravitate — V1.0-D",
    layout="centered",
)

st.title("PROGravitate")
st.caption("Predimensionamento strutturale preliminare — V1.0-D")

ALL_USAGE_LABELS = get_usage_labels()

ELEMENT_USAGE_MAP = {
    "Trave": [
        "residential",
        "balcony",
        "roof_walkable",
        "roof_not_walkable",
        "light_vehicle",
    ],
    "Soletta": [
        "residential",
        "balcony",
        "roof_walkable",
        "roof_not_walkable",
        "light_vehicle",
    ],
    "Pilastro": [
        "residential",
        "light_vehicle",
        "roof_walkable",
        "roof_not_walkable",
    ],
    "Architrave": [
        "residential",
        "balcony",
        "roof_walkable",
        "roof_not_walkable",
    ],
    "Sistema rapido": [
        "residential",
        "balcony",
        "roof_walkable",
        "roof_not_walkable",
        "light_vehicle",
    ],
}


def get_allowed_usage_keys(element: str) -> list[str]:
    return ELEMENT_USAGE_MAP.get(element, list(ALL_USAGE_LABELS.keys()))


def infer_governing_reason(status: str, note: str, warnings: list[str]) -> str:
    text = " ".join([status, note] + warnings).lower()

    if "limite geometrico" in text or "limite disponibile" in text or "altezza disponibile" in text:
        return "Limite geometrico"
    if "snellezza" in text:
        return "Snellezza"
    if "luce/altezza" in text or "luce/spessore" in text or "apertura/altezza" in text:
        return "Rapporto geometrico-strutturale"
    if "base trave ridotta" in text or "larghezza inserita" in text or "larghezza architrave" in text:
        return "Sezione poco equilibrata"
    if "deformabilità" in text or "cedevole" in text:
        return "Deformabilità"
    if "troppo ridotto" in text or "troppo tirata" in text or "cautelativa" in text:
        return "Predimensionamento strutturalmente tirato"
    return "Valutazione preliminare generale"


def classify_status_family(status: str, note: str, warnings: list[str]) -> str:
    text = " ".join([status, note] + warnings).lower()

    if "limite geometrico" in text or "supera il limite" in text or "altezza disponibile" in text:
        return "Non compatibile geometricamente"
    if "fuori scala" in text:
        return "Non plausibile in via preliminare"
    if "da verificare" in text:
        return "Possibile ma da verificare"
    if "plausibile" in text:
        return "Plausibile"
    return status


def get_suggestion(element: str, esito: str, motivo: str, material: str) -> str:
    text = f"{esito} {motivo}".lower()

    if element == "Trave" and material == "Calcestruzzo armato":
        if "limite geometrico" in text:
            return "Valutare aumento altezza disponibile, riduzione della luce oppure inserimento di un appoggio intermedio."
        if "sezione poco equilibrata" in text:
            return "Valutare una base più generosa o una sezione più equilibrata."
        if "da verificare" in text or "tirato" in text:
            return "Valutare una sezione più cauta o un miglioramento dello schema statico."
        return "Soluzione preliminarmente coerente. In fase successiva conviene confermare con verifica strutturale."

    if element == "Trave" and material == "Acciaio":
        if "limite geometrico" in text:
            return "Valutare un profilo più performante a parità di altezza, riduzione della luce oppure diversa impostazione strutturale."
        if "deformabilità" in text:
            return "Valutare un profilo con inerzia maggiore o uno schema statico più favorevole."
        if "da verificare" in text or "tirato" in text:
            return "Valutare il passaggio a una famiglia più rigida o un profilo superiore."
        return "Profilo preliminarmente coerente. In fase successiva conviene verificare deformabilità, unioni e dettagli costruttivi."

    if element == "Trave" and material == "Legno":
        if "limite geometrico" in text:
            return "Valutare aumento altezza disponibile, riduzione della luce o tipologia lignea più performante."
        if "deformabilità" in text:
            return "Valutare una sezione con altezza maggiore oppure una soluzione più rigida."
        if "da verificare" in text or "tirato" in text:
            return "Valutare una sezione più cauta o una migliore impostazione dello schema statico."
        return "Sezione preliminarmente coerente. In fase successiva conviene verificare deformabilità, unioni e dettagli di appoggio."

    if element == "Soletta":
        if "limite geometrico" in text:
            return "Valutare aumento spessore disponibile oppure una diversa impostazione strutturale del solaio."
        if "rapporto geometrico-strutturale" in text or "tirato" in text:
            return "Valutare aumento spessore o, se sensato, uno schema più favorevole."
        return "Spessore preliminarmente coerente. In fase successiva conviene verificare deformabilità e carichi definitivi."

    if element == "Pilastro":
        if "limite geometrico" in text:
            return "Valutare una sezione maggiore, riduzione del carico tributario o diversa distribuzione degli appoggi."
        if "snellezza" in text:
            return "Valutare aumento della sezione o riduzione della libera inflessione."
        return "Sezione preliminarmente coerente. In fase successiva conviene verificare snellezza e carico definitivo."

    if element == "Architrave":
        if "limite geometrico" in text:
            return "Valutare maggiore altezza disponibile sopra apertura oppure una soluzione alternativa più performante."
        if "rapporto geometrico-strutturale" in text or "tirato" in text:
            return "Valutare aumento dell'altezza dell'architrave o riduzione della luce dell'apertura."
        return "Architrave preliminarmente coerente. In fase successiva conviene confermare il carico soprastante reale."

    if element == "Sistema rapido":
        if material == "Legno":
            if "limite geometrico" in text:
                return "Valutare maggiore altezza disponibile per le travi in legno, riduzione delle luci o una soluzione strutturale più favorevole."
            if "da verificare" in text or "deformabilità" in text:
                return "Sistema possibile ma da affinare. Conviene verificare deformabilità, appoggi, unioni e protezione del legno."
            return "Sistema preliminarmente coerente. In fase successiva conviene verificare deformabilità, appoggi, unioni e protezione all'umidità."
        if material == "Acciaio":
            if "limite geometrico" in text:
                return "Valutare maggiore altezza disponibile per le travi, riduzione delle luci o una diversa impostazione del sistema."
            if "da verificare" in text or "deformabilità" in text:
                return "Sistema possibile ma con elementi da approfondire. Conviene verificare deformabilità, unioni e nodi principali."
            return "Sistema preliminarmente coerente. In fase successiva conviene verificare unioni, stabilità globale e reale ripartizione dei carichi."

    return "Valutare il risultato nel quadro complessivo del progetto."


def show_summary_box(element: str, esito: str, motivo: str, suggestion: str) -> None:
    st.markdown("### Sintesi finale")
    st.info(
        f"**Esito:** {esito}\n\n"
        f"**Motivo dominante:** {motivo}\n\n"
        f"**Suggerimento progettuale:** {suggestion}"
    )


def system_beam_main_label(material: str) -> str:
    return "Profilo suggerito" if material == "Acciaio" else "Sezione suggerita"


def system_beam_family_label(material: str) -> str:
    return "Famiglia" if material == "Acciaio" else "Tipologia"


def system_beam_dimensions_label(material: str) -> str:
    return "Dimensioni indicative"


def show_system_quick_summary(result, status_family: str) -> None:
    st.markdown("### Sintesi rapida")
    st.success(
        f"**Piano:** {result.floor_label}, {result.slab_dead_load_kN_m2:.2f} kN/m²\n\n"
        f"**Travi lunghe:** {result.long_beams.section_name}\n\n"
        f"**Travi corte:** {result.short_beams.section_name}\n\n"
        f"**Pilastri:** {result.columns.section_width_cm} x {result.columns.section_depth_cm} cm\n\n"
        f"**Esito:** {status_family}"
    )


mode = st.radio(
    "Modalità",
    options=["Elemento singolo", "Sistema rapido"],
    horizontal=True,
)

st.markdown("---")

if mode == "Elemento singolo":
    st.markdown("### Calcolo rapido")

    element = st.selectbox(
        "Elemento",
        options=["Trave", "Soletta", "Pilastro", "Architrave"],
        index=0,
    )

    if element == "Trave":
        material = st.selectbox(
            "Materiale",
            options=["Calcestruzzo armato", "Acciaio", "Legno"],
            index=0,
        )
    else:
        material = st.selectbox(
            "Materiale",
            options=["Calcestruzzo armato"],
            index=0,
        )

    allowed_usage_keys = get_allowed_usage_keys(element)

    selected_usage_key = st.selectbox(
        "Utilizzo",
        options=allowed_usage_keys,
        format_func=lambda key: ALL_USAGE_LABELS[key],
        index=0,
    )

    st.markdown("---")
    st.markdown("### Dati di input")

    if element == "Trave":
        load_mode_label = st.radio(
            "Modalità carico",
            options=["Automatica da utilizzo", "Manuale"],
            horizontal=True,
        )
        load_mode = "automatic" if load_mode_label == "Automatica da utilizzo" else "manual"

        col1, col2 = st.columns(2)

        with col1:
            span_m = st.number_input(
                "Luce netta (m)",
                min_value=0.1,
                value=5.80,
                step=0.10,
                format="%.2f",
                key="beam_span",
            )

            support_label = st.selectbox(
                "Tipo appoggio",
                options=["Appoggiata", "Continua semplificata"],
                index=0,
                key="beam_support",
            )

            if load_mode == "automatic":
                tributary_width_m = st.number_input(
                    "Larghezza tributaria (m)",
                    min_value=0.1,
                    value=3.20,
                    step=0.10,
                    format="%.2f",
                    key="beam_tributary",
                )
                manual_line_load_kN_m = 0.0
            else:
                tributary_width_m = 0.0
                manual_line_load_kN_m = st.number_input(
                    "Carico lineare manuale (kN/m)",
                    min_value=0.1,
                    value=20.0,
                    step=0.5,
                    format="%.2f",
                    key="beam_manual_load",
                )

        with col2:
            if material == "Calcestruzzo armato":
                beam_width_cm = st.number_input(
                    "Larghezza trave (cm) — opzionale",
                    min_value=0.0,
                    value=30.0,
                    step=5.0,
                    format="%.0f",
                    key="beam_width",
                )

                max_height_cm = st.number_input(
                    "Altezza massima disponibile (cm) — opzionale",
                    min_value=0.0,
                    value=60.0,
                    step=5.0,
                    format="%.0f",
                    key="beam_max_height",
                )

                effective_beam_width = beam_width_cm if beam_width_cm > 0 else None
                effective_max_height = max_height_cm if max_height_cm > 0 else None
                effective_max_height_mm = None

            elif material == "Acciaio":
                max_height_mm = st.number_input(
                    "Altezza massima disponibile (mm) — opzionale",
                    min_value=0.0,
                    value=300.0,
                    step=10.0,
                    format="%.0f",
                    key="steel_beam_max_height_mm",
                )

                effective_max_height_mm = max_height_mm if max_height_mm > 0 else None
                effective_beam_width = None
                effective_max_height = None

            else:
                max_height_cm = st.number_input(
                    "Altezza massima disponibile (cm) — opzionale",
                    min_value=0.0,
                    value=40.0,
                    step=2.0,
                    format="%.0f",
                    key="timber_beam_max_height_cm",
                )

                effective_max_height = max_height_cm if max_height_cm > 0 else None
                effective_beam_width = None
                effective_max_height_mm = None

        support_type = "simply_supported" if support_label == "Appoggiata" else "continuous"
        effective_tributary_width = tributary_width_m if tributary_width_m > 0 else None
        effective_manual_line_load = manual_line_load_kN_m if manual_line_load_kN_m > 0 else None

    elif element == "Soletta":
        col1, col2 = st.columns(2)

        with col1:
            span_m = st.number_input(
                "Luce principale (m)",
                min_value=0.1,
                value=5.00,
                step=0.10,
                format="%.2f",
                key="slab_span",
            )

            slab_type_label = st.selectbox(
                "Tipo soletta",
                options=["Monodirezionale", "Bidirezionale semplificata"],
                index=0,
                key="slab_type",
            )

        with col2:
            max_thickness_cm = st.number_input(
                "Spessore massimo disponibile (cm) — opzionale",
                min_value=0.0,
                value=24.0,
                step=2.0,
                format="%.0f",
                key="slab_max_thickness",
            )

        slab_type = "one_way" if slab_type_label == "Monodirezionale" else "two_way"
        effective_max_thickness = max_thickness_cm if max_thickness_cm > 0 else None

    elif element == "Pilastro":
        load_mode_label = st.radio(
            "Modalità carico",
            options=["Area tributaria", "Carico assiale manuale"],
            horizontal=True,
        )
        load_mode = "tributary_area" if load_mode_label == "Area tributaria" else "manual"

        col1, col2 = st.columns(2)

        with col1:
            free_height_m = st.number_input(
                "Altezza libera (m)",
                min_value=0.1,
                value=3.00,
                step=0.10,
                format="%.2f",
                key="column_height",
            )

            floors_supported = st.number_input(
                "Piani caricanti",
                min_value=1,
                value=2,
                step=1,
                key="column_floors",
            )

            if load_mode == "tributary_area":
                tributary_area_m2 = st.number_input(
                    "Area tributaria (m²)",
                    min_value=0.1,
                    value=18.0,
                    step=0.5,
                    format="%.2f",
                    key="column_area",
                )
                manual_axial_load_kN = 0.0
            else:
                tributary_area_m2 = 0.0
                manual_axial_load_kN = st.number_input(
                    "Carico assiale manuale (kN)",
                    min_value=0.1,
                    value=400.0,
                    step=10.0,
                    format="%.2f",
                    key="column_manual_load",
                )

        with col2:
            max_section_cm = st.number_input(
                "Sezione massima disponibile (cm) — opzionale",
                min_value=0.0,
                value=40.0,
                step=5.0,
                format="%.0f",
                key="column_max_section",
            )

        effective_tributary_area = tributary_area_m2 if tributary_area_m2 > 0 else None
        effective_manual_axial_load = manual_axial_load_kN if manual_axial_load_kN > 0 else None
        effective_max_section = max_section_cm if max_section_cm > 0 else None

    else:
        col1, col2 = st.columns(2)

        with col1:
            opening_width_m = st.number_input(
                "Larghezza apertura (m)",
                min_value=0.1,
                value=2.40,
                step=0.10,
                format="%.2f",
                key="lintel_opening",
            )

            load_above_label = st.selectbox(
                "Carico soprastante",
                options=["Muratura leggera", "Muratura + solaio"],
                index=0,
                key="lintel_load_above",
            )

        with col2:
            available_height_cm = st.number_input(
                "Altezza disponibile (cm) — opzionale",
                min_value=0.0,
                value=35.0,
                step=5.0,
                format="%.0f",
                key="lintel_available_height",
            )

            lintel_width_cm = st.number_input(
                "Larghezza architrave (cm) — opzionale",
                min_value=0.0,
                value=30.0,
                step=5.0,
                format="%.0f",
                key="lintel_width",
            )

        load_above_mode = "light_wall" if load_above_label == "Muratura leggera" else "wall_plus_floor"
        effective_available_height = available_height_cm if available_height_cm > 0 else None
        effective_lintel_width = lintel_width_cm if lintel_width_cm > 0 else None

    st.markdown("---")

    if st.button("Calcola predimensionamento", type="primary"):
        try:
            if element == "Trave" and material == "Calcestruzzo armato":
                result = calculate_beam_preliminary(
                    BeamInput(
                        span_m=span_m,
                        support_type=support_type,
                        usage_key=selected_usage_key,
                        load_mode=load_mode,
                        tributary_width_m=effective_tributary_width,
                        manual_line_load_kN_m=effective_manual_line_load,
                        beam_width_cm=effective_beam_width,
                        max_height_cm=effective_max_height,
                    )
                )

                reason = infer_governing_reason(result.status, result.note, result.warnings)
                status_family = classify_status_family(result.status, result.note, result.warnings)
                suggestion = get_suggestion(element, status_family, reason, material)

                st.success("Calcolo completato.")
                st.markdown("## Risultato")
                st.write(f"**Elemento:** {result.element}")
                st.write(f"**Materiale:** {result.material}")
                st.write(f"**Utilizzo:** {result.usage}")
                st.write(f"**Luce:** {result.span_m:.2f} m")

                support_text = "Appoggiata" if result.support_type == "simply_supported" else "Continua semplificata"
                st.write(f"**Schema statico:** {support_text}")

                modo_carico = "Automatico da utilizzo" if result.load_mode == "automatic" else "Manuale"
                st.write(f"**Modalità carico:** {modo_carico}")

                st.markdown("### Predimensionamento")
                st.write(f"**Sezione preliminare consigliata:** {result.beam_width_cm} x {result.beam_height_cm} cm")

                st.markdown("### Azioni e sollecitazioni")
                if result.load_mode == "automatic":
                    st.write(f"**Carico derivato da superficie:** {result.line_load_from_surface_kN_m:.2f} kN/m")
                else:
                    st.write(f"**Carico lineare manuale:** {result.manual_line_load_kN_m:.2f} kN/m")

                st.write(f"**Peso proprio trave:** {result.self_weight_kN_m:.2f} kN/m")
                st.write(f"**Carico lineare adottato:** {result.adopted_line_load_kN_m:.2f} kN/m")
                st.write(f"**Momento massimo stimato:** {result.max_moment_kNm:.2f} kNm")
                st.write(f"**Taglio massimo stimato:** {result.max_shear_kN:.2f} kN")

                st.markdown("### Valutazione sintetica")
                st.write(f"**Esito sintetico:** {status_family}")
                st.write(f"**Motivo dominante:** {reason}")
                st.write(f"**Stato interno:** {result.status}")
                st.write(f"**Rapporto luce/altezza:** {result.slenderness_ratio_l_over_h:.2f}")
                st.write(f"**Rapporto base/altezza:** {result.width_to_height_ratio:.2f}")
                st.write(f"**Nota:** {result.note}")

                if result.warnings:
                    st.markdown("### Warning")
                    for warning in result.warnings:
                        st.warning(warning)

                show_summary_box(element, status_family, reason, suggestion)

            elif element == "Trave" and material == "Acciaio":
                result = calculate_steel_beam_preliminary(
                    SteelBeamInput(
                        span_m=span_m,
                        support_type=support_type,
                        usage_key=selected_usage_key,
                        load_mode=load_mode,
                        tributary_width_m=effective_tributary_width,
                        manual_line_load_kN_m=effective_manual_line_load,
                        max_height_mm=effective_max_height_mm,
                    )
                )

                reason = infer_governing_reason(result.status, result.note, result.warnings)
                status_family = classify_status_family(result.status, result.note, result.warnings)
                suggestion = get_suggestion(element, status_family, reason, material)

                st.success("Calcolo completato.")
                st.markdown("## Risultato")
                st.write(f"**Elemento:** {result.element}")
                st.write(f"**Materiale:** {result.material}")
                st.write(f"**Utilizzo:** {result.usage}")
                st.write(f"**Luce:** {result.span_m:.2f} m")

                support_text = "Appoggiata" if result.support_type == "simply_supported" else "Continua semplificata"
                st.write(f"**Schema statico:** {support_text}")

                modo_carico = "Automatico da utilizzo" if result.load_mode == "automatic" else "Manuale"
                st.write(f"**Modalità carico:** {modo_carico}")

                st.markdown("### Predimensionamento")
                st.write(f"**Profilo suggerito:** {result.section_name}")
                st.write(f"**Famiglia:** {result.section_family}")
                st.write(f"**Dimensioni indicative:** {result.section_width_mm:.0f} x {result.section_height_mm:.0f} mm")

                st.markdown("### Azioni e sollecitazioni")
                st.write(f"**Peso proprio profilo:** {result.self_weight_kN_m:.2f} kN/m")
                st.write(f"**Carico lineare adottato:** {result.adopted_line_load_kN_m:.2f} kN/m")
                st.write(f"**Momento massimo stimato:** {result.max_moment_kNm:.2f} kNm")
                st.write(f"**Taglio massimo stimato:** {result.max_shear_kN:.2f} kN")

                st.markdown("### Parametri profilo")
                st.write(f"**Modulo resistente richiesto:** {result.required_W_cm3:.2f} cm³")
                st.write(f"**Modulo resistente profilo:** {result.section_W_cm3:.2f} cm³")
                st.write(f"**Momento d'inerzia profilo:** {result.section_I_cm4:.2f} cm⁴")
                st.write(f"**Freccia stimata:** {result.estimated_deflection_mm:.2f} mm")

                st.markdown("### Valutazione sintetica")
                st.write(f"**Esito sintetico:** {status_family}")
                st.write(f"**Motivo dominante:** {reason}")
                st.write(f"**Stato interno:** {result.status}")
                st.write(f"**Nota:** {result.note}")

                if result.warnings:
                    st.markdown("### Warning")
                    for warning in result.warnings:
                        st.warning(warning)

                show_summary_box(element, status_family, reason, suggestion)

            elif element == "Trave" and material == "Legno":
                result = calculate_timber_beam_preliminary(
                    TimberBeamInput(
                        span_m=span_m,
                        support_type=support_type,
                        usage_key=selected_usage_key,
                        load_mode=load_mode,
                        tributary_width_m=effective_tributary_width,
                        manual_line_load_kN_m=effective_manual_line_load,
                        max_height_cm=effective_max_height,
                    )
                )

                reason = infer_governing_reason(result.status, result.note, result.warnings)
                status_family = classify_status_family(result.status, result.note, result.warnings)
                suggestion = get_suggestion(element, status_family, reason, material)

                st.success("Calcolo completato.")
                st.markdown("## Risultato")
                st.write(f"**Elemento:** {result.element}")
                st.write(f"**Materiale:** {result.material}")
                st.write(f"**Tipologia:** {result.timber_type}")
                st.write(f"**Utilizzo:** {result.usage}")
                st.write(f"**Luce:** {result.span_m:.2f} m")

                support_text = "Appoggiata" if result.support_type == "simply_supported" else "Continua semplificata"
                st.write(f"**Schema statico:** {support_text}")

                modo_carico = "Automatico da utilizzo" if result.load_mode == "automatic" else "Manuale"
                st.write(f"**Modalità carico:** {modo_carico}")

                st.markdown("### Predimensionamento")
                st.write(f"**Sezione suggerita:** {result.section_b_cm:.0f} x {result.section_h_cm:.0f} cm")
                st.write(f"**Sezione catalogo:** {result.section_name}")

                st.markdown("### Azioni e sollecitazioni")
                st.write(f"**Peso proprio trave:** {result.self_weight_kN_m:.2f} kN/m")
                st.write(f"**Carico lineare adottato:** {result.adopted_line_load_kN_m:.2f} kN/m")
                st.write(f"**Momento massimo stimato:** {result.max_moment_kNm:.2f} kNm")
                st.write(f"**Taglio massimo stimato:** {result.max_shear_kN:.2f} kN")

                st.markdown("### Parametri sezione")
                st.write(f"**Modulo resistente richiesto:** {result.required_W_cm3:.2f} cm³")
                st.write(f"**Modulo resistente sezione:** {result.section_W_cm3:.2f} cm³")
                st.write(f"**Momento d'inerzia sezione:** {result.section_I_cm4:.2f} cm⁴")
                st.write(f"**Freccia stimata:** {result.estimated_deflection_mm:.2f} mm")

                st.markdown("### Valutazione sintetica")
                st.write(f"**Esito sintetico:** {status_family}")
                st.write(f"**Motivo dominante:** {reason}")
                st.write(f"**Stato interno:** {result.status}")
                st.write(f"**Rapporto luce/altezza:** {result.slenderness_ratio_l_over_h:.2f}")
                st.write(f"**Nota:** {result.note}")

                if result.warnings:
                    st.markdown("### Warning")
                    for warning in result.warnings:
                        st.warning(warning)

                show_summary_box(element, status_family, reason, suggestion)

            elif element == "Soletta":
                result = calculate_slab_preliminary(
                    SlabInput(
                        span_m=span_m,
                        slab_type=slab_type,
                        usage_key=selected_usage_key,
                        max_thickness_cm=effective_max_thickness,
                    )
                )

                reason = infer_governing_reason(result.status, result.note, result.warnings)
                status_family = classify_status_family(result.status, result.note, result.warnings)
                suggestion = get_suggestion(element, status_family, reason, material)

                st.success("Calcolo completato.")
                st.markdown("## Risultato")
                st.write(f"**Elemento:** {result.element}")
                st.write(f"**Materiale:** {result.material}")
                st.write(f"**Utilizzo:** {result.usage}")
                st.write(f"**Luce:** {result.span_m:.2f} m")

                slab_type_text = "Monodirezionale" if result.slab_type == "one_way" else "Bidirezionale semplificata"
                st.write(f"**Tipo soletta:** {slab_type_text}")

                st.markdown("### Predimensionamento")
                st.write(f"**Spessore preliminare consigliato:** {result.thickness_cm} cm")

                st.markdown("### Azioni e sollecitazioni")
                st.write(f"**Peso proprio soletta:** {result.self_weight_kN_m2:.2f} kN/m²")
                st.write(f"**Carico superficiale adottato:** {result.adopted_surface_load_kN_m2:.2f} kN/m²")
                st.write(f"**Momento massimo stimato:** {result.max_moment_kNm_per_m:.2f} kNm/m")

                st.markdown("### Valutazione sintetica")
                st.write(f"**Esito sintetico:** {status_family}")
                st.write(f"**Motivo dominante:** {reason}")
                st.write(f"**Stato interno:** {result.status}")
                st.write(f"**Rapporto luce/spessore:** {result.span_to_thickness_ratio:.2f}")
                st.write(f"**Nota:** {result.note}")

                if result.warnings:
                    st.markdown("### Warning")
                    for warning in result.warnings:
                        st.warning(warning)

                show_summary_box(element, status_family, reason, suggestion)

            elif element == "Pilastro":
                result = calculate_column_preliminary(
                    ColumnInput(
                        free_height_m=free_height_m,
                        usage_key=selected_usage_key,
                        load_mode=load_mode,
                        tributary_area_m2=effective_tributary_area,
                        floors_supported=int(floors_supported),
                        manual_axial_load_kN=effective_manual_axial_load,
                        max_section_cm=effective_max_section,
                    )
                )

                reason = infer_governing_reason(result.status, result.note, result.warnings)
                status_family = classify_status_family(result.status, result.note, result.warnings)
                suggestion = get_suggestion(element, status_family, reason, material)

                st.success("Calcolo completato.")
                st.markdown("## Risultato")
                st.write(f"**Elemento:** {result.element}")
                st.write(f"**Materiale:** {result.material}")
                st.write(f"**Utilizzo:** {result.usage}")
                st.write(f"**Altezza libera:** {result.free_height_m:.2f} m")
                st.write(f"**Piani caricanti:** {result.floors_supported}")

                modo_carico = "Area tributaria" if result.load_mode == "tributary_area" else "Carico assiale manuale"
                st.write(f"**Modalità carico:** {modo_carico}")

                st.markdown("### Predimensionamento")
                st.write(f"**Sezione preliminare consigliata:** {result.section_width_cm} x {result.section_depth_cm} cm")

                st.markdown("### Azioni")
                if result.load_mode == "tributary_area":
                    st.write(f"**Carico superficiale stimato:** {result.estimated_surface_load_kN_m2:.2f} kN/m²")
                else:
                    st.write(f"**Carico assiale manuale:** {result.manual_axial_load_kN:.2f} kN")

                st.write(f"**Peso proprio pilastro:** {result.self_weight_kN:.2f} kN")
                st.write(f"**Carico assiale adottato:** {result.adopted_axial_load_kN:.2f} kN")

                st.markdown("### Valutazione sintetica")
                st.write(f"**Esito sintetico:** {status_family}")
                st.write(f"**Motivo dominante:** {reason}")
                st.write(f"**Stato interno:** {result.status}")
                st.write(f"**Rapporto snellezza:** {result.slenderness_ratio:.2f}")
                st.write(f"**Tensione media stimata:** {result.stress_kN_m2:.2f} kN/m²")
                st.write(f"**Nota:** {result.note}")

                if result.warnings:
                    st.markdown("### Warning")
                    for warning in result.warnings:
                        st.warning(warning)

                show_summary_box(element, status_family, reason, suggestion)

            else:
                result = calculate_lintel_preliminary(
                    LintelInput(
                        opening_width_m=opening_width_m,
                        usage_key=selected_usage_key,
                        load_above_mode=load_above_mode,
                        available_height_cm=effective_available_height,
                        lintel_width_cm=effective_lintel_width,
                    )
                )

                reason = infer_governing_reason(result.status, result.note, result.warnings)
                status_family = classify_status_family(result.status, result.note, result.warnings)
                suggestion = get_suggestion(element, status_family, reason, material)

                st.success("Calcolo completato.")
                st.markdown("## Risultato")
                st.write(f"**Elemento:** {result.element}")
                st.write(f"**Materiale:** {result.material}")
                st.write(f"**Utilizzo:** {result.usage}")
                st.write(f"**Larghezza apertura:** {result.opening_width_m:.2f} m")

                load_above_text = "Muratura leggera" if result.load_above_mode == "light_wall" else "Muratura + solaio"
                st.write(f"**Carico soprastante:** {load_above_text}")

                st.markdown("### Predimensionamento")
                st.write(f"**Sezione preliminare consigliata:** {result.lintel_width_cm} x {result.lintel_height_cm} cm")

                st.markdown("### Azioni e sollecitazioni")
                st.write(f"**Peso proprio architrave:** {result.self_weight_kN_m:.2f} kN/m")
                st.write(f"**Carico lineare adottato:** {result.adopted_line_load_kN_m:.2f} kN/m")
                st.write(f"**Momento massimo stimato:** {result.max_moment_kNm:.2f} kNm")

                st.markdown("### Valutazione sintetica")
                st.write(f"**Esito sintetico:** {status_family}")
                st.write(f"**Motivo dominante:** {reason}")
                st.write(f"**Stato interno:** {result.status}")
                st.write(f"**Rapporto apertura/altezza:** {result.opening_to_height_ratio:.2f}")
                st.write(f"**Nota:** {result.note}")

                if result.warnings:
                    st.markdown("### Warning")
                    for warning in result.warnings:
                        st.warning(warning)

                show_summary_box(element, status_family, reason, suggestion)

        except Exception as exc:
            st.error(f"Errore: {exc}")

else:
    element = "Sistema rapido"

    st.markdown("### Sistema rapido light")

    selected_usage_key = st.selectbox(
        "Utilizzo",
        options=get_allowed_usage_keys("Sistema rapido"),
        format_func=lambda key: ALL_USAGE_LABELS[key],
        index=0,
    )

    floor_type_label = st.selectbox(
        "Tipologia piano",
        options=["Manuale", "Legno", "Calcestruzzo armato"],
        index=0,
    )

    if floor_type_label == "Manuale":
        floor_type = "manual"
    elif floor_type_label == "Legno":
        floor_type = "timber"
    else:
        floor_type = "concrete"

    beam_material_label = st.selectbox(
        "Materiale travi",
        options=["Acciaio", "Legno"],
        index=0,
    )
    beam_material = "steel" if beam_material_label == "Acciaio" else "timber"

    col1, col2 = st.columns(2)

    with col1:
        length_m = st.number_input(
            "Lunghezza piattaforma (m)",
            min_value=0.1,
            value=5.00,
            step=0.10,
            format="%.2f",
            key="sys_length",
        )

        width_m = st.number_input(
            "Larghezza piattaforma (m)",
            min_value=0.1,
            value=4.00,
            step=0.10,
            format="%.2f",
            key="sys_width",
        )

        if floor_type == "manual":
            slab_dead_load_kN_m2 = st.number_input(
                "Peso proprio piano / soletta (kN/m²)",
                min_value=0.1,
                value=3.0,
                step=0.1,
                format="%.2f",
                key="sys_slab_dead_manual",
            )
        elif floor_type == "timber":
            slab_dead_load_kN_m2 = st.number_input(
                "Peso equivalente piano legno (kN/m²)",
                min_value=0.1,
                value=2.5,
                step=0.1,
                format="%.2f",
                key="sys_slab_dead_timber",
            )
        else:
            concrete_thickness_cm = st.number_input(
                "Spessore soletta c.a. (cm)",
                min_value=1.0,
                value=20.0,
                step=1.0,
                format="%.0f",
                key="sys_concrete_thickness_cm",
            )
            slab_dead_load_kN_m2 = (concrete_thickness_cm / 100.0) * 25.0

    with col2:
        if beam_material == "steel":
            beam_max_height_mm = st.number_input(
                "Altezza massima travi (mm) — opzionale",
                min_value=0.0,
                value=300.0,
                step=10.0,
                format="%.0f",
                key="sys_beam_max_height_mm",
            )
            beam_max_height_cm = 0.0
        else:
            beam_max_height_cm = st.number_input(
                "Altezza massima travi (cm) — opzionale",
                min_value=0.0,
                value=40.0,
                step=2.0,
                format="%.0f",
                key="sys_beam_max_height_cm",
            )
            beam_max_height_mm = 0.0

        column_max_section_cm = st.number_input(
            "Sezione massima pilastri (cm) — opzionale",
            min_value=0.0,
            value=40.0,
            step=5.0,
            format="%.0f",
            key="sys_column_max_section",
        )

    st.markdown("---")

    floor_preview_lines = [
        f"**Superficie totale:** {(length_m * width_m):.2f} m²",
        f"**Tipologia piano:** {'Peso manuale equivalente' if floor_type == 'manual' else 'Piano leggero in legno' if floor_type == 'timber' else 'Soletta in calcestruzzo armato'}",
        f"**Materiale travi:** {beam_material_label}",
    ]

    if floor_type == "concrete":
        floor_preview_lines.append(f"**Spessore assunto:** {concrete_thickness_cm:.0f} cm")

    floor_preview_lines.append(f"**Peso proprio adottato:** {slab_dead_load_kN_m2:.2f} kN/m²")
    floor_preview_lines.append("**Schema assunto:** piattaforma rettangolare su 4 travi perimetrali appoggiate e 4 pilastri angolari")

    st.markdown("  \n".join(floor_preview_lines))

    effective_beam_max_height_mm = beam_max_height_mm if beam_max_height_mm > 0 else None
    effective_beam_max_height_cm = beam_max_height_cm if beam_max_height_cm > 0 else None
    effective_column_max_section_cm = column_max_section_cm if column_max_section_cm > 0 else None

    if st.button("Calcola sistema rapido", type="primary"):
        try:
            result = calculate_system_light(
                SystemLightInput(
                    length_m=length_m,
                    width_m=width_m,
                    floor_type=floor_type,
                    slab_dead_load_kN_m2=slab_dead_load_kN_m2,
                    usage_key=selected_usage_key,
                    beam_material=beam_material,
                    beam_max_height_mm=effective_beam_max_height_mm,
                    beam_max_height_cm=effective_beam_max_height_cm,
                    column_max_section_cm=effective_column_max_section_cm,
                )
            )

            status_family = classify_status_family(result.status, result.note, result.warnings)
            reason = infer_governing_reason(result.status, result.note, result.warnings)
            system_material_for_suggestion = result.beam_material_label
            suggestion = get_suggestion("Sistema rapido", status_family, reason, system_material_for_suggestion)

            st.success("Calcolo completato.")

            st.markdown("## Riepilogo sistema")
            st.write(f"**Tipologia sistema:** {result.system_type}")
            st.write(f"**Utilizzo:** {result.usage}")
            st.write(f"**Dimensioni:** {result.length_m:.2f} x {result.width_m:.2f} m")
            st.write(f"**Superficie:** {result.area_m2:.2f} m²")

            show_system_quick_summary(result, status_family)

            st.markdown("### Piano")
            st.write(f"**Tipologia piano:** {result.floor_label}")
            st.write(f"**Peso proprio piano adottato:** {result.slab_dead_load_kN_m2:.2f} kN/m²")
            if floor_type == "concrete":
                st.write(f"**Spessore soletta c.a.:** {concrete_thickness_cm:.0f} cm")

            st.markdown("### Materiali sistema")
            st.write(f"**Materiale travi:** {result.beam_material_label}")
            st.write("**Materiale pilastri:** Calcestruzzo armato")

            st.markdown("### Carichi")
            st.write(f"**Permanenti non strutturali:** {result.non_structural_dead_load_kN_m2:.2f} kN/m²")
            st.write(f"**Variabili d'uso:** {result.live_load_kN_m2:.2f} kN/m²")
            st.write(f"**Carico superficiale totale:** {result.total_surface_load_kN_m2:.2f} kN/m²")
            st.write(f"**Carico totale sistema:** {result.total_load_kN:.2f} kN")

            long_main_label = system_beam_main_label(result.long_beams.material)
            long_family_label = system_beam_family_label(result.long_beams.material)
            long_dim_label = system_beam_dimensions_label(result.long_beams.material)

            st.markdown("### Travi lunghe")
            st.write(f"**Numero:** {result.long_beams.count}")
            st.write(f"**Materiale:** {result.long_beams.material}")
            st.write(f"**Luce:** {result.long_beams.span_m:.2f} m")
            st.write(f"**Larghezza tributaria:** {result.long_beams.tributary_width_m:.2f} m")
            st.write(f"**Carico lineare adottato:** {result.long_beams.line_load_kN_m:.2f} kN/m")
            st.write(f"**{long_main_label}:** {result.long_beams.section_name}")
            st.write(f"**{long_family_label}:** {result.long_beams.section_family}")
            st.write(f"**{long_dim_label}:** {result.long_beams.section_width_mm:.0f} x {result.long_beams.section_height_mm:.0f} mm")
            st.write(f"**Momento massimo stimato:** {result.long_beams.max_moment_kNm:.2f} kNm")
            st.write(f"**Taglio massimo stimato:** {result.long_beams.max_shear_kN:.2f} kN")
            st.write(f"**Stato:** {result.long_beams.status}")

            short_main_label = system_beam_main_label(result.short_beams.material)
            short_family_label = system_beam_family_label(result.short_beams.material)
            short_dim_label = system_beam_dimensions_label(result.short_beams.material)

            st.markdown("### Travi corte")
            st.write(f"**Numero:** {result.short_beams.count}")
            st.write(f"**Materiale:** {result.short_beams.material}")
            st.write(f"**Luce:** {result.short_beams.span_m:.2f} m")
            st.write(f"**Larghezza tributaria:** {result.short_beams.tributary_width_m:.2f} m")
            st.write(f"**Carico lineare adottato:** {result.short_beams.line_load_kN_m:.2f} kN/m")
            st.write(f"**{short_main_label}:** {result.short_beams.section_name}")
            st.write(f"**{short_family_label}:** {result.short_beams.section_family}")
            st.write(f"**{short_dim_label}:** {result.short_beams.section_width_mm:.0f} x {result.short_beams.section_height_mm:.0f} mm")
            st.write(f"**Momento massimo stimato:** {result.short_beams.max_moment_kNm:.2f} kNm")
            st.write(f"**Taglio massimo stimato:** {result.short_beams.max_shear_kN:.2f} kN")
            st.write(f"**Stato:** {result.short_beams.status}")

            st.markdown("### Pilastri")
            st.write(f"**Numero:** {result.columns.count}")
            st.write(f"**Carico assiale per pilastro:** {result.columns.axial_load_per_column_kN:.2f} kN")
            st.write(f"**Sezione preliminare consigliata:** {result.columns.section_width_cm} x {result.columns.section_depth_cm} cm")
            st.write(f"**Rapporto snellezza:** {result.columns.slenderness_ratio:.2f}")
            st.write(f"**Stato:** {result.columns.status}")

            st.markdown("### Valutazione sintetica")
            st.write(f"**Esito sintetico:** {status_family}")
            st.write(f"**Motivo dominante:** {reason}")
            st.write(f"**Stato interno:** {result.status}")
            st.write(f"**Nota:** {result.note}")

            if result.warnings:
                st.markdown("### Warning")
                for warning in result.warnings:
                    st.warning(warning)

            show_summary_box("Sistema rapido", status_family, reason, suggestion)

        except Exception as exc:
            st.error(f"Errore: {exc}")

st.markdown("---")
st.caption("V1.0-D: modalità elemento singolo e sistema rapido light con UX più pulita.")