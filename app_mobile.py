import streamlit as st

from beam_engine_steel import SteelBeamInput, calculate_steel_beam_preliminary
from beam_engine_timber import TimberBeamInput, calculate_timber_beam_preliminary
from system_light_engine import SystemLightInput, calculate_system_light
from presets import get_usage_labels


st.set_page_config(
    page_title="PROGravitate Mobile",
    layout="centered",
    initial_sidebar_state="collapsed",
)

ALL_USAGE_LABELS = get_usage_labels()


# -----------------------------
# Helpers
# -----------------------------
def classify_status_family(status: str, note: str, warnings: list[str]) -> str:
    text = " ".join([status, note] + warnings).lower()

    if "limite geometrico" in text or "supera il limite" in text or "altezza disponibile" in text:
        return "Non compatibile"
    if "fuori scala" in text:
        return "Non plausibile"
    if "da verificare" in text:
        return "Da verificare"
    if "plausibile" in text:
        return "Plausibile"
    return status


def infer_governing_reason(status: str, note: str, warnings: list[str]) -> str:
    text = " ".join([status, note] + warnings).lower()

    if "limite geometrico" in text or "altezza disponibile" in text:
        return "Limite geometrico"
    if "deformabilità" in text:
        return "Deformabilità"
    if "snellezza" in text:
        return "Snellezza"
    if "luce/altezza" in text or "luce/spessore" in text:
        return "Rapporto geometrico"
    return "Valutazione generale"


def get_mobile_suggestion(mode: str, material: str, status_family: str, reason: str) -> str:
    text = f"{status_family} {reason}".lower()

    if mode == "Trave":
        if material == "Acciaio":
            if "limite geometrico" in text:
                return "Aumentare altezza o ridurre luce."
            if "deformabilità" in text or "da verificare" in text:
                return "Valutare un profilo più rigido."
            return "Soluzione coerente."
        if material == "Legno":
            if "limite geometrico" in text:
                return "Aumentare altezza o ridurre luce."
            if "deformabilità" in text or "da verificare" in text:
                return "Valutare una sezione più alta."
            return "Soluzione coerente."

    if mode == "Sistema rapido":
        if material == "Acciaio":
            if "limite geometrico" in text:
                return "Rivedere luci o altezza travi."
            if "da verificare" in text:
                return "Approfondire deformabilità e nodi."
            return "Sistema coerente."
        if material == "Legno":
            if "limite geometrico" in text:
                return "Rivedere luci o altezza travi."
            if "da verificare" in text:
                return "Approfondire deformabilità e appoggi."
            return "Sistema coerente."

    return "Verificare con più dettaglio."


def show_mobile_result_card(title: str, esito: str, soluzione: str, motivo: str, suggerimento: str) -> None:
    body = (
        f"**{title}**\n\n"
        f"**Esito:** {esito}\n\n"
        f"**Soluzione:** {soluzione}\n\n"
        f"**Motivo:** {motivo}\n\n"
        f"**Suggerimento:** {suggerimento}"
    )
    if esito == "Plausibile":
        st.success(body)
    elif esito == "Da verificare":
        st.warning(body)
    else:
        st.error(body)


def init_session_state() -> None:
    defaults = {
        "mobile_last_result": None,
        "mobile_form_nonce": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_mobile_form() -> None:
    st.session_state.mobile_last_result = None
    st.session_state.mobile_form_nonce += 1


def result_key(prefix: str) -> str:
    return f"{prefix}_{st.session_state.mobile_form_nonce}"


init_session_state()


# -----------------------------
# Header
# -----------------------------
top_col1, top_col2 = st.columns([4, 1])
with top_col1:
    st.title("PROGravitate")
    st.caption("Mobile — rapido")
with top_col2:
    st.write("")
    if st.button("Nuovo", use_container_width=True):
        reset_mobile_form()
        st.rerun()

mode = st.radio(
    "Modalità",
    options=["Trave", "Sistema rapido"],
    horizontal=True,
    key=result_key("mode"),
)

st.markdown("---")


# -----------------------------
# Trave
# -----------------------------
if mode == "Trave":
    material_label = st.selectbox(
        "Materiale",
        options=["Acciaio", "Legno"],
        index=0,
        key=result_key("beam_material"),
    )
    material = "steel" if material_label == "Acciaio" else "timber"

    usage_key = st.selectbox(
        "Utilizzo",
        options=["residential", "balcony", "roof_walkable", "roof_not_walkable", "light_vehicle"],
        format_func=lambda key: ALL_USAGE_LABELS[key],
        index=0,
        key=result_key("beam_usage"),
    )

    load_mode_label = st.radio(
        "Carico",
        options=["Automatico", "Manuale"],
        horizontal=True,
        key=result_key("beam_load_mode"),
    )
    load_mode = "automatic" if load_mode_label == "Automatico" else "manual"

    span_m = st.number_input(
        "Luce (m)",
        min_value=0.1,
        value=5.00,
        step=0.10,
        format="%.2f",
        key=result_key("beam_span"),
    )

    support_label = st.selectbox(
        "Schema",
        options=["Appoggiata", "Continua semplificata"],
        index=0,
        key=result_key("beam_support"),
    )
    support_type = "simply_supported" if support_label == "Appoggiata" else "continuous"

    if load_mode == "automatic":
        tributary_width_m = st.number_input(
            "Larghezza tributaria (m)",
            min_value=0.1,
            value=3.00,
            step=0.10,
            format="%.2f",
            key=result_key("beam_tributary"),
        )
        manual_line_load_kN_m = None
    else:
        tributary_width_m = None
        manual_line_load_kN_m = st.number_input(
            "Carico lineare (kN/m)",
            min_value=0.1,
            value=10.0,
            step=0.5,
            format="%.2f",
            key=result_key("beam_manual_q"),
        )

    if material == "steel":
        max_height_mm = st.number_input(
            "Altezza max (mm)",
            min_value=0.0,
            value=300.0,
            step=10.0,
            format="%.0f",
            key=result_key("beam_hmax_mm"),
        )
        effective_max_height_mm = max_height_mm if max_height_mm > 0 else None
        effective_max_height_cm = None
    else:
        max_height_cm = st.number_input(
            "Altezza max (cm)",
            min_value=0.0,
            value=40.0,
            step=2.0,
            format="%.0f",
            key=result_key("beam_hmax_cm"),
        )
        effective_max_height_cm = max_height_cm if max_height_cm > 0 else None
        effective_max_height_mm = None

    if st.button("Calcola", type="primary", use_container_width=True, key=result_key("beam_calc")):
        try:
            if material == "steel":
                result = calculate_steel_beam_preliminary(
                    SteelBeamInput(
                        span_m=span_m,
                        support_type=support_type,
                        usage_key=usage_key,
                        load_mode=load_mode,
                        tributary_width_m=tributary_width_m,
                        manual_line_load_kN_m=manual_line_load_kN_m,
                        max_height_mm=effective_max_height_mm,
                    )
                )
                status_family = classify_status_family(result.status, result.note, result.warnings)
                reason = infer_governing_reason(result.status, result.note, result.warnings)
                suggestion = get_mobile_suggestion("Trave", "Acciaio", status_family, reason)
                solution = result.section_name

                details = {
                    "Luce": f"{result.span_m:.2f} m",
                    "Carico lineare": f"{result.adopted_line_load_kN_m:.2f} kN/m",
                    "Momento massimo": f"{result.max_moment_kNm:.2f} kNm",
                    "Taglio massimo": f"{result.max_shear_kN:.2f} kN",
                    "Freccia stimata": f"{result.estimated_deflection_mm:.2f} mm",
                    "Dimensioni indicative": f"{result.section_width_mm:.0f} x {result.section_height_mm:.0f} mm",
                    "Nota": result.note,
                    "Warnings": result.warnings,
                }

                st.session_state.mobile_last_result = {
                    "title": "Trave acciaio",
                    "esito": status_family,
                    "soluzione": solution,
                    "motivo": reason,
                    "suggerimento": suggestion,
                    "details": details,
                }

            else:
                result = calculate_timber_beam_preliminary(
                    TimberBeamInput(
                        span_m=span_m,
                        support_type=support_type,
                        usage_key=usage_key,
                        load_mode=load_mode,
                        tributary_width_m=tributary_width_m,
                        manual_line_load_kN_m=manual_line_load_kN_m,
                        max_height_cm=effective_max_height_cm,
                    )
                )
                status_family = classify_status_family(result.status, result.note, result.warnings)
                reason = infer_governing_reason(result.status, result.note, result.warnings)
                suggestion = get_mobile_suggestion("Trave", "Legno", status_family, reason)
                solution = f"{result.section_name} ({result.section_b_cm:.0f}x{result.section_h_cm:.0f} cm)"

                details = {
                    "Luce": f"{result.span_m:.2f} m",
                    "Carico lineare": f"{result.adopted_line_load_kN_m:.2f} kN/m",
                    "Momento massimo": f"{result.max_moment_kNm:.2f} kNm",
                    "Taglio massimo": f"{result.max_shear_kN:.2f} kN",
                    "Freccia stimata": f"{result.estimated_deflection_mm:.2f} mm",
                    "Tipologia": result.timber_type,
                    "Nota": result.note,
                    "Warnings": result.warnings,
                }

                st.session_state.mobile_last_result = {
                    "title": "Trave legno",
                    "esito": status_family,
                    "soluzione": solution,
                    "motivo": reason,
                    "suggerimento": suggestion,
                    "details": details,
                }

        except Exception as exc:
            st.session_state.mobile_last_result = {
                "error": f"Errore: {exc}"
            }

# -----------------------------
# Sistema rapido
# -----------------------------
else:
    usage_key = st.selectbox(
        "Utilizzo",
        options=["residential", "balcony", "roof_walkable", "roof_not_walkable", "light_vehicle"],
        format_func=lambda key: ALL_USAGE_LABELS[key],
        index=0,
        key=result_key("sys_usage"),
    )

    floor_type_label = st.selectbox(
        "Tipologia piano",
        options=["Manuale", "Legno", "Calcestruzzo armato"],
        index=0,
        key=result_key("sys_floor_type"),
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
        key=result_key("sys_beam_mat"),
    )
    beam_material = "steel" if beam_material_label == "Acciaio" else "timber"

    length_m = st.number_input(
        "Lunghezza (m)",
        min_value=0.1,
        value=5.00,
        step=0.10,
        format="%.2f",
        key=result_key("sys_L"),
    )

    width_m = st.number_input(
        "Larghezza (m)",
        min_value=0.1,
        value=4.00,
        step=0.10,
        format="%.2f",
        key=result_key("sys_B"),
    )

    if floor_type == "manual":
        slab_dead_load_kN_m2 = st.number_input(
            "Peso piano (kN/m²)",
            min_value=0.1,
            value=3.0,
            step=0.1,
            format="%.2f",
            key=result_key("sys_qfloor_manual"),
        )
    elif floor_type == "timber":
        slab_dead_load_kN_m2 = st.number_input(
            "Peso piano legno (kN/m²)",
            min_value=0.1,
            value=2.5,
            step=0.1,
            format="%.2f",
            key=result_key("sys_qfloor_timber"),
        )
    else:
        concrete_thickness_cm = st.number_input(
            "Spessore soletta c.a. (cm)",
            min_value=1.0,
            value=20.0,
            step=1.0,
            format="%.0f",
            key=result_key("sys_t_ca"),
        )
        slab_dead_load_kN_m2 = (concrete_thickness_cm / 100.0) * 25.0

    if beam_material == "steel":
        beam_max_height_mm = st.number_input(
            "Altezza max travi (mm)",
            min_value=0.0,
            value=300.0,
            step=10.0,
            format="%.0f",
            key=result_key("sys_hmax_mm"),
        )
        effective_beam_max_height_mm = beam_max_height_mm if beam_max_height_mm > 0 else None
        effective_beam_max_height_cm = None
    else:
        beam_max_height_cm = st.number_input(
            "Altezza max travi (cm)",
            min_value=0.0,
            value=40.0,
            step=2.0,
            format="%.0f",
            key=result_key("sys_hmax_cm"),
        )
        effective_beam_max_height_cm = beam_max_height_cm if beam_max_height_cm > 0 else None
        effective_beam_max_height_mm = None

    column_max_section_cm = st.number_input(
        "Sezione max pilastri (cm)",
        min_value=0.0,
        value=40.0,
        step=5.0,
        format="%.0f",
        key=result_key("sys_colmax"),
    )
    effective_column_max_section_cm = column_max_section_cm if column_max_section_cm > 0 else None

    if st.button("Calcola", type="primary", use_container_width=True, key=result_key("sys_calc")):
        try:
            result = calculate_system_light(
                SystemLightInput(
                    length_m=length_m,
                    width_m=width_m,
                    floor_type=floor_type,
                    slab_dead_load_kN_m2=slab_dead_load_kN_m2,
                    usage_key=usage_key,
                    beam_material=beam_material,
                    beam_max_height_mm=effective_beam_max_height_mm,
                    beam_max_height_cm=effective_beam_max_height_cm,
                    column_max_section_cm=effective_column_max_section_cm,
                )
            )

            status_family = classify_status_family(result.status, result.note, result.warnings)
            reason = infer_governing_reason(result.status, result.note, result.warnings)
            suggestion = get_mobile_suggestion("Sistema rapido", result.beam_material_label, status_family, reason)

            solution = (
                f"Lunghe {result.long_beams.section_name} · "
                f"Corte {result.short_beams.section_name} · "
                f"Pilastri {result.columns.section_width_cm}x{result.columns.section_depth_cm}"
            )

            details = {
                "Utilizzo": result.usage,
                "Dimensioni": f"{result.length_m:.2f} x {result.width_m:.2f} m",
                "Superficie": f"{result.area_m2:.2f} m²",
                "Tipologia piano": result.floor_label,
                "Materiale travi": result.beam_material_label,
                "Carico superficiale totale": f"{result.total_surface_load_kN_m2:.2f} kN/m²",
                "Carico totale sistema": f"{result.total_load_kN:.2f} kN",
                "Travi lunghe": f"{result.long_beams.section_name} · {result.long_beams.span_m:.2f} m · {result.long_beams.line_load_kN_m:.2f} kN/m · {result.long_beams.status}",
                "Travi corte": f"{result.short_beams.section_name} · {result.short_beams.span_m:.2f} m · {result.short_beams.line_load_kN_m:.2f} kN/m · {result.short_beams.status}",
                "Pilastri": f"{result.columns.section_width_cm} x {result.columns.section_depth_cm} cm · {result.columns.axial_load_per_column_kN:.2f} kN · {result.columns.status}",
                "Nota": result.note,
                "Warnings": result.warnings,
            }

            st.session_state.mobile_last_result = {
                "title": "Sistema rapido",
                "esito": status_family,
                "soluzione": solution,
                "motivo": reason,
                "suggerimento": suggestion,
                "details": details,
            }

        except Exception as exc:
            st.session_state.mobile_last_result = {
                "error": f"Errore: {exc}"
            }

# -----------------------------
# Last result
# -----------------------------
last_result = st.session_state.mobile_last_result
if last_result:
    st.markdown("---")
    if "error" in last_result:
        st.error(last_result["error"])
    else:
        show_mobile_result_card(
            title=last_result["title"],
            esito=last_result["esito"],
            soluzione=last_result["soluzione"],
            motivo=last_result["motivo"],
            suggerimento=last_result["suggerimento"],
        )

        with st.expander("Dettagli"):
            for key, value in last_result["details"].items():
                if key == "Warnings":
                    for warning in value:
                        st.warning(warning)
                else:
                    st.write(f"**{key}:** {value}")

        bottom_col1, bottom_col2 = st.columns(2)
        with bottom_col1:
            if st.button("Nuovo calcolo", use_container_width=True, key=result_key("bottom_reset")):
                reset_mobile_form()
                st.rerun()
        with bottom_col2:
            st.button("Dettagli sopra", use_container_width=True, disabled=True, key=result_key("bottom_details"))

st.markdown("---")
st.caption("Mobile-first v2: rapido, leggibile, reset immediato.")