import streamlit as st
import pandas as pd
import json
from datetime import datetime
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, PRIORITY_LABELS
from core.utils import confirm_delete, export_csv, PRIORITY_EMOJIS


def _parse_subtareas(subtareas_str):
    """Parse subtasks - supports both JSON and plain text format."""
    if not subtareas_str:
        return []
    try:
        subs = json.loads(subtareas_str)
        if isinstance(subs, list):
            return subs
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: plain text format → convert to JSON structure
    lines = [l.strip() for l in subtareas_str.split("\n") if l.strip()]
    result = []
    for line in lines:
        done = line.startswith("[x]")
        text = line.replace("[x] ", "").replace("[x]", "").replace("[ ] ", "").replace("[ ]", "").strip()
        result.append({"text": text, "fecha": "", "done": done})
    return result


def _save_subtareas(subs):
    """Serialize subtasks list to JSON string."""
    return json.dumps(subs, ensure_ascii=False)


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

    # --- Check if viewing a project detail ---
    viewing_proj = st.session_state.get("proj_viewing")
    if viewing_proj and not proyectos.empty:
        matches = proyectos[proyectos["id"] == viewing_proj]
        if not matches.empty:
            _render_project_detail(matches.iloc[0], proyectos, tareas)
            return

    # --- Check if viewing task detail ---
    viewing_task = st.session_state.get("task_detail_id")
    if viewing_task and not tareas.empty:
        matches = tareas[tareas["id"] == viewing_task]
        if not matches.empty:
            _render_task_detail(matches.iloc[0], tareas, proyectos)
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
    status_filter = st.selectbox("Filtrar", ["Todos", "Activos", "Pausados", "Completados"],
                                  label_visibility="collapsed", key="proj_status_f")

    filtered = proyectos.copy()
    if status_filter == "Activos":
        filtered = filtered[(filtered["estado"].isin(["activo", ""])) | (filtered["estado"].isna())]
    elif status_filter == "Pausados":
        filtered = filtered[filtered["estado"] == "pausado"]
    elif status_filter == "Completados":
        filtered = filtered[filtered["estado"] == "completado"]

    for _, p in filtered.iterrows():
        area_label = AREA_LABELS.get(p["area"], p["area"])
        proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
        total_tasks = len(proj_tasks)
        done_tasks = int(proj_tasks["done"].sum()) if total_tasks > 0 else 0
        pct = int((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

        with st.container(border=True):
            proj_emoji = p.get('emoji', '📁')
            estado = p.get("estado", "activo") or "activo"
            estado_label = ESTADOS.get(estado, estado)

            col_info, col_actions = st.columns([5, 2])
            with col_info:
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
                st.progress(pct / 100, text=f"{pct}% ({done_tasks}/{total_tasks} tareas)")

            with col_actions:
                if st.button("📂 Abrir", key=f"pview_{p['id']}", use_container_width=True, type="primary"):
                    st.session_state["proj_viewing"] = p["id"]
                    st.rerun()
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✏️", key=f"pedit_{p['id']}", use_container_width=True):
                        st.session_state["proj_editing"] = True
                        st.session_state["proj_edit_id"] = p["id"]
                        st.rerun()
                with c2:
                    if confirm_delete(p["id"], p["nombre"], "proj"):
                        proyectos = proyectos[proyectos["id"] != p["id"]]
                        save_df("proyectos", proyectos)
                        st.rerun()


# ═══════════════════════════════════════════════
#  PROJECT DETAIL VIEW
# ═══════════════════════════════════════════════
def _render_project_detail(project, proyectos, tareas):
    proj_id = project["id"]
    proj_emoji = project.get("emoji", "📁")
    estado = project.get("estado", "activo") or "activo"

    # Header
    if st.button("← Volver a proyectos"):
        st.session_state["proj_viewing"] = None
        st.rerun()

    st.markdown(f"## {proj_emoji} {project['nombre']}")

    # Info
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
    col_st = st.columns(4)
    for i, (est, label) in enumerate(ESTADOS.items()):
        with col_st[i]:
            if st.button(label, key=f"pst_{est}_{proj_id}", use_container_width=True, disabled=(estado == est)):
                proyectos.loc[proyectos["id"] == proj_id, "estado"] = est
                save_df("proyectos", proyectos)
                st.rerun()

    st.divider()

    # --- ADD TASK ---
    if st.button("+ Tarea", type="primary", key="add_proj_task"):
        st.session_state["proj_task_adding"] = True

    if st.session_state.get("proj_task_adding"):
        with st.form("proj_task_form", clear_on_submit=True):
            st.subheader("Nueva tarea")
            titulo = st.text_input("Titulo")
            c1, c2, c3 = st.columns(3)
            pri_opts = ["alta", "media", "baja"]
            prioridad = c1.selectbox("Prioridad", pri_opts, index=1,
                                     format_func=lambda x: PRIORITY_LABELS.get(x, x))
            fecha_inicio = c2.date_input("Fecha inicio", value=None)
            fecha_fin = c3.date_input("Fecha limite", value=None)
            notas_txt = st.text_area("Descripcion", height=60)
            subtareas_txt = st.text_area("Subtareas (una por linea)", height=60,
                                         help="Escribe una subtarea por linea")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                # Convert plain text subtasks to JSON format
                sub_lines = [l.strip() for l in subtareas_txt.split("\n") if l.strip()] if subtareas_txt else []
                subs_json = _save_subtareas([{"text": l, "fecha": "", "done": False} for l in sub_lines]) if sub_lines else ""
                new_task = {
                    "id": uid(), "titulo": titulo.strip(), "area": project["area"],
                    "prioridad": prioridad,
                    "fecha_inicio": str(fecha_inicio) if fecha_inicio else "",
                    "fecha": str(fecha_fin) if fecha_fin else "",
                    "proyecto": proj_id, "notas": notas_txt, "subtareas": subs_json,
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

    # --- TASK LIST ---
    if proj_tasks.empty:
        st.info("No hay tareas en este proyecto. Crea una con '+ Tarea'.")
        return

    pending = proj_tasks[~proj_tasks["done"]].copy()
    done_df = proj_tasks[proj_tasks["done"]].copy()

    # Sort by priority
    pri_order = {"alta": 0, "media": 1, "baja": 2}
    if not pending.empty:
        pending["_pri"] = pending["prioridad"].map(pri_order).fillna(2)
        pending = pending.sort_values("_pri")

    # Pending tasks
    for _, t in pending.iterrows():
        _render_task_row(t, tareas, show_detail=True)

    # Completed tasks
    if not done_df.empty:
        with st.expander(f"✅ Completadas ({len(done_df)})"):
            for _, t in done_df.iterrows():
                _render_task_row(t, tareas, show_detail=False)


def _render_task_row(t, tareas, show_detail=True):
    """Render a single task row within a project."""
    pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "")
    comments = get_df("task_comments")
    task_comments = comments[comments["tarea_id"] == t["id"]] if not comments.empty else pd.DataFrame()
    comment_count = len(task_comments)
    subs = _parse_subtareas(t.get("subtareas", ""))
    sub_count = len(subs)
    sub_done = sum(1 for s in subs if s.get("done"))

    with st.container(border=True):
        col_check, col_body, col_actions = st.columns([0.5, 5, 1.5])
        with col_check:
            new_done = st.checkbox("", value=t["done"], key=f"tc_{t['id']}", label_visibility="collapsed")
            if new_done != t["done"]:
                tareas.loc[tareas["id"] == t["id"], "done"] = new_done
                save_df("tareas", tareas)
                st.rerun()
        with col_body:
            style = "~~" if t["done"] else ""
            st.markdown(f"{pri_emoji} {style}**{t['titulo']}**{style}")
            # Info line
            info = []
            if t.get("fecha_inicio") and t.get("fecha"):
                info.append(f"📅 {t['fecha_inicio']} → {t['fecha']}")
            elif t.get("fecha"):
                info.append(f"📅 Limite: {t['fecha']}")
            elif t.get("fecha_inicio"):
                info.append(f"📅 Inicio: {t['fecha_inicio']}")
            if sub_count > 0:
                info.append(f"☑️ {sub_done}/{sub_count}")
            if comment_count > 0:
                info.append(f"💬 {comment_count}")
            if info:
                st.caption(" | ".join(info))
        with col_actions:
            if show_detail:
                if st.button("Abrir", key=f"td_{t['id']}", use_container_width=True):
                    st.session_state["task_detail_id"] = t["id"]
                    st.rerun()
            if confirm_delete(t["id"], t["titulo"], "ptask"):
                tareas = tareas[tareas["id"] != t["id"]]
                save_df("tareas", tareas)
                st.rerun()


# ═══════════════════════════════════════════════
#  TASK DETAIL VIEW (subtasks, comments, edit)
# ═══════════════════════════════════════════════
def _render_task_detail(task, tareas, proyectos):
    """Full detail view of a single task."""
    task_id = task["id"]

    # Back button
    if st.button("← Volver al proyecto"):
        st.session_state["task_detail_id"] = None
        st.rerun()

    pri_emoji = PRIORITY_EMOJIS.get(task["prioridad"], "")
    st.markdown(f"## {pri_emoji} {task['titulo']}")

    # Info
    info_parts = [f"Prioridad: {PRIORITY_LABELS.get(task['prioridad'], task['prioridad'])}"]
    area_label = AREA_LABELS.get(task["area"], task["area"])
    info_parts.append(area_label)
    if task.get("fecha_inicio"):
        info_parts.append(f"Inicio: {task['fecha_inicio']}")
    if task.get("fecha"):
        info_parts.append(f"Limite: {task['fecha']}")
    st.caption(" | ".join(info_parts))

    # Status toggle
    done = task["done"]
    status_label = "✅ Completada" if done else "⬜ Pendiente"
    if st.button(f"Marcar como {'pendiente' if done else 'completada'}", type="primary"):
        tareas.loc[tareas["id"] == task_id, "done"] = not done
        save_df("tareas", tareas)
        st.rerun()

    st.divider()

    # Description
    if task.get("notas"):
        st.markdown("**Descripcion:**")
        st.markdown(task["notas"])

    # Edit button
    if st.button("✏️ Editar tarea", key="edit_task_detail"):
        st.session_state["task_detail_editing"] = True

    if st.session_state.get("task_detail_editing"):
        _render_task_edit_form(task, tareas, proyectos)

    st.divider()

    # ═══ SUBTAREAS ═══
    st.subheader("Subtareas")
    subs = _parse_subtareas(task.get("subtareas", ""))

    if subs:
        updated = False
        for i, sub in enumerate(subs):
            col_c, col_t, col_date = st.columns([0.5, 4.5, 1.5])
            with col_c:
                checked = st.checkbox("", value=sub.get("done", False), key=f"sub_{task_id}_{i}", label_visibility="collapsed")
                if checked != sub.get("done", False):
                    subs[i]["done"] = checked
                    updated = True
            with col_t:
                style = "~~" if checked else ""
                st.markdown(f"{style}{sub['text']}{style}")
            with col_date:
                sub_fecha = sub.get("fecha", "")
                if sub_fecha:
                    today = datetime.now().strftime("%Y-%m-%d")
                    color = "red" if sub_fecha < today and not checked else "gray"
                    st.caption(f":{color}[📅 {sub_fecha}]")

        if updated:
            tareas.loc[tareas["id"] == task_id, "subtareas"] = _save_subtareas(subs)
            save_df("tareas", tareas)
            st.rerun()
    else:
        st.caption("No hay subtareas.")

    # Add subtask
    with st.form("add_subtask_form", clear_on_submit=True):
        col_sub, col_date = st.columns([3, 1])
        new_sub = col_sub.text_input("Nueva subtarea", placeholder="Escribe una subtarea...")
        sub_fecha = col_date.date_input("Fecha (opcional)", value=None, key="new_sub_fecha")
        if st.form_submit_button("Agregar subtarea"):
            if new_sub.strip():
                subs.append({
                    "text": new_sub.strip(),
                    "fecha": str(sub_fecha) if sub_fecha else "",
                    "done": False,
                })
                tareas.loc[tareas["id"] == task_id, "subtareas"] = _save_subtareas(subs)
                save_df("tareas", tareas)
                st.rerun()

    st.divider()

    # ═══ COMENTARIOS ═══
    st.subheader("Comentarios")
    comments = get_df("task_comments")
    task_comments = comments[comments["tarea_id"] == task_id].sort_values("ts", ascending=False) if not comments.empty else pd.DataFrame()

    # Add comment
    with st.form("add_comment_form", clear_on_submit=True):
        texto = st.text_area("Nuevo comentario", height=60, placeholder="Escribe un comentario...")
        if st.form_submit_button("Comentar", type="primary"):
            if texto.strip():
                new_comment = {
                    "id": uid(), "tarea_id": task_id, "texto": texto.strip(),
                    "autor": st.session_state.get("current_user", ""), "ts": now_ts(),
                }
                comments = pd.concat([pd.DataFrame([new_comment]), comments], ignore_index=True)
                save_df("task_comments", comments)
                st.rerun()

    if task_comments.empty:
        st.caption("No hay comentarios.")
    else:
        for _, c in task_comments.iterrows():
            ts_str = datetime.fromtimestamp(c["ts"]).strftime("%d/%m/%Y %H:%M") if c["ts"] else ""
            with st.container(border=True):
                st.caption(f"**{c['autor']}** - {ts_str}")
                st.markdown(c["texto"])


def _render_task_edit_form(task, tareas, proyectos):
    """Edit form for a task within detail view."""
    with st.form("task_edit_form"):
        titulo = st.text_input("Titulo", value=task["titulo"])
        c1, c2 = st.columns(2)
        pri_opts = ["alta", "media", "baja"]
        prioridad = c1.selectbox("Prioridad", pri_opts, format_func=lambda x: PRIORITY_LABELS.get(x, x),
                                 index=pri_opts.index(task["prioridad"]) if task["prioridad"] in pri_opts else 1)
        area_ids = [a["id"] for a in AREAS]
        area = c2.selectbox("Area", area_ids, format_func=lambda x: AREA_LABELS.get(x, x),
                            index=area_ids.index(task["area"]) if task["area"] in area_ids else 0)

        c3, c4 = st.columns(2)
        fecha_inicio = c3.date_input("Fecha inicio", value=None)
        fecha_fin = c4.date_input("Fecha limite", value=None)

        notas_txt = st.text_area("Descripcion", value=task.get("notas", ""), height=80)

        # Show subtasks as editable text (one per line)
        existing_subs = _parse_subtareas(task.get("subtareas", ""))
        existing_subs_text = "\n".join(s["text"] for s in existing_subs) if existing_subs else ""
        subtareas_txt = st.text_area("Subtareas (una por linea)", value=existing_subs_text, height=80,
                                     help="Las fechas de subtareas se asignan desde la vista de detalle")

        col_s, col_c = st.columns(2)
        submitted = col_s.form_submit_button("Guardar", type="primary")
        cancelled = col_c.form_submit_button("Cancelar")

        if submitted and titulo.strip():
            # Merge subtask text edits preserving existing dates/done state
            new_lines = [l.strip() for l in subtareas_txt.split("\n") if l.strip()]
            old_subs = {s["text"]: s for s in existing_subs}
            merged_subs = []
            for line in new_lines:
                if line in old_subs:
                    merged_subs.append(old_subs[line])
                else:
                    merged_subs.append({"text": line, "fecha": "", "done": False})

            tareas.loc[tareas["id"] == task["id"], "titulo"] = titulo.strip()
            tareas.loc[tareas["id"] == task["id"], "prioridad"] = prioridad
            tareas.loc[tareas["id"] == task["id"], "area"] = area
            tareas.loc[tareas["id"] == task["id"], "fecha_inicio"] = str(fecha_inicio) if fecha_inicio else ""
            tareas.loc[tareas["id"] == task["id"], "fecha"] = str(fecha_fin) if fecha_fin else ""
            tareas.loc[tareas["id"] == task["id"], "notas"] = notas_txt
            tareas.loc[tareas["id"] == task["id"], "subtareas"] = _save_subtareas(merged_subs) if merged_subs else ""
            save_df("tareas", tareas)
            st.session_state["task_detail_editing"] = False
            st.rerun()
        if cancelled:
            st.session_state["task_detail_editing"] = False
            st.rerun()


# ═══════════════════════════════════════════════
#  PROJECT FORM
# ═══════════════════════════════════════════════
def _render_project_form(proyectos):
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
                              index=estado_opts.index(existing.get("estado", "activo") or "activo") if existing is not None else 0)

        desc = st.text_area("Descripcion", value=existing["desc"] if existing is not None else "", height=80)

        c5, c6 = st.columns(2)
        fecha_inicio = c5.date_input("Fecha inicio (opcional)", value=None)
        fecha_fin = c6.date_input("Fecha fin (opcional)", value=None)

        compartido = st.text_input("Compartir con (correos separados por coma)",
                                   value=existing.get("compartido", "") if existing is not None else "")

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
            "prioridad": "media", "fecha_inicio": "", "fecha": "",
            "proyecto": proj_id, "notas": "", "subtareas": "",
            "recurrente": "", "depende_de": "",
            "done": False, "pinned": False, "archived": False, "ts": now_ts(),
        })
    if new_tasks:
        tareas = pd.concat([pd.DataFrame(new_tasks), tareas], ignore_index=True)
        save_df("tareas", tareas)
