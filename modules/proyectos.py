import streamlit as st
import pandas as pd
import json
from datetime import datetime
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, PRIORITY_LABELS
from core.utils import confirm_delete, export_csv, PRIORITY_EMOJIS, soft_delete, cascade_delete_project, mark_task_done


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


ETIQUETAS = {"": "Sin etiqueta", "urgente": "🔴 Urgente", "bug": "🐛 Bug", "idea": "💡 Idea", "reunion": "📞 Reunion", "personal": "🏠 Personal"}


def render():
    st.header("Proyectos")

    proyectos = get_df("proyectos")
    tareas = get_df("tareas")

    # --- Check if viewing task detail (must be before project check) ---
    viewing_task = st.session_state.get("task_detail_id")
    if viewing_task and not tareas.empty:
        matches = tareas[tareas["id"] == viewing_task]
        if not matches.empty:
            _render_task_detail(matches.iloc[0], tareas, proyectos)
            return

    # --- Check if viewing a project detail ---
    viewing_proj = st.session_state.get("proj_viewing")
    if viewing_proj and not proyectos.empty:
        matches = proyectos[proyectos["id"] == viewing_proj]
        if not matches.empty:
            _render_project_detail(matches.iloc[0], proyectos, tareas)
            return

    # --- Toolbar ---
    col_tmpl, col_view, col_export, col_add = st.columns([2, 1, 1, 1])
    with col_tmpl:
        if st.button("📋 Plantilla", use_container_width=True):
            st.session_state["show_templates"] = True
    with col_view:
        view_mode = st.selectbox("Vista", ["Lista", "Kanban"], key="proj_view_mode", label_visibility="collapsed")
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

    if view_mode == "Kanban":
        _render_projects_kanban(proyectos, tareas)
    else:
        _render_projects_list(proyectos, tareas)


def _render_projects_kanban(proyectos, tareas):
    """Kanban board for projects grouped by status."""
    kanban_states = [("activo", "🟢 Activos"), ("pausado", "🟡 Pausados"), ("completado", "✅ Completados"), ("cancelado", "🔴 Cancelados")]

    # Count per column
    def _count_by_estado(est):
        if est == "activo":
            return len(proyectos[(proyectos["estado"].isin(["activo", ""])) | (proyectos["estado"].isna())])
        return len(proyectos[proyectos["estado"] == est])

    total_proj = len(proyectos) if not proyectos.empty else 1

    cols = st.columns(len(kanban_states))
    for col, (estado, label) in zip(cols, kanban_states):
        with col:
            count = _count_by_estado(estado)
            pct_col = int(count / total_proj * 100) if total_proj > 0 else 0
            st.markdown(f"**{label}** ({count})")
            st.progress(pct_col / 100, text=f"{pct_col}%")

            if estado == "activo":
                group = proyectos[(proyectos["estado"].isin(["activo", ""])) | (proyectos["estado"].isna())]
            else:
                group = proyectos[proyectos["estado"] == estado]

            # Move targets for arrows
            estado_list = [s[0] for s in kanban_states]
            idx = estado_list.index(estado)

            if group.empty:
                st.caption("—")
            for _, p in group.iterrows():
                proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
                total = len(proj_tasks)
                done = int(proj_tasks["done"].sum()) if total > 0 else 0
                pct = int(done / total * 100) if total > 0 else 0
                with st.container(border=True):
                    st.markdown(f"{p.get('emoji', '📁')} **{p['nombre']}**")
                    if total > 0:
                        st.progress(pct / 100, text=f"{done}/{total}")
                    # Move arrows + Open
                    arrow_cols = st.columns([1, 1, 2])
                    with arrow_cols[0]:
                        if idx > 0:
                            if st.button("←", key=f"kb_l_{p['id']}", use_container_width=True, help=f"Mover a {kanban_states[idx-1][1]}"):
                                proyectos.loc[proyectos["id"] == p["id"], "estado"] = estado_list[idx - 1]
                                save_df("proyectos", proyectos)
                                st.rerun()
                    with arrow_cols[1]:
                        if idx < len(estado_list) - 1:
                            if st.button("→", key=f"kb_r_{p['id']}", use_container_width=True, help=f"Mover a {kanban_states[idx+1][1]}"):
                                proyectos.loc[proyectos["id"] == p["id"], "estado"] = estado_list[idx + 1]
                                save_df("proyectos", proyectos)
                                st.rerun()
                    with arrow_cols[2]:
                        if st.button("Abrir", key=f"kb_{p['id']}", use_container_width=True):
                            st.session_state["proj_viewing"] = p["id"]
                            st.rerun()


def _days_without_progress(proj_tasks):
    """Return days since last task was completed, or days since project creation."""
    if proj_tasks.empty:
        return None
    completed = proj_tasks[proj_tasks["done"] == True]
    if not completed.empty and "fecha_completada" in completed.columns:
        fechas = completed["fecha_completada"].dropna()
        fechas = fechas[fechas != ""]
        if not fechas.empty:
            last = max(fechas)
            try:
                last_date = datetime.strptime(str(last)[:10], "%Y-%m-%d")
                return (datetime.now() - last_date).days
            except (ValueError, TypeError):
                pass
    # Fallback: use ts (timestamp) of last modified task
    if "ts" in proj_tasks.columns:
        last_ts = proj_tasks["ts"].max()
        if last_ts and last_ts > 0:
            last_date = datetime.fromtimestamp(last_ts)
            return (datetime.now() - last_date).days
    return None


def _render_projects_list(proyectos, tareas):
    """Compact list view for projects."""
    status_filter = st.selectbox("Filtrar", ["Todos", "Activos", "Pausados", "Completados", "Sin avance (+7 dias)"],
                                  label_visibility="collapsed", key="proj_status_f")

    filtered = proyectos.copy()
    if status_filter == "Activos":
        filtered = filtered[(filtered["estado"].isin(["activo", ""])) | (filtered["estado"].isna())]
    elif status_filter == "Pausados":
        filtered = filtered[filtered["estado"] == "pausado"]
    elif status_filter == "Completados":
        filtered = filtered[filtered["estado"] == "completado"]
    elif status_filter == "Sin avance (+7 dias)":
        filtered = filtered[(filtered["estado"].isin(["activo", ""])) | (filtered["estado"].isna())]

    # Pre-calculate stale projects for filter and badges
    stale_ids = set()
    for _, p in filtered.iterrows():
        proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
        days = _days_without_progress(proj_tasks)
        if days is not None and days >= 7:
            stale_ids.add(p["id"])

    if status_filter == "Sin avance (+7 dias)":
        filtered = filtered[filtered["id"].isin(stale_ids)]

    if filtered.empty:
        st.info("No hay proyectos en esta categoria.")
        return

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

            col_info, col_progress, col_actions = st.columns([4, 2, 2])
            with col_info:
                # Stale badge
                days = _days_without_progress(proj_tasks)
                stale_tag = ""
                if days is not None and days >= 7 and estado in ("activo", ""):
                    stale_tag = f"  :red[⏸ {days}d sin avance]"
                st.markdown(f"**{proj_emoji} {p['nombre']}**{stale_tag}")
                st.caption(f"{area_label} | {estado_label} | {done_tasks}/{total_tasks} tareas")
            with col_progress:
                st.progress(pct / 100, text=f"{pct}%")
            with col_actions:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    if st.button("📂", key=f"pview_{p['id']}", use_container_width=True, help="Abrir"):
                        st.session_state["proj_viewing"] = p["id"]
                        st.rerun()
                with c2:
                    if st.button("✏️", key=f"pedit_{p['id']}", use_container_width=True, help="Editar"):
                        st.session_state["proj_editing"] = True
                        st.session_state["proj_edit_id"] = p["id"]
                        st.rerun()
                with c3:
                    if st.button("📋", key=f"pdup_{p['id']}", use_container_width=True, help="Duplicar"):
                        _duplicate_project(p, proyectos, tareas)
                        st.rerun()
                with c4:
                    if confirm_delete(p["id"], p["nombre"], "proj"):
                        soft_delete(p, "proyecto", p["nombre"])
                        cascade_delete_project(p["id"])
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

    # --- ADD TASK + VIEW TOGGLE ---
    col_add_t, col_view_t = st.columns([2, 1])
    with col_add_t:
        if st.button("+ Tarea", type="primary", key="add_proj_task"):
            st.session_state["proj_task_adding"] = True
    with col_view_t:
        task_view = st.selectbox("Vista", ["Lista", "Kanban"], key="task_view_mode", label_visibility="collapsed")

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
            etiqueta_opts = list(ETIQUETAS.keys())
            etiqueta = c1.selectbox("Etiqueta", etiqueta_opts, format_func=lambda x: ETIQUETAS.get(x, x), key="new_task_tag")
            notas_txt = st.text_area("Descripcion", height=60)
            subtareas_txt = st.text_area("Subtareas (una por linea)", height=60,
                                         help="Escribe una subtarea por linea")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
                    st.error("La fecha de inicio no puede ser mayor a la fecha limite.")
                else:
                    sub_lines = [l.strip() for l in subtareas_txt.split("\n") if l.strip()] if subtareas_txt else []
                    subs_json = _save_subtareas([{"text": l, "fecha": "", "done": False} for l in sub_lines]) if sub_lines else ""
                    new_task = {
                        "id": uid(), "titulo": titulo.strip(), "area": project["area"],
                        "prioridad": prioridad,
                        "fecha_inicio": str(fecha_inicio) if fecha_inicio else "",
                        "fecha": str(fecha_fin) if fecha_fin else "",
                        "proyecto": proj_id, "notas": notas_txt, "subtareas": subs_json,
                        "recurrente": "", "depende_de": "", "etiqueta": etiqueta,
                        "done": False, "pinned": False, "archived": False, "ts": now_ts(),
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

    if task_view == "Kanban":
        _render_tasks_kanban(proj_tasks, tareas)
    else:
        _render_tasks_list(proj_tasks, tareas)


def _get_task_status(t, subs=None):
    """Determine task kanban status: pendiente / en_progreso / completada."""
    if t["done"]:
        return "completada"
    if subs is None:
        subs = _parse_subtareas(t.get("subtareas", ""))
    if subs and any(s.get("done") for s in subs) and not all(s.get("done") for s in subs):
        return "en_progreso"
    return "pendiente"


def _render_tasks_kanban(proj_tasks, tareas):
    """Kanban board: Pendiente | En progreso | Completada with filters and move arrows."""
    # Filters
    col_fpri, col_ftag = st.columns(2)
    with col_fpri:
        pri_filter = st.selectbox("Prioridad", ["Todas", "alta", "media", "baja"],
                                  format_func=lambda x: "Todas" if x == "Todas" else PRIORITY_LABELS.get(x, x),
                                  key="kb_pri_filter", label_visibility="collapsed")
    with col_ftag:
        tag_filter = st.selectbox("Etiqueta", list(ETIQUETAS.keys()),
                                  format_func=lambda x: ETIQUETAS.get(x, x),
                                  key="kb_tag_filter", label_visibility="collapsed")

    # Apply filters
    filtered = proj_tasks.copy()
    if pri_filter != "Todas":
        filtered = filtered[filtered["prioridad"] == pri_filter]
    if tag_filter:
        if "etiqueta" in filtered.columns:
            filtered = filtered[filtered["etiqueta"] == tag_filter]

    kanban_cols = [("pendiente", "⬜ Pendiente"), ("en_progreso", "🔄 En progreso"), ("completada", "✅ Completada")]
    status_list = [s[0] for s in kanban_cols]
    total_filtered = len(filtered) if not filtered.empty else 1

    cols = st.columns(3)
    for col, (status, label) in zip(cols, kanban_cols):
        with col:
            group = [t for _, t in filtered.iterrows() if _get_task_status(t) == status]
            count = len(group)
            pct_col = int(count / total_filtered * 100) if total_filtered > 0 else 0
            st.markdown(f"**{label}** ({count})")
            st.progress(pct_col / 100, text=f"{pct_col}%")

            idx = status_list.index(status)

            if not group:
                st.caption("—")
            for t in group:
                pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "")
                subs = _parse_subtareas(t.get("subtareas", ""))
                sub_done = sum(1 for s in subs if s.get("done"))
                tag = t.get("etiqueta", "")
                with st.container(border=True):
                    st.markdown(f"{pri_emoji} **{t['titulo']}**")
                    info = []
                    if t.get("fecha"):
                        info.append(f"📅 {t['fecha']}")
                    if subs:
                        info.append(f"☑️ {sub_done}/{len(subs)}")
                    if tag:
                        info.append(ETIQUETAS.get(tag, tag))
                    if info:
                        st.caption(" | ".join(info))
                    # Move arrows + Open
                    arrow_cols = st.columns([1, 1, 2])
                    with arrow_cols[0]:
                        if idx > 0:
                            target = status_list[idx - 1]
                            if st.button("←", key=f"kb_tl_{t['id']}", use_container_width=True):
                                _move_task_status(t, target, tareas)
                                st.rerun()
                    with arrow_cols[1]:
                        if idx < len(status_list) - 1:
                            target = status_list[idx + 1]
                            if st.button("→", key=f"kb_tr_{t['id']}", use_container_width=True):
                                _move_task_status(t, target, tareas)
                                st.rerun()
                    with arrow_cols[2]:
                        if st.button("Abrir", key=f"kb_t_{t['id']}", use_container_width=True):
                            st.session_state["task_detail_id"] = t["id"]
                            st.rerun()


def _move_task_status(task, target_status, tareas):
    """Move a task to a target kanban status by updating done/subtasks."""
    task_id = task["id"]
    if target_status == "completada":
        mark_task_done(tareas, task_id)
    elif target_status == "pendiente":
        tareas.loc[tareas["id"] == task_id, "done"] = False
        # Reset all subtasks
        subs = _parse_subtareas(task.get("subtareas", ""))
        if subs:
            for s in subs:
                s["done"] = False
            tareas.loc[tareas["id"] == task_id, "subtareas"] = _save_subtareas(subs)
    elif target_status == "en_progreso":
        tareas.loc[tareas["id"] == task_id, "done"] = False
        # Mark first subtask done if none are, to trigger en_progreso
        subs = _parse_subtareas(task.get("subtareas", ""))
        if subs and not any(s.get("done") for s in subs):
            subs[0]["done"] = True
            tareas.loc[tareas["id"] == task_id, "subtareas"] = _save_subtareas(subs)
    save_df("tareas", tareas)


def _render_tasks_list(proj_tasks, tareas):
    """Traditional list view for tasks with bulk operations."""
    pending = proj_tasks[~proj_tasks["done"]].copy()
    done_df = proj_tasks[proj_tasks["done"]].copy()

    pri_order = {"alta": 0, "media": 1, "baja": 2}
    if not pending.empty:
        pending["_pri"] = pending["prioridad"].map(pri_order).fillna(2)
        pending = pending.sort_values("_pri")

    # Bulk operations toggle
    bulk_mode = st.checkbox("Seleccion multiple", key="bulk_mode")

    if bulk_mode and not pending.empty:
        selected = []
        for _, t in pending.iterrows():
            col_sel, col_body = st.columns([0.3, 5.7])
            with col_sel:
                if st.checkbox("", key=f"bulk_{t['id']}", label_visibility="collapsed"):
                    selected.append(t["id"])
            with col_body:
                pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "")
                st.markdown(f"{pri_emoji} **{t['titulo']}**")
                info = []
                if t.get("fecha"):
                    info.append(f"📅 {t['fecha']}")
                tag = t.get("etiqueta", "")
                if tag:
                    info.append(ETIQUETAS.get(tag, tag))
                if info:
                    st.caption(" | ".join(info))

        if selected:
            st.divider()
            st.caption(f"{len(selected)} tarea(s) seleccionada(s)")
            bc1, bc2, bc3, bc4 = st.columns(4)
            with bc1:
                if st.button("✅ Completar", use_container_width=True, type="primary"):
                    for tid in selected:
                        mark_task_done(tareas, tid)
                    save_df("tareas", tareas)
                    st.rerun()
            with bc2:
                new_pri = st.selectbox("Prioridad", ["alta", "media", "baja"],
                                       format_func=lambda x: PRIORITY_LABELS.get(x, x),
                                       key="bulk_pri", label_visibility="collapsed")
                if st.button("Cambiar prioridad", use_container_width=True):
                    for tid in selected:
                        tareas.loc[tareas["id"] == tid, "prioridad"] = new_pri
                    save_df("tareas", tareas)
                    st.rerun()
            with bc3:
                new_tag = st.selectbox("Etiqueta", list(ETIQUETAS.keys()),
                                       format_func=lambda x: ETIQUETAS.get(x, x),
                                       key="bulk_tag", label_visibility="collapsed")
                if st.button("Cambiar etiqueta", use_container_width=True):
                    for tid in selected:
                        tareas.loc[tareas["id"] == tid, "etiqueta"] = new_tag
                    save_df("tareas", tareas)
                    st.rerun()
            with bc4:
                if st.button("🗑️ Eliminar", use_container_width=True):
                    for tid in selected:
                        row = tareas[tareas["id"] == tid]
                        if not row.empty:
                            soft_delete(row.iloc[0], "tarea", row.iloc[0]["titulo"])
                    tareas = tareas[~tareas["id"].isin(selected)]
                    save_df("tareas", tareas)
                    st.rerun()
    else:
        for _, t in pending.iterrows():
            _render_task_row(t, tareas, show_detail=True)

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
            tag = t.get("etiqueta", "")
            if tag:
                info.append(ETIQUETAS.get(tag, tag))
            if info:
                st.caption(" | ".join(info))
        with col_actions:
            if show_detail:
                if st.button("Abrir", key=f"td_{t['id']}", use_container_width=True):
                    st.session_state["task_detail_id"] = t["id"]
                    st.rerun()
            ca, cb = st.columns(2)
            with ca:
                if st.button("📋", key=f"tdup_{t['id']}", help="Duplicar"):
                    _duplicate_task(t, tareas)
                    st.rerun()
            with cb:
                pass
            if confirm_delete(t["id"], t["titulo"], "ptask"):
                soft_delete(t, "tarea", t["titulo"])
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
    subs = _parse_subtareas(task.get("subtareas", ""))
    sub_pending = sum(1 for s in subs if not s.get("done"))
    sub_done_count = sum(1 for s in subs if s.get("done"))

    col_sub_header, col_sub_view = st.columns([3, 1])
    with col_sub_header:
        st.subheader(f"Subtareas ({sub_done_count}/{len(subs)})" if subs else "Subtareas")
    with col_sub_view:
        sub_view = st.selectbox("Vista", ["Lista", "Kanban"], key="sub_view_mode", label_visibility="collapsed") if subs else "Lista"

    if subs:
        updated = False

        if sub_view == "Kanban":
            total_subs = len(subs) if subs else 1
            pct_pend = int(sub_pending / total_subs * 100) if total_subs > 0 else 0
            pct_done = int(sub_done_count / total_subs * 100) if total_subs > 0 else 0

            col_pend, col_done = st.columns(2)
            with col_pend:
                st.markdown(f"**⬜ Pendientes** ({sub_pending})")
                st.progress(pct_pend / 100, text=f"{pct_pend}%")
                for i, sub in enumerate(subs):
                    if sub.get("done"):
                        continue
                    with st.container(border=True):
                        st.markdown(sub["text"])
                        sub_fecha = sub.get("fecha", "")
                        if sub_fecha:
                            today = datetime.now().strftime("%Y-%m-%d")
                            color = "red" if sub_fecha < today else "gray"
                            st.caption(f":{color}[📅 {sub_fecha}]")
                        if st.button("Completar →", key=f"sub_mv_{task_id}_{i}", use_container_width=True):
                            subs[i]["done"] = True
                            updated = True
                if sub_pending == 0:
                    st.caption("—")
            with col_done:
                st.markdown(f"**✅ Completadas** ({sub_done_count})")
                st.progress(pct_done / 100, text=f"{pct_done}%")
                for i, sub in enumerate(subs):
                    if not sub.get("done"):
                        continue
                    with st.container(border=True):
                        st.markdown(f"~~{sub['text']}~~")
                        if st.button("← Reabrir", key=f"sub_mv_{task_id}_{i}", use_container_width=True):
                            subs[i]["done"] = False
                            updated = True
                if sub_done_count == 0:
                    st.caption("—")
        else:
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

        etiqueta_opts = list(ETIQUETAS.keys())
        current_tag = task.get("etiqueta", "") or ""
        etiqueta = st.selectbox("Etiqueta", etiqueta_opts,
                                format_func=lambda x: ETIQUETAS.get(x, x),
                                index=etiqueta_opts.index(current_tag) if current_tag in etiqueta_opts else 0,
                                key="edit_task_tag")

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
            if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
                st.error("La fecha de inicio no puede ser mayor a la fecha limite.")
            else:
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
                tareas.loc[tareas["id"] == task["id"], "etiqueta"] = etiqueta
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
            if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
                st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
            else:
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
            "recurrente": "", "depende_de": "", "etiqueta": "",
            "done": False, "pinned": False, "archived": False, "ts": now_ts(),
        })
    if new_tasks:
        tareas = pd.concat([pd.DataFrame(new_tasks), tareas], ignore_index=True)
        save_df("tareas", tareas)


def _duplicate_project(project, proyectos, tareas):
    """Duplicate a project with all its tasks."""
    new_proj_id = uid()
    new_proj = {
        "id": new_proj_id, "nombre": f"{project['nombre']} (copia)",
        "area": project["area"], "emoji": project.get("emoji", "📁"),
        "desc": project.get("desc", ""), "estado": "activo",
        "fecha_inicio": "", "fecha_fin": "",
        "plantilla": False, "compartido": "", "ts": now_ts(),
    }
    proyectos = pd.concat([pd.DataFrame([new_proj]), proyectos], ignore_index=True)
    save_df("proyectos", proyectos)

    # Duplicate tasks
    proj_tasks = tareas[tareas["proyecto"] == project["id"]] if not tareas.empty else pd.DataFrame()
    if not proj_tasks.empty:
        new_tasks = []
        for _, t in proj_tasks.iterrows():
            new_tasks.append({
                "id": uid(), "titulo": t["titulo"], "area": t["area"],
                "prioridad": t["prioridad"], "fecha_inicio": "", "fecha": "",
                "proyecto": new_proj_id, "notas": t.get("notas", ""),
                "subtareas": t.get("subtareas", ""), "recurrente": "",
                "depende_de": "", "etiqueta": t.get("etiqueta", ""),
                "done": False, "pinned": False, "archived": False, "ts": now_ts(),
            })
        if new_tasks:
            tareas = pd.concat([pd.DataFrame(new_tasks), tareas], ignore_index=True)
            save_df("tareas", tareas)


def _duplicate_task(task, tareas):
    """Duplicate a single task."""
    new_task = {
        "id": uid(), "titulo": f"{task['titulo']} (copia)",
        "area": task["area"], "prioridad": task["prioridad"],
        "fecha_inicio": "", "fecha": "",
        "proyecto": task.get("proyecto", ""), "notas": task.get("notas", ""),
        "subtareas": task.get("subtareas", ""), "recurrente": "",
        "depende_de": "", "etiqueta": task.get("etiqueta", ""),
        "done": False, "pinned": False, "archived": False, "ts": now_ts(),
    }
    tareas = pd.concat([pd.DataFrame([new_task]), tareas], ignore_index=True)
    save_df("tareas", tareas)
