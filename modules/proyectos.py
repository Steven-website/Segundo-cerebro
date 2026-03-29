import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS
from core.utils import confirm_delete, export_csv


def render():
    st.header("Proyectos")

    proyectos = get_df("proyectos")
    tareas = get_df("tareas")

    col_export, col_add = st.columns([5, 1])
    with col_export:
        export_csv(proyectos, "proyectos.csv", "\U0001f4e5 Exportar CSV")
    with col_add:
        add_proj = st.button("+ Proyecto", type="primary", use_container_width=True)

    if add_proj:
        st.session_state["proj_editing"] = True
        st.session_state["proj_edit_id"] = None

    if st.session_state.get("proj_editing"):
        edit_id = st.session_state.get("proj_edit_id")
        existing = None
        if edit_id and not proyectos.empty:
            matches = proyectos[proyectos["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("proj_form", clear_on_submit=True):
            st.subheader("Editar proyecto" if existing is not None else "Nuevo proyecto")
            c1, c2 = st.columns([3, 1])
            nombre = c1.text_input("Nombre", value=existing["nombre"] if existing is not None else "")
            emoji = c2.text_input("Emoji", value=existing.get("emoji", "\U0001f4c1") if existing is not None else "\U0001f4c1")
            area_ids = [a["id"] for a in AREAS]
            area = st.selectbox("Area", area_ids, format_func=lambda x: AREA_LABELS.get(x, x),
                                index=area_ids.index(existing["area"]) if existing is not None and existing["area"] in area_ids else 0)
            desc = st.text_area("Descripcion", value=existing["desc"] if existing is not None else "", height=80)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and nombre.strip():
                new_row = {
                    "id": edit_id or uid(),
                    "nombre": nombre.strip(),
                    "area": area,
                    "emoji": emoji or "\U0001f4c1",
                    "desc": desc,
                    "ts": now_ts(),
                }
                if edit_id and not proyectos.empty:
                    proyectos = proyectos[proyectos["id"] != edit_id]
                new_df = pd.concat([pd.DataFrame([new_row]), proyectos], ignore_index=True)
                save_df("proyectos", new_df)
                st.session_state["proj_editing"] = False
                st.session_state["proj_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["proj_editing"] = False
                st.session_state["proj_edit_id"] = None
                st.rerun()

    # --- Display ---
    if proyectos.empty:
        st.info("No hay proyectos. Crea uno con '+ Proyecto'.")
        return

    cols = st.columns(2)
    for i, (_, p) in enumerate(proyectos.iterrows()):
        with cols[i % 2]:
            area_label = AREA_LABELS.get(p["area"], p["area"])

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

                c_edit, c_del = st.columns(2)
                with c_edit:
                    if st.button("\u270f\ufe0f Editar", key=f"pedit_{p['id']}", use_container_width=True):
                        st.session_state["proj_editing"] = True
                        st.session_state["proj_edit_id"] = p["id"]
                        st.rerun()
                with c_del:
                    if confirm_delete(p["id"], p["nombre"], "proj"):
                        proyectos = proyectos[proyectos["id"] != p["id"]]
                        save_df("proyectos", proyectos)
                        st.rerun()
