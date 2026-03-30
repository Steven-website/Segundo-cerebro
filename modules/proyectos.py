import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS
from core.utils import confirm_delete, export_csv


# --- Project templates ---
TEMPLATES = {
    "Lanzamiento web": {
        "emoji": "🌐",
        "desc": "Plantilla para lanzar un sitio web",
        "tasks": [
            "Definir requisitos y alcance",
            "Disenar wireframes / mockups",
            "Configurar dominio y hosting",
            "Desarrollar frontend",
            "Desarrollar backend / API",
            "Integrar base de datos",
            "Pruebas funcionales",
            "Pruebas de rendimiento",
            "Configurar SSL y seguridad",
            "Despliegue a produccion",
        ],
    },
    "App movil": {
        "emoji": "📱",
        "desc": "Plantilla para desarrollar una app movil",
        "tasks": [
            "Investigacion y planificacion",
            "Disenar UI/UX",
            "Configurar proyecto (React Native / Flutter)",
            "Pantallas principales",
            "Navegacion y routing",
            "Integracion con API",
            "Autenticacion de usuarios",
            "Pruebas en dispositivos",
            "Publicar en App Store / Play Store",
        ],
    },
    "Marketing digital": {
        "emoji": "📣",
        "desc": "Plantilla para campana de marketing",
        "tasks": [
            "Definir objetivos y KPIs",
            "Investigar audiencia objetivo",
            "Crear contenido (copy, imagenes, video)",
            "Configurar redes sociales",
            "Configurar anuncios pagados",
            "Email marketing - crear secuencia",
            "Landing page",
            "Monitorear metricas",
            "Ajustar estrategia segun resultados",
        ],
    },
    "Evento": {
        "emoji": "🎉",
        "desc": "Plantilla para organizar un evento",
        "tasks": [
            "Definir fecha y lugar",
            "Crear presupuesto",
            "Enviar invitaciones",
            "Contratar proveedores",
            "Preparar decoracion",
            "Confirmar asistentes",
            "Logistica del dia",
            "Seguimiento post-evento",
        ],
    },
}


def render():
    st.header("Proyectos")

    proyectos = get_df("proyectos")
    tareas = get_df("tareas")

    col_tmpl, col_export, col_add = st.columns([2, 1, 1])
    with col_tmpl:
        if st.button("📋 Usar plantilla", use_container_width=True):
            st.session_state["show_templates"] = True
    with col_export:
        export_csv(proyectos, "proyectos.csv", "CSV")
    with col_add:
        add_proj = st.button("+ Proyecto", type="primary", use_container_width=True)

    # --- Templates ---
    if st.session_state.get("show_templates"):
        st.divider()
        st.subheader("Plantillas de proyectos")
        st.caption("Selecciona una plantilla para crear un proyecto con tareas predefinidas")

        template_cols = st.columns(2)
        for i, (name, tmpl) in enumerate(TEMPLATES.items()):
            with template_cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"### {tmpl['emoji']} {name}")
                    st.caption(tmpl["desc"])
                    st.caption(f"{len(tmpl['tasks'])} tareas incluidas")
                    if st.button(f"Usar plantilla", key=f"tmpl_{name}", use_container_width=True, type="primary"):
                        _create_from_template(name, tmpl, proyectos, tareas)
                        st.session_state["show_templates"] = False
                        st.rerun()

        if st.button("Cancelar"):
            st.session_state["show_templates"] = False
            st.rerun()
        st.divider()

    # --- Add/Edit form ---
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
            emoji = c2.text_input("Emoji", value=existing.get("emoji", "📁") if existing is not None else "📁")
            area_ids = [a["id"] for a in AREAS]
            area = st.selectbox("Area", area_ids, format_func=lambda x: AREA_LABELS.get(x, x),
                                index=area_ids.index(existing["area"]) if existing is not None and existing["area"] in area_ids else 0)
            desc = st.text_area("Descripcion", value=existing["desc"] if existing is not None else "", height=80)

            # Sharing
            compartido = st.text_input("Compartir con usuarios (separar por coma)",
                                       value=existing.get("compartido", "") if existing is not None else "",
                                       placeholder="usuario1, usuario2",
                                       help="Estos usuarios podran ver este proyecto y sus tareas")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and nombre.strip():
                new_row = {
                    "id": edit_id or uid(),
                    "nombre": nombre.strip(),
                    "area": area,
                    "emoji": emoji or "📁",
                    "desc": desc,
                    "plantilla": False,
                    "compartido": compartido,
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
        st.info("No hay proyectos. Crea uno con '+ Proyecto' o usa una plantilla.")
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
                proj_emoji = p.get('emoji', '📁')
                st.markdown(f"### {proj_emoji} {p['nombre']}")
                st.caption(f"{area_label}")
                if p.get("desc"):
                    st.markdown(p["desc"])
                if p.get("compartido", ""):
                    st.caption(f"👥 Compartido con: {p['compartido']}")

                st.progress(pct / 100, text=f"{pct}% completado")
                st.caption(f"{total_tasks} tareas | {int(done_tasks)} hechas")

                c_edit, c_del = st.columns(2)
                with c_edit:
                    if st.button("✏️ Editar", key=f"pedit_{p['id']}", use_container_width=True):
                        st.session_state["proj_editing"] = True
                        st.session_state["proj_edit_id"] = p["id"]
                        st.rerun()
                with c_del:
                    if confirm_delete(p["id"], p["nombre"], "proj"):
                        proyectos = proyectos[proyectos["id"] != p["id"]]
                        save_df("proyectos", proyectos)
                        st.rerun()


def _create_from_template(template_name, template, proyectos, tareas):
    """Create a project and its tasks from a template."""
    proj_id = uid()
    new_proj = {
        "id": proj_id,
        "nombre": template_name,
        "area": "proyectos",
        "emoji": template["emoji"],
        "desc": template["desc"],
        "plantilla": False,
        "compartido": "",
        "ts": now_ts(),
    }
    proyectos = pd.concat([pd.DataFrame([new_proj]), proyectos], ignore_index=True)
    save_df("proyectos", proyectos)

    # Create tasks
    new_tasks = []
    for task_title in template["tasks"]:
        new_tasks.append({
            "id": uid(),
            "titulo": task_title,
            "area": "proyectos",
            "prioridad": "media",
            "fecha": "",
            "proyecto": proj_id,
            "notas": f"Creada desde plantilla: {template_name}",
            "subtareas": "",
            "recurrente": "",
            "depende_de": "",
            "done": False,
            "pinned": False,
            "archived": False,
            "ts": now_ts(),
        })
    if new_tasks:
        tareas = pd.concat([pd.DataFrame(new_tasks), tareas], ignore_index=True)
        save_df("tareas", tareas)
