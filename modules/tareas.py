import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, PRIORITY_LABELS
from core.utils import PRIORITY_EMOJIS, confirm_delete, export_csv, get_area_id, mark_task_done


def _auto_generate_recurring(tareas):
    """When a recurring task is completed, generate the next occurrence."""
    from datetime import datetime, timedelta
    if tareas.empty:
        return tareas

    recurring_done = tareas[(tareas["done"]) & (tareas["recurrente"] != "") & (tareas["recurrente"].notna())]
    if recurring_done.empty:
        return tareas

    new_tasks = []
    for _, t in recurring_done.iterrows():
        # Check if next occurrence already exists (same title, not done)
        existing = tareas[(tareas["titulo"] == t["titulo"]) & (~tareas["done"]) & (tareas["recurrente"] == t["recurrente"])]
        if not existing.empty:
            continue

        # Calculate next date
        base_date = datetime.now().date()
        if t.get("fecha"):
            try:
                base_date = datetime.strptime(str(t["fecha"]), "%Y-%m-%d").date()
            except ValueError:
                pass

        freq = t["recurrente"]
        if freq == "diario":
            next_date = base_date + timedelta(days=1)
        elif freq == "semanal":
            next_date = base_date + timedelta(weeks=1)
        elif freq == "mensual":
            month = base_date.month + 1
            year = base_date.year
            if month > 12:
                month = 1
                year += 1
            day = min(base_date.day, 28)
            next_date = base_date.replace(year=year, month=month, day=day)
        else:
            continue

        # Ensure next_date is in the future
        today = datetime.now().date()
        while next_date <= today:
            if freq == "diario":
                next_date += timedelta(days=1)
            elif freq == "semanal":
                next_date += timedelta(weeks=1)
            elif freq == "mensual":
                month = next_date.month + 1
                year = next_date.year
                if month > 12:
                    month = 1
                    year += 1
                day = min(next_date.day, 28)
                next_date = next_date.replace(year=year, month=month, day=day)

        new_tasks.append({
            "id": uid(), "titulo": t["titulo"], "area": t["area"],
            "prioridad": t["prioridad"],
            "fecha_inicio": str(next_date),
            "fecha": str(next_date),
            "proyecto": t.get("proyecto", ""), "notas": t.get("notas", ""),
            "subtareas": "", "recurrente": t["recurrente"],
            "depende_de": "", "etiqueta": t.get("etiqueta", ""),
            "done": False, "pinned": False, "archived": False, "ts": now_ts(),
        })

    if new_tasks:
        tareas = pd.concat([pd.DataFrame(new_tasks), tareas], ignore_index=True)
        save_df("tareas", tareas)

    return tareas


def render():
    st.header("Tareas")

    tareas = get_df("tareas")
    tareas = _auto_generate_recurring(tareas)
    proyectos = get_df("proyectos")

    # --- View toggle ---
    col_view, col_spacer = st.columns([2, 4])
    with col_view:
        view_mode = st.radio("Vista", ["Lista", "Kanban"], horizontal=True, key="tareas_view", label_visibility="collapsed")

    # --- Toolbar ---
    col_filter, col_area, col_export, col_add = st.columns([2, 2, 1, 1])
    with col_filter:
        status_filter = st.selectbox("Estado", ["Pendientes", "Completadas", "Archivadas", "Todas"], label_visibility="collapsed")
    with col_area:
        area_options = ["Todas las areas"] + [f'{a["emoji"]} {a["name"]}' for a in AREAS]
        area_filter = st.selectbox("Area", area_options, label_visibility="collapsed", key="tarea_area_f")
    with col_export:
        export_csv(tareas, "tareas.csv", "CSV")
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

            subtareas_txt = st.text_area(
                "Subtareas (una por linea)",
                value=existing.get("subtareas", "") if existing is not None else "",
                height=80,
                help="Escribe una subtarea por linea. Marca completadas con [x] al inicio.",
            )

            c5, c6 = st.columns(2)
            recurrente_opts = ["", "diario", "semanal", "mensual"]
            recurrente = c5.selectbox(
                "Recurrencia",
                recurrente_opts,
                format_func=lambda x: {"": "No se repite", "diario": "Diario", "semanal": "Semanal", "mensual": "Mensual"}.get(x, x),
                index=recurrente_opts.index(existing.get("recurrente", "")) if existing is not None and existing.get("recurrente", "") in recurrente_opts else 0,
            )

            # Dependency
            dep_options = [""]
            dep_labels = ["Sin dependencia"]
            if not tareas.empty:
                other_tasks = tareas[tareas["id"] != edit_id] if edit_id else tareas
                for _, ot in other_tasks.iterrows():
                    dep_options.append(ot["id"])
                    dep_labels.append(ot["titulo"])
            dep_idx = 0
            if existing is not None and existing.get("depende_de", "") in dep_options:
                dep_idx = dep_options.index(existing["depende_de"])
            depende_de = c6.selectbox("Depende de", dep_options,
                                      format_func=lambda x: dep_labels[dep_options.index(x)] if x in dep_options else x,
                                      index=dep_idx, help="Esta tarea no puede completarse hasta que la dependencia este hecha")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                new_row = {
                    "id": edit_id or uid(),
                    "titulo": titulo.strip(),
                    "area": area,
                    "prioridad": prioridad,
                    "fecha_inicio": existing.get("fecha_inicio", "") if existing is not None else "",
                    "fecha": str(fecha) if fecha else "",
                    "proyecto": proyecto,
                    "notas": notas_txt,
                    "subtareas": subtareas_txt,
                    "recurrente": recurrente,
                    "depende_de": depende_de,
                    "etiqueta": existing.get("etiqueta", "") if existing is not None else "",
                    "done": existing["done"] if existing is not None else False,
                    "pinned": existing.get("pinned", False) if existing is not None else False,
                    "archived": False,
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
            if "archived" in filtered.columns:
                filtered = filtered[~filtered["archived"].fillna(False)]
            filtered = filtered[~filtered["done"]]
        elif status_filter == "Completadas":
            if "archived" in filtered.columns:
                filtered = filtered[~filtered["archived"].fillna(False)]
            filtered = filtered[filtered["done"]]
        elif status_filter == "Archivadas":
            if "archived" in filtered.columns:
                filtered = filtered[filtered["archived"].fillna(False)]
        # "Todas" shows everything

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

    # Sort pinned first
    if "pinned" in filtered.columns:
        filtered["_pin_ord"] = (~filtered["pinned"].fillna(False)).astype(int)
        filtered = filtered.sort_values(["_pin_ord", "_done_ord", "_pri_ord"] if "_done_ord" in filtered.columns else ["_pin_ord"])

    for _, t in filtered.iterrows():
        pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "")
        area_label = AREA_LABELS.get(t["area"], t["area"])
        fecha_str = f" {t['fecha']}" if t.get("fecha") else ""
        pin_icon = "📌 " if t.get("pinned", False) else ""
        recur_icon = " 🔁" if t.get("recurrente", "") else ""

        # Check dependency
        dep_blocked = False
        dep_name = ""
        if t.get("depende_de", ""):
            dep_task = tareas[tareas["id"] == t["depende_de"]]
            if not dep_task.empty and not dep_task.iloc[0]["done"]:
                dep_blocked = True
                dep_name = dep_task.iloc[0]["titulo"]

        col_check, col_body, col_actions = st.columns([0.5, 6, 2])
        with col_check:
            done = st.checkbox("", value=t["done"], key=f"tcheck_{t['id']}", label_visibility="collapsed",
                               disabled=dep_blocked)
            if done != t["done"] and not dep_blocked:
                tareas.loc[tareas["id"] == t["id"], "done"] = done
                save_df("tareas", tareas)
                st.rerun()
        with col_body:
            style = "~~" if t["done"] else ""
            st.markdown(f"{pin_icon}{pri_emoji} {style}**{t['titulo']}**{style} - {area_label}{fecha_str}{recur_icon}")
            if dep_blocked:
                st.caption(f"🔒 Bloqueada por: *{dep_name}*")
            # Subtasks inline
            subtareas_str = t.get("subtareas", "")
            if subtareas_str:
                lines = [l.strip() for l in subtareas_str.split("\n") if l.strip()]
                for line in lines[:3]:
                    check = "✅" if line.startswith("[x]") else "⬜"
                    text = line.replace("[x] ", "").replace("[x]", "")
                    st.caption(f"  {check} {text}")
        with col_actions:
            ac1, ac2, ac3, ac4, ac5 = st.columns(5)
            with ac1:
                pin_label = "📌" if not t.get("pinned", False) else "❌"
                if st.button(pin_label, key=f"tpin_{t['id']}"):
                    tareas.loc[tareas["id"] == t["id"], "pinned"] = not t.get("pinned", False)
                    save_df("tareas", tareas)
                    st.rerun()
            with ac2:
                if st.button("📦", key=f"tarch_{t['id']}", help="Archivar"):
                    tareas.loc[tareas["id"] == t["id"], "archived"] = True
                    save_df("tareas", tareas)
                    st.rerun()
            with ac3:
                if st.button("💬", key=f"tcomm_{t['id']}", help="Comentarios"):
                    st.session_state["tarea_comments_id"] = t["id"]
                    st.rerun()
            with ac4:
                if st.button("✏️", key=f"tedit_{t['id']}"):
                    st.session_state["tarea_editing"] = True
                    st.session_state["tarea_edit_id"] = t["id"]
                    st.rerun()
            with ac5:
                if confirm_delete(t["id"], t["titulo"], "tarea"):
                    tareas = tareas[tareas["id"] != t["id"]]
                    save_df("tareas", tareas)
                    st.rerun()

    # --- Comments panel ---
    comment_id = st.session_state.get("tarea_comments_id")
    if comment_id:
        _render_comments(comment_id, tareas)


def _render_comments(tarea_id, tareas):
    """Render comments panel for a task."""
    task_match = tareas[tareas["id"] == tarea_id]
    if task_match.empty:
        return

    task = task_match.iloc[0]
    comments = get_df("task_comments")
    task_comments = comments[comments["tarea_id"] == tarea_id].sort_values("ts", ascending=False) if not comments.empty else pd.DataFrame()

    st.divider()
    col_t, col_close = st.columns([5, 1])
    with col_t:
        st.subheader(f"Comentarios: {task['titulo']}")
    with col_close:
        if st.button("Cerrar", key="close_comments"):
            st.session_state["tarea_comments_id"] = None
            st.rerun()

    # Add comment
    with st.form("comment_form", clear_on_submit=True):
        texto = st.text_area("Nuevo comentario", height=80, placeholder="Escribe un comentario...")
        if st.form_submit_button("Agregar comentario", type="primary"):
            if texto.strip():
                new_comment = {
                    "id": uid(),
                    "tarea_id": tarea_id,
                    "texto": texto.strip(),
                    "autor": st.session_state.get("current_user", ""),
                    "ts": now_ts(),
                }
                comments = pd.concat([pd.DataFrame([new_comment]), comments], ignore_index=True)
                save_df("task_comments", comments)
                st.rerun()

    # Display comments
    if task_comments.empty:
        st.caption("No hay comentarios aun.")
    else:
        for _, c in task_comments.iterrows():
            from datetime import datetime
            ts_str = datetime.fromtimestamp(c["ts"]).strftime("%d/%m/%Y %H:%M") if c["ts"] else ""
            with st.container(border=True):
                st.caption(f"**{c['autor']}** - {ts_str}")
                st.markdown(c["texto"])


def _render_kanban(filtered, tareas):
    col_alta, col_media, col_baja, col_done = st.columns(4)

    for col, pri, label, color in [
        (col_alta, "alta", "🔴 Alta", "#c96a6a"),
        (col_media, "media", "🟡 Media", "#c9943a"),
        (col_baja, "baja", "🟢 Baja", "#4a9e7a"),
    ]:
        with col:
            st.markdown(f"### {label}")
            items = filtered[(~filtered["done"]) & (filtered["prioridad"] == pri)]
            for _, t in items.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{t['titulo']}**")
                    st.caption(AREA_LABELS.get(t["area"], t["area"]))
                    if t.get("fecha"):
                        st.caption(f"{t['fecha']}")
                    if st.checkbox("Hecho", key=f"kb_done_{t['id']}"):
                        mark_task_done(tareas, t["id"])
                        save_df("tareas", tareas)
                        st.rerun()

    with col_done:
        st.markdown("### ✅ Hechas")
        done = filtered[filtered["done"]]
        for _, t in done.iterrows():
            with st.container(border=True):
                st.markdown(f"~~{t['titulo']}~~")
                st.caption(AREA_LABELS.get(t["area"], t["area"]))
