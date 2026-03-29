import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, PRIORITY_LABELS


def render():
    st.header("Tareas")

    tareas = get_df("tareas")
    proyectos = get_df("proyectos")

    # --- Toolbar ---
    col_filter, col_area, col_add = st.columns([2, 2, 1])
    with col_filter:
        status_filter = st.selectbox("Estado", ["Pendientes", "Completadas", "Todas"], label_visibility="collapsed")
    with col_area:
        area_options = ["Todas las areas"] + [f'{a["emoji"]} {a["name"]}' for a in AREAS]
        area_filter = st.selectbox("Area", area_options, label_visibility="collapsed", key="tarea_area_f")
    with col_add:
        add_tarea = st.button("+ Tarea", type="primary", use_container_width=True)

    # --- Add form ---
    if add_tarea:
        st.session_state["tarea_adding"] = True

    if st.session_state.get("tarea_adding"):
        with st.form("tarea_form", clear_on_submit=True):
            st.subheader("Nueva tarea")
            titulo = st.text_input("Titulo")
            c1, c2 = st.columns(2)
            area = c1.selectbox("Area", [a["id"] for a in AREAS], format_func=lambda x: AREA_LABELS.get(x, x))
            prioridad = c2.selectbox("Prioridad", ["alta", "media", "baja"], format_func=lambda x: PRIORITY_LABELS.get(x, x), index=1)

            c3, c4 = st.columns(2)
            fecha = c3.date_input("Fecha limite (opcional)", value=None)
            proj_options = [""] + (proyectos["id"].tolist() if not proyectos.empty else [])
            proj_labels = ["Sin proyecto"] + (proyectos["nombre"].tolist() if not proyectos.empty else [])
            proyecto = c4.selectbox("Proyecto", proj_options, format_func=lambda x: proj_labels[proj_options.index(x)] if x in proj_options else x)

            notas_txt = st.text_area("Notas", height=80)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                new_row = {
                    "id": uid(),
                    "titulo": titulo.strip(),
                    "area": area,
                    "prioridad": prioridad,
                    "fecha": str(fecha) if fecha else "",
                    "proyecto": proyecto,
                    "notas": notas_txt,
                    "done": False,
                    "ts": now_ts(),
                }
                new_df = pd.concat([pd.DataFrame([new_row]), tareas], ignore_index=True)
                save_df("tareas", new_df)
                st.session_state["tarea_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["tarea_adding"] = False
                st.rerun()

    # --- Filter ---
    filtered = tareas.copy()
    if not filtered.empty:
        if status_filter == "Pendientes":
            filtered = filtered[~filtered["done"]]
        elif status_filter == "Completadas":
            filtered = filtered[filtered["done"]]

        if area_filter != "Todas las areas":
            area_id = next((a["id"] for a in AREAS if f'{a["emoji"]} {a["name"]}' == area_filter), None)
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

    for _, t in filtered.iterrows():
        pri_emoji = {
            "alta": "\U0001f534",
            "media": "\U0001f7e1",
            "baja": "\U0001f7e2",
        }.get(t["prioridad"], "\u26aa")
        area_label = AREA_LABELS.get(t["area"], t["area"])
        fecha_str = f" \U0001f4c5 {t['fecha']}" if t.get("fecha") else ""

        col_check, col_body, col_del = st.columns([0.5, 8, 0.5])
        with col_check:
            done = st.checkbox("", value=t["done"], key=f"tcheck_{t['id']}", label_visibility="collapsed")
            if done != t["done"]:
                tareas.loc[tareas["id"] == t["id"], "done"] = done
                save_df("tareas", tareas)
                st.rerun()
        with col_body:
            style = "~~" if t["done"] else ""
            st.markdown(f"{pri_emoji} {style}**{t['titulo']}**{style} \u2022 {area_label}{fecha_str}")
        with col_del:
            if st.button("\U0001f5d1", key=f"tdel_{t['id']}"):
                tareas = tareas[tareas["id"] != t["id"]]
                save_df("tareas", tareas)
                st.rerun()
