import streamlit as st
import pandas as pd
from datetime import datetime
from core.data import get_df, save_df, uid, now_ts
from core.utils import confirm_delete, export_csv


TIPO_EMOJIS = {"productividad": "🎯", "finanzas": "💰", "salud": "💪", "aprendizaje": "📚", "otro": "⭐"}


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

            # Link to project for auto-progress
            proyectos = get_df("proyectos")
            proj_options = ["Ninguno (progreso manual)"]
            proj_ids = [""]
            if not proyectos.empty:
                for _, p in proyectos.iterrows():
                    proj_emoji = p.get("emoji", "📁")
                    proj_options.append(f"{proj_emoji} {p['nombre']}")
                    proj_ids.append(p["id"])

            existing_proj = existing.get("proyecto_id", "") if existing is not None else ""
            proj_default = proj_ids.index(existing_proj) if existing_proj in proj_ids else 0
            proj_idx = st.selectbox("Vincular a proyecto (progreso automatico)", range(len(proj_options)),
                                    format_func=lambda i: proj_options[i], index=proj_default)

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
                    "proyecto_id": proj_ids[proj_idx],
                    "ts": now_ts(),
                }
                if edit_id and not metas.empty:
                    metas = metas[metas["id"] != edit_id]
                save_df("metas", pd.concat([pd.DataFrame([new_row]), metas], ignore_index=True))
                _record_progress(new_row["id"], new_row["progreso"])
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

    # Auto-update progress for project-linked goals
    _auto_update_progress(metas)

    # Separate active vs completed
    tab_active, tab_done = st.tabs(["Activas", "Completadas"])

    with tab_active:
        active = metas[~metas["completada"].fillna(False)]
        if active.empty:
            st.success("Todas las metas estan completadas!")
        else:
            for _, m in active.iterrows():
                _render_meta(m, metas)

    with tab_done:
        done = metas[metas["completada"].fillna(False)]
        if done.empty:
            st.info("No hay metas completadas aun.")
        else:
            for _, m in done.iterrows():
                _render_meta(m, metas)

    # History panel
    hist_id = st.session_state.get("meta_hist_id")
    if hist_id:
        _render_history(hist_id, metas)


def _render_history(meta_id, metas):
    """Show progress history chart for a goal."""
    meta_match = metas[metas["id"] == meta_id]
    if meta_match.empty:
        return

    meta = meta_match.iloc[0]
    hist = get_df("metas_hist")
    meta_hist = hist[hist["meta_id"] == meta_id].sort_values("fecha") if not hist.empty else pd.DataFrame()

    st.divider()
    col_t, col_close = st.columns([5, 1])
    with col_t:
        emoji = TIPO_EMOJIS.get(meta["tipo"], "⭐")
        st.subheader(f"📈 Historial: {emoji} {meta['titulo']}")
    with col_close:
        if st.button("Cerrar", key="close_hist"):
            st.session_state["meta_hist_id"] = None
            st.rerun()

    if meta_hist.empty:
        st.info("No hay historial de progreso aun. El historial se registra cada vez que cambia el progreso.")
        return

    # Chart
    chart_data = meta_hist[["fecha", "progreso"]].copy()
    chart_data = chart_data.rename(columns={"fecha": "Fecha", "progreso": "Progreso %"})
    chart_data = chart_data.set_index("Fecha")
    st.line_chart(chart_data, color=["#c9943a"])

    # Stats
    c1, c2, c3 = st.columns(3)
    c1.metric("Progreso actual", f"{int(meta['progreso'])}%")
    if len(meta_hist) >= 2:
        first = meta_hist.iloc[0]["progreso"]
        last = meta_hist.iloc[-1]["progreso"]
        c2.metric("Avance total", f"{int(last - first)}%")
    c3.metric("Registros", len(meta_hist))

    # Detail list
    with st.expander("Detalle de cambios"):
        for _, h in meta_hist.iterrows():
            st.caption(f"**{h['fecha']}** — {int(h['progreso'])}%")


def _record_progress(meta_id, progreso):
    """Record a progress snapshot for a goal."""
    hist = get_df("metas_hist")
    today = datetime.now().strftime("%Y-%m-%d")
    # Avoid duplicate entries for same meta + same day + same value
    if not hist.empty:
        existing = hist[(hist["meta_id"] == meta_id) & (hist["fecha"] == today) & (hist["progreso"] == progreso)]
        if not existing.empty:
            return
    new_entry = {
        "id": uid(), "meta_id": meta_id,
        "progreso": float(progreso), "fecha": today, "ts": now_ts(),
    }
    hist = pd.concat([pd.DataFrame([new_entry]), hist], ignore_index=True)
    save_df("metas_hist", hist)


def _auto_update_progress(metas):
    """Auto-calculate progress for goals linked to projects."""
    tareas = get_df("tareas")
    updated = False
    for idx, m in metas.iterrows():
        proj_id = m.get("proyecto_id", "")
        if not proj_id or tareas.empty:
            continue
        proj_tasks = tareas[tareas["proyecto"] == proj_id]
        if proj_tasks.empty:
            continue
        total = len(proj_tasks)
        done = int(proj_tasks["done"].sum())
        new_prog = int(done / total * 100)
        if new_prog != int(m["progreso"]):
            metas.loc[metas["id"] == m["id"], "progreso"] = float(new_prog)
            metas.loc[metas["id"] == m["id"], "completada"] = new_prog >= 100
            _record_progress(m["id"], new_prog)
            updated = True
    if updated:
        save_df("metas", metas)


def _render_meta(m, metas):
    with st.container(border=True):
        c1, c2 = st.columns([5, 1])
        with c1:
            emoji = TIPO_EMOJIS.get(m["tipo"], "⭐")
            periodo_label = m.get("periodo", "").capitalize()
            st.markdown(f"### {emoji} {m['titulo']}")
            info_parts = [periodo_label, m['tipo'].capitalize()]
            if m.get("proyecto_id"):
                proyectos = get_df("proyectos")
                if not proyectos.empty:
                    proj_match = proyectos[proyectos["id"] == m["proyecto_id"]]
                    if not proj_match.empty:
                        p = proj_match.iloc[0]
                        info_parts.append(f"📁 {p.get('emoji', '')} {p['nombre']}")
            st.caption(" | ".join(info_parts))
            if m.get("objetivo"):
                st.markdown(f"**Objetivo:** {m['objetivo']}")
            pct = min(m["progreso"] / 100, 1.0)
            auto_label = " (auto)" if m.get("proyecto_id") else ""
            st.progress(pct, text=f"{int(m['progreso'])}%{auto_label}")
        with c2:
            if st.button("✏️", key=f"meta_edit_{m['id']}"):
                st.session_state["meta_editing"] = True
                st.session_state["meta_edit_id"] = m["id"]
                st.rerun()
            if st.button("📈", key=f"meta_hist_{m['id']}", help="Ver historial"):
                st.session_state["meta_hist_id"] = m["id"]
                st.rerun()
            # Quick progress update (only for manual goals)
            if not m.get("proyecto_id"):
                new_prog = st.number_input("%", min_value=0, max_value=100,
                                           value=int(m["progreso"]), key=f"meta_prog_{m['id']}",
                                           label_visibility="collapsed")
                if new_prog != int(m["progreso"]):
                    metas.loc[metas["id"] == m["id"], "progreso"] = float(new_prog)
                    metas.loc[metas["id"] == m["id"], "completada"] = new_prog >= 100
                    _record_progress(m["id"], new_prog)
                    save_df("metas", metas)
                    st.rerun()
            if confirm_delete(m["id"], m["titulo"], "meta"):
                metas = metas[metas["id"] != m["id"]]
                save_df("metas", metas)
                st.rerun()
