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
                return "Aumentare H o ridurre luce."
            if "deformabilità" in text or "da verificare" in text:
                return "Valutare profilo più rigido."
            return "Procedere a verifica successiva."
        if material == "Legno":
            if "limite geometrico" in text:
                return "Aumentare H o ridurre luce."
            if "deformabilità" in text or "da verificare" in text:
                return "Valutare sezione più alta."
            return "Procedere a verifica successiva."

    if mode == "Sistema rapido":
        if material == "Acciaio":
            if "limite geometrico" in text:
                return "Rivedere luci o H travi."
            if "da verificare" in text:
                return "Approfondire nodi e deformabilità."
            return "Sistema coerente per studio rapido."
        if material == "Legno":
            if "limite geometrico" in text:
                return "Rivedere luci o H travi."
            if "da verificare" in text:
                return "Approfondire appoggi e deformabilità."
            return "Sistema coerente per studio rapido."

    return "Verificare con maggior dettaglio."


def show_result_card(title: str, esito: str, soluzione: str, motivo: str, azione: str) -> None:
    body = (
        f"**{title}**\n\n"
        f"**Esito:** {esito}\n\n"
        f"**Soluzione:** {soluzione}\n\n"
        f"**Motivo:** {motivo}\n\n"
        f"**Azione:** {azione}"
    )
    if esito == "Plausibile":
        st.success(body)
    elif esito == "Da verificare":
        st.warning(body)
    else:
        st.error(body)


def init_state() -> None:
    defaults = {
        "mobile_last_result": None,
        "form_nonce": 0,
        "preset_length_m": 5.0,
        "preset_width_m": 4.0,
        "preset_usage_key": "residential",
        "preset_floor_type": "manual",
        "preset_slab_dead_load_kN_m2": 3.0,
        "beam_usage_key": "residential",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def form_key(name: str) -> str:
    return f"{name}_{st.session_state.form_nonce}"


def reset_form() -> None:
    st.session_state.mobile_last_result = None
    st.session_state.form_nonce += 1
    st.session_state.preset_length_m = 5.0
    st.session_state.preset_width_m = 4.0
    st.session_state.preset_usage_key = "residential"
    st.session_state.preset_floor_type = "manual"
    st.session_state.preset_slab_dead_load_kN_m2 = 3.0
    st.session_state.beam_usage_key = "residential"


def apply_geometry_preset(length_m: float, width_m: float) -> None:
    st.session_state.preset_length_m = length_m
    st.session_state.preset_width_m = width_m


def apply_usage_preset(usage_key: str) -> None:
    st.session_state.preset_usage_key = usage_key


def apply_beam_usage_preset(usage_key: str) -> None:
    st.session_state.beam_usage_key = usage_key


def apply_floor_preset(floor_type: str, dead_load: float) -> None:
    st.session_state.preset_floor_type = floor_type
    st.session_state.preset_slab_dead_load_kN_m2 = dead_load


init_state()

st.title("PROGravitate")

top1, top2 = st.columns([3, 1])
with top1:
    mode = st.radio(
        "Modo",
        options=["Trave", "Sistema"],
        horizontal=True,
        key=form_key("mode"),
        label_visibility="collapsed",
    )
with top2:
    if st.button("Nuovo", use_container_width=True):
        reset_form()
        st.rerun()

st.markdown("---")

if mode == "Trave":
    material_label = st.selectbox(
        "Materiale",
        ["Acciaio", "Legno"],
        key=form_key("beam_material"),
    )
    material = "steel" if material_label == "Acciaio" else "timber"

    st.caption("Preset uso")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abitazione", use_container_width=True, key=form_key("beam_res")):
            apply_beam_usage_preset("residential")
            st.rerun()
    with c2:
        if st.button("Copertura", use_container_width=True, key=form_key("beam_roof")):
            apply_beam_usage_preset("roof_not_walkable")
            st.rerun()

    c3, c4 = st.columns(2)
    with c3:
        if st.button("Balcone", use_container_width=True, key=form_key("beam_balcony")):
            apply_beam_usage_preset("balcony")
            st.rerun()
    with c4:
        if st.button("Carrabile", use_container_width=True, key=form_key("beam_vehicle")):
            apply_beam_usage_preset("light_vehicle")
            st.rerun()

    beam_usage_options = ["residential", "balcony", "roof_walkable", "roof_not_walkable", "light_vehicle"]
    beam_usage_index = beam_usage_options.index(st.session_state.beam_usage_key)

    usage_key = st.selectbox(
        "Uso",
        beam_usage_options,
        index=beam_usage_index,
        format_func=lambda key: ALL_USAGE_LABELS[key],
        key=form_key("beam_usage"),
    )

    load_mode_label = st.radio(
        "Carico",
        ["Auto", "Manuale"],
        horizontal=True,
        key=form_key("beam_load_mode"),
    )
    load_mode = "automatic" if load_mode_label == "Auto" else "manual"

    span_m = st.number_input(
        "Luce",
        min_value=0.1,
        value=5.00,
        step=0.10,
        format="%.2f",
        key=form_key("beam_span"),
    )

    support_label = st.selectbox(
        "Schema",
        ["Appoggiata", "Continua"],
        key=form_key("beam_support"),
    )
    support_type = "simply_supported" if support_label == "Appoggiata" else "continuous"

    if load_mode == "automatic":
        tributary_width_m = st.number_input(
            "Largh. trib.",
            min_value=0.1,
            value=3.00,
            step=0.10,
            format="%.2f",
            key=form_key("beam_tributary"),
        )
        manual_line_load_kN_m = None
    else:
        tributary_width_m = None
        manual_line_load_kN_m = st.number_input(
            "Carico lin.",
            min_value=0.1,
            value=10.0,
            step=0.5,
            format="%.2f",
            key=form_key("beam_manual"),
        )

    if material == "steel":
        max_height_mm = st.number_input(
            "H max (mm)",
            min_value=0.0,
            value=300.0,
            step=10.0,
            format="%.0f",
            key=form_key("beam_hmax_mm"),
        )
        effective_max_height_mm = max_height_mm if max_height_mm > 0 else None
        effective_max_height_cm = None
    else:
        max_height_cm = st.number_input(
            "H max (cm)",
            min_value=0.0,
            value=40.0,
            step=2.0,
            format="%.0f",
            key=form_key("beam_hmax_cm"),
        )
        effective_max_height_cm = max_height_cm if max_height_cm > 0 else None
        effective_max_height_mm = None

    if st.button("Calcola", type="primary", use_container_width=True, key=form_key("beam_calc")):
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
                action = get_mobile_suggestion("Trave", "Acciaio", status_family, reason)

                st.session_state.mobile_last_result = {
                    "title": "Trave acciaio",
                    "esito": status_family,
                    "soluzione": result.section_name,
                    "motivo": reason,
                    "azione": action,
                    "details": {
                        "Luce": f"{result.span_m:.2f} m",
                        "Carico": f"{result.adopted_line_load_kN_m:.2f} kN/m",
                        "Momento": f"{result.max_moment_kNm:.2f} kNm",
                        "Taglio": f"{result.max_shear_kN:.2f} kN",
                        "Freccia": f"{result.estimated_deflection_mm:.2f} mm",
                        "Dimensioni": f"{result.section_width_mm:.0f} x {result.section_height_mm:.0f} mm",
                        "Nota": result.note,
                        "Warnings": result.warnings,
                    },
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
                action = get_mobile_suggestion("Trave", "Legno", status_family, reason)

                st.session_state.mobile_last_result = {
                    "title": "Trave legno",
                    "esito": status_family,
                    "soluzione": result.section_name,
                    "motivo": reason,
                    "azione": action,
                    "details": {
                        "Luce": f"{result.span_m:.2f} m",
                        "Carico": f"{result.adopted_line_load_kN_m:.2f} kN/m",
                        "Momento": f"{result.max_moment_kNm:.2f} kNm",
                        "Taglio": f"{result.max_shear_kN:.2f} kN",
                        "Freccia": f"{result.estimated_deflection_mm:.2f} mm",
                        "Tipologia": result.timber_type,
                        "Sezione": f"{result.section_b_cm:.0f} x {result.section_h_cm:.0f} cm",
                        "Nota": result.note,
                        "Warnings": result.warnings,
                    },
                }

        except Exception as exc:
            st.session_state.mobile_last_result = {"error": f"Errore: {exc}"}

else:
    st.caption("Preset geometria")
    g1, g2 = st.columns(2)
    with g1:
        if st.button("4x4", use_container_width=True, key=form_key("g44")):
            apply_geometry_preset(4.0, 4.0)
            st.rerun()
    with g2:
        if st.button("5x4", use_container_width=True, key=form_key("g54")):
            apply_geometry_preset(5.0, 4.0)
            st.rerun()

    g3, g4 = st.columns(2)
    with g3:
        if st.button("6x5", use_container_width=True, key=form_key("g65")):
            apply_geometry_preset(6.0, 5.0)
            st.rerun()
    with g4:
        if st.button("8x4", use_container_width=True, key=form_key("g84")):
            apply_geometry_preset(8.0, 4.0)
            st.rerun()

    st.caption("Preset uso")
    u1, u2 = st.columns(2)
    with u1:
        if st.button("Abitazione", use_container_width=True, key=form_key("u_res")):
            apply_usage_preset("residential")
            st.rerun()
    with u2:
        if st.button("Copertura", use_container_width=True, key=form_key("u_roof")):
            apply_usage_preset("roof_not_walkable")
            st.rerun()

    u3, u4 = st.columns(2)
    with u3:
        if st.button("Balcone", use_container_width=True, key=form_key("u_bal")):
            apply_usage_preset("balcony")
            st.rerun()
    with u4:
        if st.button("Carrabile", use_container_width=True, key=form_key("u_car")):
            apply_usage_preset("light_vehicle")
            st.rerun()

    st.caption("Preset piano")
    p1, p2 = st.columns(2)
    with p1:
        if st.button("Legno", use_container_width=True, key=form_key("p_wood")):
            apply_floor_preset("timber", 2.5)
            st.rerun()
    with p2:
        if st.button("CA 20", use_container_width=True, key=form_key("p_ca20")):
            apply_floor_preset("concrete", 5.0)
            st.rerun()

    p3, p4 = st.columns(2)
    with p3:
        if st.button("3.0", use_container_width=True, key=form_key("p_30")):
            apply_floor_preset("manual", 3.0)
            st.rerun()
    with p4:
        if st.button("5.0", use_container_width=True, key=form_key("p_50")):
            apply_floor_preset("manual", 5.0)
            st.rerun()

    usage_options = ["residential", "balcony", "roof_walkable", "roof_not_walkable", "light_vehicle"]
    usage_index = usage_options.index(st.session_state.preset_usage_key)

    usage_key = st.selectbox(
        "Uso",
        usage_options,
        index=usage_index,
        format_func=lambda key: ALL_USAGE_LABELS[key],
        key=form_key("sys_usage"),
    )

    floor_type_index_map = {"manual": 0, "timber": 1, "concrete": 2}
    floor_type_label = st.selectbox(
        "Piano",
        ["Manuale", "Legno", "CA"],
        index=floor_type_index_map[st.session_state.preset_floor_type],
        key=form_key("sys_floor"),
    )

    if floor_type_label == "Manuale":
        floor_type = "manual"
    elif floor_type_label == "Legno":
        floor_type = "timber"
    else:
        floor_type = "concrete"

    beam_material_label = st.selectbox(
        "Travi",
        ["Acciaio", "Legno"],
        key=form_key("sys_beam_mat"),
    )
    beam_material = "steel" if beam_material_label == "Acciaio" else "timber"

    length_m = st.number_input(
        "Lung.",
        min_value=0.1,
        value=float(st.session_state.preset_length_m),
        step=0.10,
        format="%.2f",
        key=form_key("sys_L"),
    )

    width_m = st.number_input(
        "Largh.",
        min_value=0.1,
        value=float(st.session_state.preset_width_m),
        step=0.10,
        format="%.2f",
        key=form_key("sys_B"),
    )

    if floor_type == "manual":
        slab_dead_load_kN_m2 = st.number_input(
            "Peso piano",
            min_value=0.1,
            value=float(st.session_state.preset_slab_dead_load_kN_m2),
            step=0.1,
            format="%.2f",
            key=form_key("sys_q_manual"),
        )
    elif floor_type == "timber":
        slab_dead_load_kN_m2 = st.number_input(
            "Peso legno",
            min_value=0.1,
            value=2.5 if st.session_state.preset_floor_type != "timber" else float(st.session_state.preset_slab_dead_load_kN_m2),
            step=0.1,
            format="%.2f",
            key=form_key("sys_q_timber"),
        )
    else:
        concrete_thickness_cm = st.number_input(
            "Sp. CA",
            min_value=1.0,
            value=20.0,
            step=1.0,
            format="%.0f",
            key=form_key("sys_t_ca"),
        )
        slab_dead_load_kN_m2 = (concrete_thickness_cm / 100.0) * 25.0

    if beam_material == "steel":
        beam_max_height_mm = st.number_input(
            "H max travi",
            min_value=0.0,
            value=300.0,
            step=10.0,
            format="%.0f",
            key=form_key("sys_hmax_mm"),
        )
        effective_beam_max_height_mm = beam_max_height_mm if beam_max_height_mm > 0 else None
        effective_beam_max_height_cm = None
    else:
        beam_max_height_cm = st.number_input(
            "H max travi",
            min_value=0.0,
            value=40.0,
            step=2.0,
            format="%.0f",
            key=form_key("sys_hmax_cm"),
        )
        effective_beam_max_height_cm = beam_max_height_cm if beam_max_height_cm > 0 else None
        effective_beam_max_height_mm = None

    column_max_section_cm = st.number_input(
        "Sez. pil.",
        min_value=0.0,
        value=40.0,
        step=5.0,
        format="%.0f",
        key=form_key("sys_colmax"),
    )
    effective_column_max_section_cm = column_max_section_cm if column_max_section_cm > 0 else None

    if st.button("Calcola", type="primary", use_container_width=True, key=form_key("sys_calc")):
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
            action = get_mobile_suggestion("Sistema rapido", result.beam_material_label, status_family, reason)

            st.session_state.mobile_last_result = {
                "title": "Sistema rapido",
                "esito": status_family,
                "soluzione": (
                    f"L {result.long_beams.section_name} · "
                    f"C {result.short_beams.section_name} · "
                    f"P {result.columns.section_width_cm}x{result.columns.section_depth_cm}"
                ),
                "motivo": reason,
                "azione": action,
                "details": {
                    "Uso": result.usage,
                    "Dim.": f"{result.length_m:.2f} x {result.width_m:.2f} m",
                    "Sup.": f"{result.area_m2:.2f} m²",
                    "Piano": result.floor_label,
                    "Travi": result.beam_material_label,
                    "Q tot": f"{result.total_surface_load_kN_m2:.2f} kN/m²",
                    "Q sist": f"{result.total_load_kN:.2f} kN",
                    "Travi lunghe": f"{result.long_beams.section_name} · {result.long_beams.span_m:.2f} m · {result.long_beams.line_load_kN_m:.2f} kN/m · {result.long_beams.status}",
                    "Travi corte": f"{result.short_beams.section_name} · {result.short_beams.span_m:.2f} m · {result.short_beams.line_load_kN_m:.2f} kN/m · {result.short_beams.status}",
                    "Pilastri": f"{result.columns.section_width_cm} x {result.columns.section_depth_cm} cm · {result.columns.axial_load_per_column_kN:.2f} kN · {result.columns.status}",
                    "Nota": result.note,
                    "Warnings": result.warnings,
                },
            }

        except Exception as exc:
            st.session_state.mobile_last_result = {"error": f"Errore: {exc}"}

last_result = st.session_state.mobile_last_result
if last_result:
    st.markdown("---")
    if "error" in last_result:
        st.error(last_result["error"])
    else:
        show_result_card(
            title=last_result["title"],
            esito=last_result["esito"],
            soluzione=last_result["soluzione"],
            motivo=last_result["motivo"],
            azione=last_result["azione"],
        )

        with st.expander("Dettagli"):
            for key, value in last_result["details"].items():
                if key == "Warnings":
                    for warning in value:
                        st.warning(warning)
                else:
                    st.write(f"**{key}:** {value}")

        if st.button("Nuovo calcolo", use_container_width=True, key=form_key("bottom_reset")):
            reset_form()
            st.rerun()

st.caption("Mobile final")