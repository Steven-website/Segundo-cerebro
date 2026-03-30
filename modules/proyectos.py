import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, PRIORITY_LABELS
from core.utils import confirm_delete, export_csv, PRIORITY_EMOJIS


ESTADOS = {"activo": "🟢 Activo", "pausado": "🟡 Pausado", "completado": "✅ Completado", "cancelado": "🔴 Cancelado"}

TEMPLATES = {
    "Lanzamiento web": {
        "emoji": "🌐", "desc": "Plantilla para lanzar un sitio web",
        "tasks": ["Definir requisitos y alcance", "Disenar wireframes / mockups", "Configurar dominio y hosting",
                  "Desarrollar frontend", "Desarrollar backend / API", "Integrar base de datos",
                  "Pruebas funcionales", "Pruebas de rendimiento", "Configurar SSL y seguridad", "Despliegue a produccion"],
    },
    "App movil": {
        "emoji": "📱", "desc": "Plantilla para desarrollar una app movil",
        "tasks": ["Investigacion y planificacion", "Disenar UI/UX", "Configurar proyecto (React Native / Flutter)",
                  "Pantallas principales", "Navegacion y routing", "Integracion con API",
                  "Autenticacion de usuarios", "Pruebas en dispositivos", "Publicar en App Store / Play Store"],
    },
    "Marketing digital": {
        "emoji": "📣", "desc": "Plantilla para campana de marketing",
        "tasks": ["Definir objetivos y KPIs", "Investigar audiencia objetivo", "Crear contenido (copy, imagenes, video)",
                  "Configurar redes sociales", "Configurar anuncios pagados", "Email marketing - crear secuencia",
                  "Landing page", "Monitorear metricas", "Ajustar estrategia segun resultados"],
    },
    "Evento": {
        "emoji": "🎉", "desc": "Plantilla para organizar un evento",
        "tasks": ["Definir fecha y lugar", "Crear presupuesto", "Enviar invitaciones", "Contratar proveedores",
                  "Preparar decoracion", "Confirmar asistentes", "Logistica del dia", "Seguimiento post-evento"],
    },
}


def render():
    st.header("Proyectos")

    proyectos = get_df("proyectos")
    tareas = get_df("tareas")
    notas = get_df("notas")

    # --- Check if viewing a project detail ---
    viewing_proj = st.session_state.get("proj_viewing")
    if viewing_proj and not proyectos.empty:
        matches = proyectos[proyectos["id"] == viewing_proj]
        if not matches.empty:
            _render_project_detail(matches.iloc[0], proyectos, tareas, notas)
            return

    # --- Toolbar ---
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
        template_cols = st.columns(2)
        for i, (name, tmpl) in enumerate(TEMPLATES.items()):
            with template_cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"### {tmpl['emoji']} {name}")
                    st.caption(f"{tmpl['desc']} | {len(tmpl['tasks'])} tareas")
                    if st.button("Usar", key=f"tmpl_{name}", use_container_width=True, type="primary"):
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
        _render_project_form(proyectos)

    # --- Project list ---
    if proyectos.empty:
        st.info("No hay proyectos. Crea uno con '+ Proyecto' o usa una plantilla.")
        return

    # Filter by status
    status_filter = st.selectbox("Filtrar por estado", ["Todos", "Activos", "Pausados", "Completados"],
                                  label_visibility="collapsed", key="proj_status_f")

    filtered = proyectos.copy()
    if status_filter == "Activos":
        filtered = filtered[filtered.get("estado", "activo").isin(["activo", ""])]
    elif status_filter == "Pausados":
        filtered = filtered[filtered["estado"] == "pausado"]
    elif status_filter == "Completados":
        filtered = filtered[filtered["estado"] == "completado"]

    cols = st.columns(2)
    for i, (_, p) in enumerate(filtered.iterrows()):
        with cols[i % 2]:
            area_label = AREA_LABELS.get(p["area"], p["area"])
            proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
            proj_notas = notas[notas.get("proyecto", "") == p["id"]] if not notas.empty and "proyecto" in notas.columns else pd.DataFrame()
            total_tasks = len(proj_tasks)
            done_tasks = int(proj_tasks["done"].sum()) if total_tasks > 0 else 0
            pct = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

            with st.container(border=True):
                proj_emoji = p.get('emoji', '📁')
                estado = p.get("estado", "activo") or "activo"
                estado_label = ESTADOS.get(estado, estado)
                st.markdown(f"### {proj_emoji} {p['nombre']}")
                st.caption(f"{area_label} | {estado_label}")
                if p.get("desc"):
                    st.caption(p["desc"][:100])
                if p.get("fecha_inicio") or p.get("fecha_fin"):
                    dates = []
                    if p.get("fecha_inicio"):
                        dates.append(f"Inicio: {p['fecha_inicio']}")
                    if p.get("fecha_fin"):
                        dates.append(f"Fin: {p['fecha_fin']}")
                    st.caption(" | ".join(dates))

                st.progress(pct / 100, text=f"{pct}% completado")
                st.caption(f"{total_tasks} tareas | {int(done_tasks)} hechas | {len(proj_notas)} notas")

                c_view, c_edit, c_del = st.columns(3)
                with c_view:
                    if st.button("📂 Abrir", key=f"pview_{p['id']}", use_container_width=True, type="primary"):
                        st.session_state["proj_viewing"] = p["id"]
                        st.rerun()
                with c_edit:
                    if st.button("✏️", key=f"pedit_{p['id']}", use_container_width=True):
                        st.session_state["proj_editing"] = True
                        st.session_state["proj_edit_id"] = p["id"]
                        st.rerun()
                with c_del:
                    if confirm_delete(p["id"], p["nombre"], "proj"):
                        proyectos = proyectos[proyectos["id"] != p["id"]]
                        save_df("proyectos", proyectos)
                        st.rerun()


def _render_project_detail(project, proyectos, tareas, notas):
    """Full detail view of a single project with its tasks and notes."""
    proj_id = project["id"]
    proj_emoji = project.get("emoji", "📁")
    estado = project.get("estado", "activo") or "activo"

    # Header
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Volver", use_container_width=True):
            st.session_state["proj_viewing"] = None
            st.rerun()
    with col_title:
        st.markdown(f"## {proj_emoji} {project['nombre']}")

    # Info bar
    area_label = AREA_LABELS.get(project["area"], project["area"])
    estado_label = ESTADOS.get(estado, estado)
    info_parts = [area_label, estado_label]
    if project.get("fecha_inicio"):
        info_parts.append(f"Inicio: {project['fecha_inicio']}")
    if project.get("fecha_fin"):
        info_parts.append(f"Fin: {project['fecha_fin']}")
    st.caption(" | ".join(info_parts))

    if project.get("desc"):
        st.markdown(project["desc"])
    if project.get("compartido"):
        st.caption(f"👥 Compartido con: {project['compartido']}")

    # Progress
    proj_tasks = tareas[tareas["proyecto"] == proj_id] if not tareas.empty else pd.DataFrame()
    total_tasks = len(proj_tasks)
    done_tasks = int(proj_tasks["done"].sum()) if total_tasks > 0 else 0
    pct = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0
    st.progress(pct / 100, text=f"{pct}% completado ({done_tasks}/{total_tasks} tareas)")

    # Quick status change
    col_st1, col_st2, col_st3, col_st4 = st.columns(4)
    for col, est, label in [(col_st1, "activo", "🟢 Activo"), (col_st2, "pausado", "🟡 Pausar"),
                             (col_st3, "completado", "✅ Completar"), (col_st4, "cancelado", "🔴 Cancelar")]:
        with col:
            disabled = estado == est
            if st.button(label, key=f"pst_{est}_{proj_id}", use_container_width=True, disabled=disabled):
                proyectos.loc[proyectos["id"] == proj_id, "estado"] = est
                save_df("proyectos", proyectos)
                st.rerun()

    st.divider()

    # === TABS: Tareas | Notas ===
    tab_tareas, tab_notas = st.tabs([f"📋 Tareas ({total_tasks})", f"📝 Notas"])

    # --- TAREAS TAB ---
    with tab_tareas:
        if st.button("+ Tarea al proyecto", type="primary", key="add_proj_task"):
            st.session_state["proj_task_adding"] = True

        if st.session_state.get("proj_task_adding"):
            with st.form("proj_task_form", clear_on_submit=True):
                titulo = st.text_input("Titulo de la tarea")
                c1, c2 = st.columns(2)
                pri_opts = ["alta", "media", "baja"]
                prioridad = c1.selectbox("Prioridad", pri_opts, index=1,
                                         format_func=lambda x: PRIORITY_LABELS.get(x, x))
                fecha = c2.date_input("Fecha limite (opcional)", value=None)
                notas_txt = st.text_area("Notas", height=60)

                col_s, col_c = st.columns(2)
                submitted = col_s.form_submit_button("Guardar", type="primary")
                cancelled = col_c.form_submit_button("Cancelar")

                if submitted and titulo.strip():
                    new_task = {
                        "id": uid(), "titulo": titulo.strip(), "area": project["area"],
                        "prioridad": prioridad, "fecha": str(fecha) if fecha else "",
                        "proyecto": proj_id, "notas": notas_txt, "subtareas": "",
                        "recurrente": "", "depende_de": "", "done": False,
                        "pinned": False, "archived": False, "ts": now_ts(),
                    }
                    tareas = pd.concat([pd.DataFrame([new_task]), tareas], ignore_index=True)
                    save_df("tareas", tareas)
                    st.session_state["proj_task_adding"] = False
                    st.rerun()
                if cancelled:
                    st.session_state["proj_task_adding"] = False
                    st.rerun()

        # Display tasks
        if proj_tasks.empty:
            st.info("No hay tareas en este proyecto.")
        else:
            # Pending first, then done
            pending = proj_tasks[~proj_tasks["done"]].sort_values("ts", ascending=False)
            done = proj_tasks[proj_tasks["done"]].sort_values("ts", ascending=False)

            for _, t in pending.iterrows():
                pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "")
                fecha_str = f" | {t['fecha']}" if t.get("fecha") else ""
                col_check, col_body, col_del = st.columns([0.5, 5, 0.5])
                with col_check:
                    if st.checkbox("", value=False, key=f"pt_check_{t['id']}", label_visibility="collapsed"):
                        tareas.loc[tareas["id"] == t["id"], "done"] = True
                        save_df("tareas", tareas)
                        st.rerun()
                with col_body:
                    st.markdown(f"{pri_emoji} **{t['titulo']}**{fecha_str}")
                    if t.get("notas"):
                        st.caption(t["notas"][:80])
                with col_del:
                    if confirm_delete(t["id"], t["titulo"], "ptask"):
                        tareas = tareas[tareas["id"] != t["id"]]
                        save_df("tareas", tareas)
                        st.rerun()

            if not done.empty:
                with st.expander(f"✅ Completadas ({len(done)})"):
                    for _, t in done.iterrows():
                        col_check, col_body = st.columns([0.5, 5.5])
                        with col_check:
                            if st.checkbox("", value=True, key=f"pt_check_{t['id']}", label_visibility="collapsed"):
                                pass
                            else:
                                tareas.loc[tareas["id"] == t["id"], "done"] = False
                                save_df("tareas", tareas)
                                st.rerun()
                        with col_body:
                            st.markdown(f"~~{t['titulo']}~~")

    # --- NOTAS TAB ---
    with tab_notas:
        proj_notas = notas[notas.get("proyecto", "") == proj_id] if not notas.empty and "proyecto" in notas.columns else pd.DataFrame()

        if st.button("+ Nota al proyecto", type="primary", key="add_proj_nota"):
            st.session_state["proj_nota_adding"] = True

        if st.session_state.get("proj_nota_adding"):
            with st.form("proj_nota_form", clear_on_submit=True):
                titulo = st.text_input("Titulo de la nota")
                tags = st.text_input("Tags (separados por coma)", placeholder="idea, investigacion, referencia...")
                body = st.text_area("Contenido (soporta Markdown)", height=200)

                col_s, col_c = st.columns(2)
                submitted = col_s.form_submit_button("Guardar", type="primary")
                cancelled = col_c.form_submit_button("Cancelar")

                if submitted and titulo.strip():
                    new_nota = {
                        "id": uid(), "titulo": titulo.strip(), "area": project["area"],
                        "tags": tags, "body": body, "proyecto": proj_id,
                        "pinned": False, "archived": False, "ts": now_ts(),
                    }
                    notas = pd.concat([pd.DataFrame([new_nota]), notas], ignore_index=True)
                    save_df("notas", notas)
                    st.session_state["proj_nota_adding"] = False
                    st.rerun()
                if cancelled:
                    st.session_state["proj_nota_adding"] = False
                    st.rerun()

        # Display notes
        if proj_notas.empty:
            st.info("No hay notas en este proyecto.")
        else:
            for _, n in proj_notas.sort_values("ts", ascending=False).iterrows():
                with st.container(border=True):
                    col_t, col_del = st.columns([5, 1])
                    with col_t:
                        st.markdown(f"**{n['titulo']}**")
                        if n.get("tags"):
                            tags_list = [t.strip() for t in n["tags"].split(",") if t.strip()]
                            st.caption(" ".join([f"`{t}`" for t in tags_list]))
                    with col_del:
                        if confirm_delete(n["id"], n["titulo"], "pnota"):
                            notas = notas[notas["id"] != n["id"]]
                            save_df("notas", notas)
                            st.rerun()

                    # Expandable content
                    preview = (n["body"][:150] + "...") if len(n.get("body", "")) > 150 else n.get("body", "")
                    if preview:
                        st.caption(preview)
                    if len(n.get("body", "")) > 150:
                        with st.expander("Ver completa"):
                            st.markdown(n["body"])


def _render_project_form(proyectos):
    """Render the add/edit project form."""
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

        c3, c4 = st.columns(2)
        area_ids = [a["id"] for a in AREAS]
        area = c3.selectbox("Area", area_ids, format_func=lambda x: AREA_LABELS.get(x, x),
                            index=area_ids.index(existing["area"]) if existing is not None and existing["area"] in area_ids else 0)
        estado_opts = list(ESTADOS.keys())
        estado = c4.selectbox("Estado", estado_opts, format_func=lambda x: ESTADOS.get(x, x),
                              index=estado_opts.index(existing.get("estado", "activo")) if existing is not None and existing.get("estado", "activo") in estado_opts else 0)

        desc = st.text_area("Descripcion", value=existing["desc"] if existing is not None else "", height=80)

        c5, c6 = st.columns(2)
        fecha_inicio = c5.date_input("Fecha inicio (opcional)", value=None)
        fecha_fin = c6.date_input("Fecha fin (opcional)", value=None)

        compartido = st.text_input("Compartir con (correos separados por coma)",
                                   value=existing.get("compartido", "") if existing is not None else "",
                                   placeholder="correo1@mail.com, correo2@mail.com")

        col_s, col_c = st.columns(2)
        submitted = col_s.form_submit_button("Guardar", type="primary")
        cancelled = col_c.form_submit_button("Cancelar")

        if submitted and nombre.strip():
            new_row = {
                "id": edit_id or uid(), "nombre": nombre.strip(), "area": area,
                "emoji": emoji or "📁", "desc": desc, "estado": estado,
                "fecha_inicio": str(fecha_inicio) if fecha_inicio else "",
                "fecha_fin": str(fecha_fin) if fecha_fin else "",
                "plantilla": False, "compartido": compartido, "ts": now_ts(),
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


def _create_from_template(template_name, template, proyectos, tareas):
    """Create a project and its tasks from a template."""
    proj_id = uid()
    new_proj = {
        "id": proj_id, "nombre": template_name, "area": "proyectos",
        "emoji": template["emoji"], "desc": template["desc"], "estado": "activo",
        "fecha_inicio": "", "fecha_fin": "",
        "plantilla": False, "compartido": "", "ts": now_ts(),
    }
    proyectos = pd.concat([pd.DataFrame([new_proj]), proyectos], ignore_index=True)
    save_df("proyectos", proyectos)

    new_tasks = []
    for task_title in template["tasks"]:
        new_tasks.append({
            "id": uid(), "titulo": task_title, "area": "proyectos",
            "prioridad": "media", "fecha": "", "proyecto": proj_id,
            "notas": f"Creada desde plantilla: {template_name}",
            "subtareas": "", "recurrente": "", "depende_de": "",
            "done": False, "pinned": False, "archived": False, "ts": now_ts(),
        })
    if new_tasks:
        tareas = pd.concat([pd.DataFrame(new_tasks), tareas], ignore_index=True)
        save_df("tareas", tareas)
