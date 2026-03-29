import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS


def render():
    st.header("Proyectos")

    proyectos = get_df("proyectos")
    tareas = get_df("tareas")

    col_spacer, col_add = st.columns([5, 1])
    with col_add:
        add_proj = st.button("+ Proyecto", type="primary", use_container_width=True)

    if add_proj:
        st.session_state["proj_adding"] = True

    if st.session_state.get("proj_adding"):
        with st.form("proj_form", clear_on_submit=True):
            st.subheader("Nuevo proyecto")
            c1, c2 = st.columns([3, 1])
            nombre = c1.text_input("Nombre")
            emoji = c2.text_input("Emoji", value="\U0001f4c1")
            area = st.selectbox("Area", [a["id"] for a in AREAS], format_func=lambda x: AREA_LABELS.get(x, x))
            desc = st.text_area("Descripcion", height=80)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and nombre.strip():
                new_row = {
                    "id": uid(),
                    "nombre": nombre.strip(),
                    "area": area,
                    "emoji": emoji or "\U0001f4c1",
                    "desc": desc,
                    "ts": now_ts(),
                }
                new_df = pd.concat([pd.DataFrame([new_row]), proyectos], ignore_index=True)
                save_df("proyectos", new_df)
                st.session_state["proj_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["proj_adding"] = False
                st.rerun()

    # --- Display ---
    if proyectos.empty:
        st.info("No hay proyectos. Crea uno con '+ Proyecto'.")
        return

    cols = st.columns(2)
    for i, (_, p) in enumerate(proyectos.iterrows()):
        with cols[i % 2]:
            area_label = AREA_LABELS.get(p["area"], p["area"])

            # Calculate progress from linked tasks
            proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
            total_tasks = len(proj_tasks)
            done_tasks = proj_tasks["done"].sum() if total_tasks > 0 else 0
            pct = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

            with st.container(border=True):
                proj_emoji = p.get('emoji', '\U0001f4c1')
                st.markdown(f"### {proj_emoji} {p['nombre']}")
                st.caption(f"{area_label}")
                if p.get("desc"):
                    st.markdown(p["desc"])

                st.progress(pct / 100, text=f"{pct}% completado")
                st.caption(f"{total_tasks} tareas \u2022 {int(done_tasks)} hechas")

                if st.button("\U0001f5d1 Eliminar", key=f"pdel_{p['id']}"):
                    proyectos = proyectos[proyectos["id"] != p["id"]]
                    save_df("proyectos", proyectos)
                    st.rerun()
