import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, PRIORITY_LABELS
from core.utils import PRIORITY_EMOJIS, confirm_delete, export_csv, get_area_id


def render():
    st.header("Tareas")

    tareas = get_df("tareas")
    proyectos = get_df("proyectos")

    # --- View toggle ---
    col_view, col_spacer = st.columns([2, 4])
    with col_view:
        view_mode = st.radio("Vista", ["Lista", "Kanban"], horizontal=True, key="tareas_view", label_visibility="collapsed")

    # --- Toolbar ---
    col_filter, col_area, col_export, col_add = st.columns([2, 2, 1, 1])
    with col_filter:
        status_filter = st.selectbox("Estado", ["Pendientes", "Completadas", "Todas"], label_visibility="collapsed")
    with col_area:
        area_options = ["Todas las areas"] + [f'{a["emoji"]} {a["name"]}' for a in AREAS]
        area_filter = st.selectbox("Area", area_options, label_visibility="collapsed", key="tarea_area_f")
    with col_export:
        export_csv(tareas, "tareas.csv", "\U0001f4e5 CSV")
    with col_add:
        add_tarea = st.button("+ Tarea", type="primary", use_container_width=True)

    # --- Add/Edit form ---
    if add_tarea:
        st.session_state["tarea_editing"] = True
        st.session_state["tarea_edit_id"] = None

    if st.session_state.get("tarea_editing"):
        edit_id = st.session_state.get("tarea_edit_id")
        existing = None
        if edit_id and not tareas.empty:
            matches = tareas[tareas["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("tarea_form", clear_on_submit=True):
            st.subheader("Editar tarea" if existing is not None else "Nueva tarea")
            titulo = st.text_input("Titulo", value=existing["titulo"] if existing is not None else "")
            c1, c2 = st.columns(2)
            area_ids = [a["id"] for a in AREAS]
            area = c1.selectbox("Area", area_ids, format_func=lambda x: AREA_LABELS.get(x, x),
                                index=area_ids.index(existing["area"]) if existing is not None and existing["area"] in area_ids else 0)
            pri_opts = ["alta", "media", "baja"]
            prioridad = c2.selectbox("Prioridad", pri_opts, format_func=lambda x: PRIORITY_LABELS.get(x, x),
                                     index=pri_opts.index(existing["prioridad"]) if existing is not None and existing["prioridad"] in pri_opts else 1)

            c3, c4 = st.columns(2)
            fecha = c3.date_input("Fecha limite (opcional)", value=None)
            proj_options = [""] + (proyectos["id"].tolist() if not proyectos.empty else [])
            proj_labels = ["Sin proyecto"] + (proyectos["nombre"].tolist() if not proyectos.empty else [])
            proj_idx = 0
            if existing is not None and existing.get("proyecto") in proj_options:
                proj_idx = proj_options.index(existing["proyecto"])
            proyecto = c4.selectbox("Proyecto", proj_options, format_func=lambda x: proj_labels[proj_options.index(x)] if x in proj_options else x, index=proj_idx)

            notas_txt = st.text_area("Notas", value=existing["notas"] if existing is not None else "", height=80)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                new_row = {
                    "id": edit_id or uid(),
                    "titulo": titulo.strip(),
                    "area": area,
                    "prioridad": prioridad,
                    "fecha": str(fecha) if fecha else "",
                    "proyecto": proyecto,
                    "notas": notas_txt,
                    "done": existing["done"] if existing is not None else False,
                    "ts": now_ts(),
                }
                if edit_id and not tareas.empty:
                    tareas = tareas[tareas["id"] != edit_id]
                new_df = pd.concat([pd.DataFrame([new_row]), tareas], ignore_index=True)
                save_df("tareas", new_df)
                st.session_state["tarea_editing"] = False
                st.session_state["tarea_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["tarea_editing"] = False
                st.session_state["tarea_edit_id"] = None
                st.rerun()

    # --- Filter ---
    filtered = tareas.copy()
    if not filtered.empty:
        if status_filter == "Pendientes":
            filtered = filtered[~filtered["done"]]
        elif status_filter == "Completadas":
            filtered = filtered[filtered["done"]]

        if area_filter != "Todas las areas":
            area_id = get_area_id(area_filter)
            if area_id:
                filtered = filtered[filtered["area"] == area_id]

        pri_order = {"alta": 0, "media": 1, "baja": 2}
        filtered["_done_ord"] = filtered["done"].astype(int)
        filtered["_pri_ord"] = filtered["prioridad"].map(pri_order).fillna(2)
        filtered = filtered.sort_values(["_done_ord", "_pri_ord"])

    # --- Display ---
    if filtered.empty:
        st.info("No hay tareas. Crea una con '+ Tarea'.")
        return

    if view_mode == "Kanban":
        _render_kanban(filtered, tareas)
        return

    for _, t in filtered.iterrows():
        pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "\u26aa")
        area_label = AREA_LABELS.get(t["area"], t["area"])
        fecha_str = f" \U0001f4c5 {t['fecha']}" if t.get("fecha") else ""

        col_check, col_body, col_edit, col_del = st.columns([0.5, 7, 0.5, 0.5])
        with col_check:
            done = st.checkbox("", value=t["done"], key=f"tcheck_{t['id']}", label_visibility="collapsed")
            if done != t["done"]:
                tareas.loc[tareas["id"] == t["id"], "done"] = done
                save_df("tareas", tareas)
                st.rerun()
        with col_body:
            style = "~~" if t["done"] else ""
            st.markdown(f"{pri_emoji} {style}**{t['titulo']}**{style} \u2022 {area_label}{fecha_str}")
        with col_edit:
            if st.button("\u270f\ufe0f", key=f"tedit_{t['id']}"):
                st.session_state["tarea_editing"] = True
                st.session_state["tarea_edit_id"] = t["id"]
                st.rerun()
        with col_del:
            if confirm_delete(t["id"], t["titulo"], "tarea"):
                tareas = tareas[tareas["id"] != t["id"]]
                save_df("tareas", tareas)
                st.rerun()


def _render_kanban(filtered, tareas):
    col_alta, col_media, col_baja, col_done = st.columns(4)

    with col_alta:
        st.markdown("### \U0001f534 Alta")
        alta = filtered[(~filtered["done"]) & (filtered["prioridad"] == "alta")]
        for _, t in alta.iterrows():
            with st.container(border=True):
                st.markdown(f"**{t['titulo']}**")
                st.caption(AREA_LABELS.get(t["area"], t["area"]))
                if t.get("fecha"):
                    st.caption(f"\U0001f4c5 {t['fecha']}")
                if st.checkbox("Hecho", key=f"kb_done_{t['id']}"):
                    tareas.loc[tareas["id"] == t["id"], "done"] = True
                    save_df("tareas", tareas)
                    st.rerun()

    with col_media:
        st.markdown("### \U0001f7e1 Media")
        media = filtered[(~filtered["done"]) & (filtered["prioridad"] == "media")]
        for _, t in media.iterrows():
            with st.container(border=True):
                st.markdown(f"**{t['titulo']}**")
                st.caption(AREA_LABELS.get(t["area"], t["area"]))
                if t.get("fecha"):
                    st.caption(f"\U0001f4c5 {t['fecha']}")
                if st.checkbox("Hecho", key=f"kb_done_{t['id']}"):
                    tareas.loc[tareas["id"] == t["id"], "done"] = True
                    save_df("tareas", tareas)
                    st.rerun()

    with col_baja:
        st.markdown("### \U0001f7e2 Baja")
        baja = filtered[(~filtered["done"]) & (filtered["prioridad"] == "baja")]
        for _, t in baja.iterrows():
            with st.container(border=True):
                st.markdown(f"**{t['titulo']}**")
                st.caption(AREA_LABELS.get(t["area"], t["area"]))
                if t.get("fecha"):
                    st.caption(f"\U0001f4c5 {t['fecha']}")
                if st.checkbox("Hecho", key=f"kb_done_{t['id']}"):
                    tareas.loc[tareas["id"] == t["id"], "done"] = True
                    save_df("tareas", tareas)
                    st.rerun()

    with col_done:
        st.markdown("### \u2705 Hechas")
        done = filtered[filtered["done"]]
        for _, t in done.iterrows():
            with st.container(border=True):
                st.markdown(f"~~{t['titulo']}~~")
                st.caption(AREA_LABELS.get(t["area"], t["area"]))
