import streamlit as st
import pandas as pd
from datetime import datetime
from core.data import get_df, save_df, uid, now_ts
from core.utils import confirm_delete, export_csv


def render():
    st.header("Metas")
    st.caption("Define objetivos semanales y mensuales y mide tu avance")

    metas = get_df("metas")

    col_exp, col_add = st.columns([5, 1])
    with col_exp:
        export_csv(metas, "metas.csv", "CSV")
    with col_add:
        if st.button("+ Meta", type="primary", use_container_width=True):
            st.session_state["meta_editing"] = True
            st.session_state["meta_edit_id"] = None

    # --- Add/Edit form ---
    if st.session_state.get("meta_editing"):
        edit_id = st.session_state.get("meta_edit_id")
        existing = None
        if edit_id and not metas.empty:
            matches = metas[metas["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("meta_form", clear_on_submit=True):
            st.subheader("Editar meta" if existing is not None else "Nueva meta")
            titulo = st.text_input("Que quieres lograr?", value=existing["titulo"] if existing is not None else "",
                                   placeholder="Ej: Completar 5 tareas, Ahorrar 50,000, Hacer ejercicio 4 dias...")
            c1, c2 = st.columns(2)
            tipo_opts = ["productividad", "finanzas", "salud", "aprendizaje", "otro"]
            tipo = c1.selectbox("Tipo", tipo_opts,
                                format_func=lambda x: {"productividad": "Productividad", "finanzas": "Finanzas",
                                                       "salud": "Salud", "aprendizaje": "Aprendizaje", "otro": "Otro"}.get(x, x),
                                index=tipo_opts.index(existing["tipo"]) if existing is not None and existing["tipo"] in tipo_opts else 0)
            periodo_opts = ["semanal", "mensual", "trimestral"]
            periodo = c2.selectbox("Periodo", periodo_opts,
                                   format_func=lambda x: x.capitalize(),
                                   index=periodo_opts.index(existing["periodo"]) if existing is not None and existing["periodo"] in periodo_opts else 0)

            objetivo = st.text_input("Objetivo especifico (medible)",
                                     value=existing["objetivo"] if existing is not None else "",
                                     placeholder="Ej: 5 tareas, 50000 colones, 4 sesiones...")
            progreso = st.slider("Progreso actual (%)", 0, 100,
                                 value=int(existing["progreso"]) if existing is not None else 0)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                new_row = {
                    "id": edit_id or uid(),
                    "titulo": titulo.strip(),
                    "tipo": tipo,
                    "periodo": periodo,
                    "objetivo": objetivo,
                    "progreso": float(progreso),
                    "completada": progreso >= 100,
                    "ts": now_ts(),
                }
                if edit_id and not metas.empty:
                    metas = metas[metas["id"] != edit_id]
                save_df("metas", pd.concat([pd.DataFrame([new_row]), metas], ignore_index=True))
                st.session_state["meta_editing"] = False
                st.session_state["meta_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["meta_editing"] = False
                st.session_state["meta_edit_id"] = None
                st.rerun()

    # --- Display ---
    if metas.empty:
        st.info("No hay metas definidas. Crea una con '+ Meta'.")
        return

    TIPO_EMOJIS = {"productividad": "🎯", "finanzas": "💰", "salud": "💪", "aprendizaje": "📚", "otro": "⭐"}

    # Separate active vs completed
    tab_active, tab_done = st.tabs(["Activas", "Completadas"])

    with tab_active:
        active = metas[~metas["completada"].fillna(False)]
        if active.empty:
            st.success("Todas las metas estan completadas!")
        else:
            for _, m in active.iterrows():
                _render_meta(m, metas, TIPO_EMOJIS)

    with tab_done:
        done = metas[metas["completada"].fillna(False)]
        if done.empty:
            st.info("No hay metas completadas aun.")
        else:
            for _, m in done.iterrows():
                _render_meta(m, metas, TIPO_EMOJIS)


def _render_meta(m, metas, tipo_emojis):
    with st.container(border=True):
        c1, c2 = st.columns([5, 1])
        with c1:
            emoji = tipo_emojis.get(m["tipo"], "⭐")
            periodo_label = m.get("periodo", "").capitalize()
            st.markdown(f"### {emoji} {m['titulo']}")
            st.caption(f"{periodo_label} | {m['tipo'].capitalize()}")
            if m.get("objetivo"):
                st.markdown(f"**Objetivo:** {m['objetivo']}")
            pct = min(m["progreso"] / 100, 1.0)
            st.progress(pct, text=f"{int(m['progreso'])}%")
        with c2:
            if st.button("✏️", key=f"meta_edit_{m['id']}"):
                st.session_state["meta_editing"] = True
                st.session_state["meta_edit_id"] = m["id"]
                st.rerun()
            # Quick progress update
            new_prog = st.number_input("%", min_value=0, max_value=100,
                                       value=int(m["progreso"]), key=f"meta_prog_{m['id']}",
                                       label_visibility="collapsed")
            if new_prog != int(m["progreso"]):
                metas.loc[metas["id"] == m["id"], "progreso"] = float(new_prog)
                metas.loc[metas["id"] == m["id"], "completada"] = new_prog >= 100
                save_df("metas", metas)
                st.rerun()
            if confirm_delete(m["id"], m["titulo"], "meta"):
                metas = metas[metas["id"] != m["id"]]
                save_df("metas", metas)
                st.rerun()
