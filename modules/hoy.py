import streamlit as st
import json
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df, save_df
from core.constants import AREA_LABELS, PRIORITY_LABELS
from core.utils import PRIORITY_EMOJIS


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
    # Fallback: plain text format
    lines = [l.strip() for l in subtareas_str.split("\n") if l.strip()]
    result = []
    for line in lines:
        done = line.startswith("[x]")
        text = line.replace("[x] ", "").replace("[x]", "").replace("[ ] ", "").replace("[ ]", "").strip()
        result.append({"text": text, "fecha": "", "done": done})
    return result


def _check_undo():
    """Show undo banner if a recent action can be reverted."""
    import time
    undo = st.session_state.get("undo_action")
    if not undo:
        return
    # Auto-expire after 8 seconds
    if time.time() - undo.get("ts", 0) > 8:
        st.session_state["undo_action"] = None
        return

    with st.container(border=True):
        col_msg, col_btn = st.columns([5, 1])
        with col_msg:
            st.success(f"✅ {undo['msg']}")
        with col_btn:
            if st.button("Deshacer", type="primary", use_container_width=True):
                _execute_undo(undo)
                st.session_state["undo_action"] = None
                st.rerun()


def _execute_undo(undo):
    """Revert the last action."""
    tipo = undo.get("tipo")
    if tipo == "task_done":
        tareas = get_df("tareas")
        tareas.loc[tareas["id"] == undo["id"], "done"] = False
        save_df("tareas", tareas)
    elif tipo == "subtask_done":
        tareas = get_df("tareas")
        task_row = tareas[tareas["id"] == undo["tarea_id"]]
        if not task_row.empty:
            subs = _parse_subtareas(task_row.iloc[0].get("subtareas", ""))
            idx = undo["sub_index"]
            if idx < len(subs):
                subs[idx]["done"] = False
                tareas.loc[tareas["id"] == undo["tarea_id"], "subtareas"] = json.dumps(subs, ensure_ascii=False)
                save_df("tareas", tareas)
    elif tipo == "habit_done":
        from core.utils import parse_checks
        habitos = get_df("habitos")
        h_row = habitos[habitos["id"] == undo["id"]]
        if not h_row.empty:
            checks = parse_checks(h_row.iloc[0].get("checks", "{}"))
            checks[undo["fecha"]] = False
            habitos.loc[habitos["id"] == undo["id"], "checks"] = json.dumps(checks)
            save_df("habitos", habitos)


def render():
    st.header("Hoy")

    _check_undo()

    tab_pendientes, tab_plan, tab_focus = st.tabs(["Pendientes", "Planificador", "Modo enfoque"])

    with tab_pendientes:
        _render_pendientes()

    with tab_plan:
        _render_planificador()

    with tab_focus:
        _render_focus_mode()


def _render_pendientes():
    st.caption("Todo lo que tienes pendiente para hoy")

    today = datetime.now().strftime("%Y-%m-%d")
    tareas = get_df("tareas")
    proyectos = get_df("proyectos")

    # === TASKS DUE TODAY OR OVERDUE ===
    pending_tasks = tareas[~tareas["done"]].copy() if not tareas.empty else pd.DataFrame()

    tasks_today = pending_tasks[
        (pending_tasks["fecha"] != "") &
        (pending_tasks["fecha"] <= today)
    ].copy() if not pending_tasks.empty else pd.DataFrame()

    # === SUBTASKS DUE TODAY OR OVERDUE ===
    subtask_items = []
    if not pending_tasks.empty:
        for _, t in pending_tasks.iterrows():
            subs = _parse_subtareas(t.get("subtareas", ""))
            for i, sub in enumerate(subs):
                if sub.get("done"):
                    continue
                sub_fecha = sub.get("fecha", "")
                if sub_fecha and sub_fecha <= today:
                    proj_name = ""
                    proj_id = t.get("proyecto", "")
                    if proj_id and not proyectos.empty:
                        proj_match = proyectos[proyectos["id"] == proj_id]
                        if not proj_match.empty:
                            proj_name = proj_match.iloc[0]["nombre"]

                    subtask_items.append({
                        "tarea_id": t["id"],
                        "tarea_titulo": t["titulo"],
                        "proyecto": proj_name,
                        "proyecto_id": proj_id,
                        "sub_index": i,
                        "sub_text": sub["text"],
                        "sub_fecha": sub_fecha,
                        "overdue": sub_fecha < today,
                    })

    # === HABITS ===
    from core.data import get_df as _get_df
    from core.utils import is_done_today, habit_applies_today
    habitos = _get_df("habitos")
    today_habs = []
    if not habitos.empty:
        for _, h in habitos.iterrows():
            if habit_applies_today(h):
                today_habs.append(h)
    habs_done = sum(1 for h in today_habs if is_done_today(h))

    # === METRICS ===
    total_tasks = len(tasks_today)
    total_subs = len(subtask_items)
    total_habs = len(today_habs)

    c1, c2, c3 = st.columns(3)
    overdue_count = len(tasks_today[tasks_today["fecha"] < today]) if not tasks_today.empty else 0
    c1.metric("Tareas hoy", f"{total_tasks}", delta=f"{overdue_count} atrasadas" if overdue_count else None, delta_color="inverse")
    c2.metric("Subtareas hoy", f"{total_subs}")
    c3.metric("Habitos", f"{habs_done}/{total_habs}")

    # ═══ TASK SUMMARY BY PERIOD ═══
    if not tareas.empty:
        pending_all = tareas[(~tareas["done"]) & (tareas["fecha"] != "")]
        if not pending_all.empty:
            now_dt = datetime.now()
            # Week: rest of this week (until Sunday)
            days_to_sunday = 6 - now_dt.weekday()
            end_week = (now_dt + timedelta(days=days_to_sunday)).strftime("%Y-%m-%d")
            # Biweekly
            end_quincena = (now_dt + timedelta(days=14)).strftime("%Y-%m-%d")
            # Month end
            if now_dt.month == 12:
                end_month = f"{now_dt.year + 1}-01-01"
            else:
                end_month = f"{now_dt.year}-{now_dt.month + 1:02d}-01"

            week_tasks = pending_all[(pending_all["fecha"] >= today) & (pending_all["fecha"] <= end_week)]
            quin_tasks = pending_all[(pending_all["fecha"] >= today) & (pending_all["fecha"] <= end_quincena)]
            month_tasks = pending_all[(pending_all["fecha"] >= today) & (pending_all["fecha"] < end_month)]

            with st.expander("📊 Resumen de tareas pendientes"):
                r1, r2, r3 = st.columns(3)
                r1.metric("Esta semana", len(week_tasks))
                r2.metric("Proximos 15 dias", len(quin_tasks))
                r3.metric("Este mes", len(month_tasks))

    st.divider()

    # ═══ HABITS SECTION ═══
    pending_habs = [h for h in today_habs if not is_done_today(h)]
    done_habs = [h for h in today_habs if is_done_today(h)]

    if pending_habs:
        st.subheader(f"◉ Habitos ({habs_done}/{total_habs})")
        _render_today_habits_compact(pending_habs, habitos)
        st.divider()

    # ═══ OVERDUE SECTION ═══
    overdue_tasks = tasks_today[tasks_today["fecha"] < today] if not tasks_today.empty else pd.DataFrame()
    overdue_subs = [s for s in subtask_items if s["overdue"]]

    if (not overdue_tasks.empty) or overdue_subs:
        st.subheader("🔴 Atrasadas")
        if not overdue_tasks.empty:
            _render_tasks_by_project(overdue_tasks, tareas, proyectos, overdue=True)
        for sub in overdue_subs:
            _render_today_subtask(sub, tareas)
        st.divider()

    # ═══ TODAY SECTION - GROUPED BY PROJECT ═══
    due_today_tasks = tasks_today[tasks_today["fecha"] == today] if not tasks_today.empty else pd.DataFrame()
    today_subs = [s for s in subtask_items if not s["overdue"]]

    st.subheader("📋 Para hoy")

    if due_today_tasks.empty and not today_subs:
        st.success("No hay tareas pendientes para hoy. Buen trabajo!")
    else:
        if not due_today_tasks.empty:
            _render_tasks_by_project(due_today_tasks, tareas, proyectos, overdue=False)
        for sub in today_subs:
            _render_today_subtask(sub, tareas)

    # --- Tasks without date ---
    if not pending_tasks.empty:
        tasks_no_date = pending_tasks[pending_tasks["fecha"] == ""].copy()
        if not tasks_no_date.empty:
            st.divider()
            with st.expander(f"📌 Sin fecha asignada ({len(tasks_no_date)})"):
                _render_tasks_by_project(tasks_no_date, tareas, proyectos, overdue=False)

    # ═══ COMPLETED HABITS (at the bottom) ═══
    if done_habs:
        st.divider()
        with st.expander(f"✅ Habitos completados ({len(done_habs)}/{total_habs})"):
            _render_today_habits_compact(done_habs, habitos)


def _render_tasks_by_project(task_df, tareas, proyectos, overdue=False):
    """Render tasks grouped by project."""
    if task_df.empty:
        return

    # Group by project
    groups = {}
    for _, t in task_df.iterrows():
        proj_id = t.get("proyecto", "") or ""
        if proj_id not in groups:
            proj_name = "Sin proyecto"
            proj_emoji = "📋"
            if proj_id and not proyectos.empty:
                pm = proyectos[proyectos["id"] == proj_id]
                if not pm.empty:
                    proj_name = pm.iloc[0]["nombre"]
                    proj_emoji = pm.iloc[0].get("emoji", "📁")
            groups[proj_id] = {"name": proj_name, "emoji": proj_emoji, "tasks": []}
        groups[proj_id]["tasks"].append(t)

    for proj_id, group in groups.items():
        if len(groups) > 1 or proj_id:
            st.caption(f"{group['emoji']} **{group['name']}**")
        for t in group["tasks"]:
            _render_today_task(t, tareas, proyectos, overdue=overdue)


def _render_today_habits_compact(today_habs, habitos):
    """Compact habit rendering for the Hoy page."""
    from core.data import save_df as _save_df
    from core.utils import parse_checks, is_done_today, get_day_completion
    import json as _json

    today_str = datetime.now().strftime("%Y-%m-%d")

    for h in today_habs:
        checks = parse_checks(h.get("checks", "{}"))
        reps = [r.strip() for r in h.get("repeticiones", "").split(",") if r.strip()]
        done_today = is_done_today(h)
        emoji = h.get("emoji", "⭐")

        with st.container(border=True):
            if reps:
                # Sub-checks mode
                today_val = checks.get(today_str, {})
                if not isinstance(today_val, dict):
                    today_val = {r: bool(today_val) for r in reps}
                d_count, t_count = get_day_completion(h, today_str)
                pct = int(d_count / t_count * 100) if t_count > 0 else 0

                status = "~~" if done_today else ""
                st.markdown(f"{emoji} {status}**{h['name']}**{status} — {d_count}/{t_count} ({pct}%)")

                rep_cols = st.columns(len(reps))
                for ri, rep in enumerate(reps):
                    with rep_cols[ri]:
                        rep_done = today_val.get(rep, False)
                        new_val = st.checkbox(rep.capitalize(), value=rep_done, key=f"hoy_hrep_{h['id']}_{ri}")
                        if new_val != rep_done:
                            today_val[rep] = new_val
                            checks[today_str] = today_val
                            habitos.loc[habitos["id"] == h["id"], "checks"] = _json.dumps(checks)
                            _save_df("habitos", habitos)
                            st.rerun()
            else:
                # Simple mode
                col_c, col_n = st.columns([0.5, 5.5])
                with col_c:
                    new_done = st.checkbox("", value=done_today, key=f"hoy_hab_{h['id']}", label_visibility="collapsed")
                    if new_done != done_today:
                        import time as _time
                        checks[today_str] = new_done
                        habitos.loc[habitos["id"] == h["id"], "checks"] = _json.dumps(checks)
                        _save_df("habitos", habitos)
                        if new_done:
                            st.session_state["undo_action"] = {"tipo": "habit_done", "id": h["id"], "fecha": today_str, "msg": f"Habito completado: {h['name']}", "ts": _time.time()}
                        st.rerun()
                with col_n:
                    status = "~~" if done_today else ""
                    st.markdown(f"{emoji} {status}**{h['name']}**{status}")


def _render_today_task(t, tareas, proyectos, overdue=False):
    """Render a task in the today view."""
    pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "")
    proj_name = ""
    if t.get("proyecto") and not proyectos.empty:
        proj_match = proyectos[proyectos["id"] == t["proyecto"]]
        if not proj_match.empty:
            proj_name = proj_match.iloc[0]["nombre"]

    with st.container(border=True):
        col_check, col_body = st.columns([0.5, 5.5])
        with col_check:
            if st.checkbox("", value=False, key=f"today_tc_{t['id']}", label_visibility="collapsed"):
                import time as _time
                tareas.loc[tareas["id"] == t["id"], "done"] = True
                save_df("tareas", tareas)
                st.session_state["undo_action"] = {"tipo": "task_done", "id": t["id"], "msg": f"Tarea completada: {t['titulo']}", "ts": _time.time()}
                st.rerun()
        with col_body:
            overdue_tag = " `ATRASADA`" if overdue else ""
            st.markdown(f"{pri_emoji} **{t['titulo']}**{overdue_tag}")
            info = []
            if proj_name:
                info.append(f"📂 {proj_name}")
            if t.get("fecha"):
                info.append(f"📅 {t['fecha']}")
            info.append(AREA_LABELS.get(t["area"], t["area"]))
            st.caption(" | ".join(info))

            # Show subtasks count
            subs = _parse_subtareas(t.get("subtareas", ""))
            if subs:
                done_count = sum(1 for s in subs if s.get("done"))
                st.caption(f"☑️ Subtareas: {done_count}/{len(subs)}")


def _render_today_subtask(sub, tareas):
    """Render a subtask in the today view."""
    overdue_tag = " `ATRASADA`" if sub["overdue"] else ""
    with st.container(border=True):
        col_check, col_body = st.columns([0.5, 5.5])
        with col_check:
            if st.checkbox("", value=False, key=f"today_sub_{sub['tarea_id']}_{sub['sub_index']}", label_visibility="collapsed"):
                import time as _time
                task_row = tareas[tareas["id"] == sub["tarea_id"]]
                if not task_row.empty:
                    subs = _parse_subtareas(task_row.iloc[0].get("subtareas", ""))
                    if sub["sub_index"] < len(subs):
                        subs[sub["sub_index"]]["done"] = True
                        tareas.loc[tareas["id"] == sub["tarea_id"], "subtareas"] = json.dumps(subs, ensure_ascii=False)
                        save_df("tareas", tareas)
                        st.session_state["undo_action"] = {"tipo": "subtask_done", "tarea_id": sub["tarea_id"], "sub_index": sub["sub_index"], "msg": f"Subtarea completada: {sub['sub_text']}", "ts": _time.time()}
                        st.rerun()
        with col_body:
            st.markdown(f"↳ **{sub['sub_text']}**{overdue_tag}")
            info = []
            if sub["proyecto"]:
                info.append(f"📂 {sub['proyecto']}")
            info.append(f"📋 {sub['tarea_titulo']}")
            if sub["sub_fecha"]:
                info.append(f"📅 {sub['sub_fecha']}")
            st.caption(" | ".join(info))


def _render_planificador():
    """Daily planner with hourly time blocks."""
    from core.data import get_df as _get_df, save_df as _save_df, uid as _uid, now_ts as _now_ts

    today = datetime.now().strftime("%Y-%m-%d")
    tareas = _get_df("tareas")
    proyectos = _get_df("proyectos")
    blocks = _get_df("plan_blocks")

    # Auto-move incomplete blocks from previous days
    if not blocks.empty:
        past_incomplete = blocks[(blocks["fecha"] < today) & (~blocks["completado"])]
        if not past_incomplete.empty:
            moved = 0
            for _, b in past_incomplete.iterrows():
                blocks.loc[blocks["id"] == b["id"], "fecha"] = today
                moved += 1
                # Also move linked task due date
                if b["tarea_id"] and not tareas.empty:
                    task_match = tareas[tareas["id"] == b["tarea_id"]]
                    if not task_match.empty and not task_match.iloc[0]["done"]:
                        tareas.loc[tareas["id"] == b["tarea_id"], "fecha"] = today
            if moved > 0:
                _save_df("plan_blocks", blocks)
                _save_df("tareas", tareas)
                st.info(f"{moved} bloque(s) pendiente(s) movido(s) a hoy.")

    today_blocks = blocks[blocks["fecha"] == today].sort_values("hora") if not blocks.empty else pd.DataFrame()

    # Summary
    total_blocks = len(today_blocks) if not today_blocks.empty else 0
    done_blocks = int(today_blocks["completado"].sum()) if not today_blocks.empty else 0
    total_hours = today_blocks["duracion"].sum() / 60 if not today_blocks.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Bloques", f"{done_blocks}/{total_blocks}")
    c2.metric("Horas planificadas", f"{total_hours:.1f}h")
    c3.metric("Completado", f"{int(done_blocks/total_blocks*100)}%" if total_blocks > 0 else "0%")

    st.divider()

    # Add block
    col_add, _ = st.columns([1, 5])
    with col_add:
        if st.button("+ Bloque", type="primary", use_container_width=True):
            st.session_state["plan_adding"] = True

    if st.session_state.get("plan_adding"):
        with st.form("plan_block_form", clear_on_submit=True):
            st.subheader("Nuevo bloque")

            c1, c2 = st.columns(2)
            horas = [f"{h:02d}:00" for h in range(5, 24)]
            hora = c1.selectbox("Hora", horas, index=3)
            dur_options = [15, 30, 45, 60, 90, 120]
            duracion = c2.selectbox("Duracion (min)", dur_options, index=2, format_func=lambda x: f"{x} min ({x/60:.1f}h)" if x >= 60 else f"{x} min")

            # Task selector
            pending_tasks = tareas[~tareas["done"]] if not tareas.empty else pd.DataFrame()
            task_options = ["Actividad libre"]
            task_ids = [""]
            if not pending_tasks.empty:
                for _, t in pending_tasks.iterrows():
                    pri = {"alta": "🔴", "media": "🟡", "baja": "🟢"}.get(t["prioridad"], "")
                    proj_name = ""
                    if t.get("proyecto") and not proyectos.empty:
                        pm = proyectos[proyectos["id"] == t["proyecto"]]
                        if not pm.empty:
                            proj_name = f" ({pm.iloc[0]['nombre']})"
                    task_options.append(f"{pri} {t['titulo']}{proj_name}")
                    task_ids.append(t["id"])

            task_sel = st.selectbox("Tarea", range(len(task_options)), format_func=lambda i: task_options[i])
            titulo = ""
            if task_sel == 0:
                titulo = st.text_input("Titulo del bloque", placeholder="Que vas a hacer?")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Agregar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted:
                block_titulo = titulo.strip() if task_sel == 0 else task_options[task_sel]
                if block_titulo or task_ids[task_sel]:
                    new_block = {
                        "id": _uid(), "fecha": today, "hora": hora,
                        "tarea_id": task_ids[task_sel],
                        "titulo": block_titulo or task_options[task_sel],
                        "duracion": duracion, "completado": False, "ts": _now_ts(),
                    }
                    blocks = pd.concat([pd.DataFrame([new_block]), blocks], ignore_index=True)
                    _save_df("plan_blocks", blocks)
                    st.session_state["plan_adding"] = False
                    st.rerun()
            if cancelled:
                st.session_state["plan_adding"] = False
                st.rerun()

    st.divider()

    # Display hourly timeline
    if today_blocks.empty:
        st.info("No hay bloques planificados para hoy. Agrega uno con '+ Bloque'.")
        return

    current_hour = datetime.now().strftime("%H:00")

    for _, b in today_blocks.iterrows():
        hora = b["hora"]
        is_now = hora == current_hour
        done = b["completado"]

        with st.container(border=True):
            col_time, col_info, col_actions = st.columns([1.5, 4, 1.5])
            with col_time:
                if is_now:
                    st.markdown(f"🔵 **:orange[{hora}]**")
                else:
                    st.markdown(f"**{hora}**")
                st.caption(f"{b['duracion']} min")
            with col_info:
                style = "~~" if done else ""
                st.markdown(f"{style}{b['titulo']}{style}")
                if b["tarea_id"] and not tareas.empty:
                    task_match = tareas[tareas["id"] == b["tarea_id"]]
                    if not task_match.empty:
                        t = task_match.iloc[0]
                        if t.get("proyecto") and not proyectos.empty:
                            pm = proyectos[proyectos["id"] == t["proyecto"]]
                            if not pm.empty:
                                st.caption(f"📂 {pm.iloc[0]['nombre']}")
            with col_actions:
                if not done:
                    if st.button("✅", key=f"plan_done_{b['id']}", use_container_width=True, help="Completar"):
                        blocks.loc[blocks["id"] == b["id"], "completado"] = True
                        if b["tarea_id"] and not tareas.empty:
                            tareas.loc[tareas["id"] == b["tarea_id"], "done"] = True
                            _save_df("tareas", tareas)
                        _save_df("plan_blocks", blocks)
                        st.rerun()
                else:
                    st.markdown("✅")
                if st.button("🗑️", key=f"plan_del_{b['id']}", use_container_width=True, help="Eliminar"):
                    blocks = blocks[blocks["id"] != b["id"]]
                    _save_df("plan_blocks", blocks)
                    st.rerun()


def _render_focus_mode():
    """Focus mode: show only the current task with integrated Pomodoro timer."""
    from core.data import get_df as _get_df, save_df as _save_df, uid as _uid, now_ts as _now_ts

    today = datetime.now().strftime("%Y-%m-%d")
    tareas = _get_df("tareas")
    proyectos = _get_df("proyectos")

    if tareas.empty:
        st.info("No hay tareas pendientes.")
        return

    # Get prioritized pending tasks
    pending = tareas[(~tareas["done"]) & ((tareas["fecha"] == today) | ((tareas["fecha"] != "") & (tareas["fecha"] <= today)))].copy()
    if pending.empty:
        pending = tareas[~tareas["done"]].copy()
    if pending.empty:
        st.success("Todas las tareas completadas. Buen trabajo!")
        return

    pri_order = {"alta": 0, "media": 1, "baja": 2}
    pending["_pri"] = pending["prioridad"].map(pri_order).fillna(2)
    pending = pending.sort_values("_pri")

    # Task selector
    task_options = []
    for _, t in pending.iterrows():
        pri = {"alta": "🔴", "media": "🟡", "baja": "🟢"}.get(t["prioridad"], "")
        task_options.append(f"{pri} {t['titulo']}")

    focus_idx = st.selectbox("Tarea actual", range(len(task_options)),
                              format_func=lambda i: task_options[i],
                              key="focus_task_sel", label_visibility="collapsed")

    task = pending.iloc[focus_idx]
    task_id = task["id"]

    st.divider()

    # Big task display
    pri_emoji = {"alta": "🔴", "media": "🟡", "baja": "🟢"}.get(task["prioridad"], "")
    st.markdown(f"## {pri_emoji} {task['titulo']}")

    # Project info
    if task.get("proyecto") and not proyectos.empty:
        pm = proyectos[proyectos["id"] == task["proyecto"]]
        if not pm.empty:
            st.caption(f"📂 {pm.iloc[0].get('emoji', '📁')} {pm.iloc[0]['nombre']}")

    if task.get("fecha"):
        st.caption(f"📅 Fecha limite: {task['fecha']}")

    if task.get("notas"):
        st.markdown(task["notas"])

    # Subtasks
    subs = _parse_subtareas(task.get("subtareas", ""))
    if subs:
        st.markdown("**Subtareas:**")
        updated = False
        for i, sub in enumerate(subs):
            done = sub.get("done", False)
            new_done = st.checkbox(sub["text"], value=done, key=f"focus_sub_{task_id}_{i}")
            if new_done != done:
                subs[i]["done"] = new_done
                updated = True
        if updated:
            tareas.loc[tareas["id"] == task_id, "subtareas"] = json.dumps(subs, ensure_ascii=False)
            _save_df("tareas", tareas)
            st.rerun()

    st.divider()

    # Pomodoro timer
    st.subheader("🍅 Pomodoro")

    if "focus_timer_start" not in st.session_state:
        st.session_state["focus_timer_start"] = None
    if "focus_timer_mins" not in st.session_state:
        st.session_state["focus_timer_mins"] = 25

    col_dur, col_start = st.columns(2)
    with col_dur:
        mins = st.selectbox("Duracion", [15, 25, 30, 45, 60], index=1,
                            format_func=lambda x: f"{x} min", key="focus_pomo_dur")
        st.session_state["focus_timer_mins"] = mins
    with col_start:
        if st.session_state["focus_timer_start"] is None:
            if st.button("▶️ Iniciar", use_container_width=True, type="primary"):
                import time
                st.session_state["focus_timer_start"] = time.time()
                st.rerun()
        else:
            import time
            elapsed = time.time() - st.session_state["focus_timer_start"]
            remaining = max(0, st.session_state["focus_timer_mins"] * 60 - elapsed)
            mins_left = int(remaining // 60)
            secs_left = int(remaining % 60)

            if remaining <= 0:
                st.success("🎉 Tiempo completado!")
                # Save pomodoro session
                pomo = _get_df("pomo_sessions")
                new_session = {
                    "id": _uid(), "tarea": task["titulo"],
                    "minutos": st.session_state["focus_timer_mins"],
                    "fecha": today, "ts": _now_ts(),
                }
                pomo = pd.concat([pd.DataFrame([new_session]), pomo], ignore_index=True)
                _save_df("pomo_sessions", pomo)
                if st.button("Reiniciar", use_container_width=True):
                    st.session_state["focus_timer_start"] = None
                    st.rerun()
            else:
                st.metric("Tiempo restante", f"{mins_left:02d}:{secs_left:02d}")
                pct = 1 - (remaining / (st.session_state["focus_timer_mins"] * 60))
                st.progress(pct)
                if st.button("⏹️ Detener", use_container_width=True):
                    st.session_state["focus_timer_start"] = None
                    st.rerun()

    st.divider()

    # Complete task button
    if st.button("✅ Completar tarea", use_container_width=True, type="primary"):
        import time as _time
        tareas.loc[tareas["id"] == task_id, "done"] = True
        _save_df("tareas", tareas)
        st.session_state["undo_action"] = {"tipo": "task_done", "id": task_id, "msg": f"Tarea completada: {task['titulo']}", "ts": _time.time()}
        st.session_state["focus_timer_start"] = None
        st.rerun()

    # Skip to next
    if len(pending) > 1:
        if st.button("⏭️ Siguiente tarea", use_container_width=True):
            next_idx = (focus_idx + 1) % len(pending)
            st.session_state["focus_task_sel"] = next_idx
            st.session_state["focus_timer_start"] = None
            st.rerun()
