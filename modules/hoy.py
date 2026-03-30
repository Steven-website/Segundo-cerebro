import streamlit as st
import json
from datetime import datetime
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
    st.caption("Todo lo que tienes pendiente para hoy")

    _check_undo()

    today = datetime.now().strftime("%Y-%m-%d")
    tareas = get_df("tareas")
    proyectos = get_df("proyectos")

    if tareas.empty:
        st.info("No hay tareas. Crea un proyecto y agrega tareas para verlas aqui.")
        return

    # === TASKS DUE TODAY OR OVERDUE ===
    pending_tasks = tareas[~tareas["done"]].copy()

    # Tasks with fecha <= today (due today or overdue)
    tasks_today = pending_tasks[
        (pending_tasks["fecha"] != "") &
        (pending_tasks["fecha"] <= today)
    ].copy()

    # Tasks without date (always show)
    tasks_no_date = pending_tasks[pending_tasks["fecha"] == ""].copy()

    # === SUBTASKS DUE TODAY OR OVERDUE ===
    subtask_items = []
    for _, t in pending_tasks.iterrows():
        subs = _parse_subtareas(t.get("subtareas", ""))
        for i, sub in enumerate(subs):
            if sub.get("done"):
                continue
            sub_fecha = sub.get("fecha", "")
            if sub_fecha and sub_fecha <= today:
                # Get project name
                proj_name = ""
                if t.get("proyecto") and not proyectos.empty:
                    proj_match = proyectos[proyectos["id"] == t["proyecto"]]
                    if not proj_match.empty:
                        proj_name = proj_match.iloc[0]["nombre"]

                subtask_items.append({
                    "tarea_id": t["id"],
                    "tarea_titulo": t["titulo"],
                    "proyecto": proj_name,
                    "sub_index": i,
                    "sub_text": sub["text"],
                    "sub_fecha": sub_fecha,
                    "overdue": sub_fecha < today,
                })

    # === DISPLAY ===
    total_items = len(tasks_today) + len(subtask_items)

    # Metrics
    c1, c2, c3 = st.columns(3)
    overdue_tasks = tasks_today[tasks_today["fecha"] < today] if not tasks_today.empty else pd.DataFrame()
    overdue_subs = [s for s in subtask_items if s["overdue"]]
    c1.metric("Pendientes hoy", total_items)
    c2.metric("Tareas atrasadas", len(overdue_tasks) if not tasks_today.empty else 0)
    c3.metric("Subtareas atrasadas", len(overdue_subs))

    st.divider()

    # --- Overdue section ---
    all_overdue_tasks = tasks_today[tasks_today["fecha"] < today] if not tasks_today.empty else None
    if (all_overdue_tasks is not None and not all_overdue_tasks.empty) or overdue_subs:
        st.subheader("🔴 Atrasadas")
        st.caption("Estas tareas ya pasaron su fecha limite")

        if all_overdue_tasks is not None and not all_overdue_tasks.empty:
            for _, t in all_overdue_tasks.iterrows():
                _render_today_task(t, tareas, proyectos, overdue=True)

        for sub in overdue_subs:
            _render_today_subtask(sub, tareas)

        st.divider()

    # --- Due today section ---
    st.subheader("📋 Para hoy")

    due_exactly_today_tasks = tasks_today[tasks_today["fecha"] == today] if not tasks_today.empty else None
    today_subs = [s for s in subtask_items if not s["overdue"]]

    if (due_exactly_today_tasks is None or due_exactly_today_tasks.empty) and not today_subs:
        st.success("No hay pendientes para hoy. Buen trabajo!")
    else:
        if due_exactly_today_tasks is not None and not due_exactly_today_tasks.empty:
            for _, t in due_exactly_today_tasks.iterrows():
                _render_today_task(t, tareas, proyectos, overdue=False)

        for sub in today_subs:
            _render_today_subtask(sub, tareas)

    # --- Tasks without date ---
    if not tasks_no_date.empty:
        st.divider()
        with st.expander(f"📌 Sin fecha asignada ({len(tasks_no_date)})"):
            for _, t in tasks_no_date.iterrows():
                _render_today_task(t, tareas, proyectos, overdue=False)

    # ═══ HABITOS DE HOY ═══
    st.divider()
    _render_today_habits()


import pandas as pd


def _render_today_habits():
    """Show today's habits with toggle."""
    from core.data import get_df as _get_df, save_df as _save_df
    from core.utils import parse_checks
    from core.constants import HABIT_FREQ
    import json as _json

    habitos = _get_df("habitos")
    if habitos.empty:
        return

    # Filter by frequency
    dow = datetime.now().weekday()
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_habs = []
    for _, h in habitos.iterrows():
        freq = h.get("freq", "diario")
        if freq == "laborables" and dow >= 5:
            continue
        if freq == "fines" and dow < 5:
            continue
        today_habs.append(h)

    if not today_habs:
        return

    done_count = 0
    for h in today_habs:
        checks = parse_checks(h.get("checks", "{}"))
        if checks.get(today_str, False):
            done_count += 1

    st.subheader(f"Habitos de hoy ({done_count}/{len(today_habs)})")

    for h in today_habs:
        checks = parse_checks(h.get("checks", "{}"))
        done_today = checks.get(today_str, False)
        emoji = h.get("emoji", "⭐")

        with st.container(border=True):
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
