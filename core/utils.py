import json
import pandas as pd
import streamlit as st
from datetime import datetime
from core.constants import AREAS


def parse_checks(data):
    if isinstance(data, dict):
        return data
    if isinstance(data, str) and data:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def is_done_today(habit):
    today_str = datetime.now().strftime("%Y-%m-%d")
    checks = parse_checks(habit.get("checks", "{}"))
    reps = [r.strip() for r in habit.get("repeticiones", "").split(",") if r.strip()]
    val = checks.get(today_str, False)
    if isinstance(val, dict):
        if reps:
            return all(val.get(r, False) for r in reps)
        return all(val.values()) if val else False
    if reps and not isinstance(val, dict):
        # Has sub-checks but stored as bool — not truly complete
        return False
    return val


def get_day_completion(habit, date_str):
    """Return (done_count, total_count) for a day. Supports sub-checks."""
    checks = parse_checks(habit.get("checks", "{}"))
    reps = [r.strip() for r in habit.get("repeticiones", "").split(",") if r.strip()]
    val = checks.get(date_str, False)
    if reps:
        if isinstance(val, dict):
            done = sum(1 for r in reps if val.get(r, False))
            return done, len(reps)
        elif val is True:
            return len(reps), len(reps)
        return 0, len(reps)
    return (1 if val else 0), 1


def get_area_id(label):
    area = next((a for a in AREAS if f'{a["emoji"]} {a["name"]}' == label), None)
    return area["id"] if area else None


PRIORITY_EMOJIS = {
    "alta": "\U0001f534",
    "media": "\U0001f7e1",
    "baja": "\U0001f7e2",
}


def confirm_delete(item_id, item_name, key_prefix):
    confirm_key = f"{key_prefix}_confirm_{item_id}"
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False

    if not st.session_state[confirm_key]:
        if st.button("\U0001f5d1", key=f"{key_prefix}_del_{item_id}"):
            st.session_state[confirm_key] = True
            st.rerun()
        return False
    else:
        st.warning(f"Eliminar **{item_name}**?")
        c1, c2 = st.columns(2)
        if c1.button("\u2705 Si, eliminar", key=f"{key_prefix}_yes_{item_id}", type="primary"):
            st.session_state[confirm_key] = False
            return True
        if c2.button("\u274c Cancelar", key=f"{key_prefix}_no_{item_id}"):
            st.session_state[confirm_key] = False
            st.rerun()
        return False


def export_csv(df, filename, label="Exportar CSV"):
    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(label, csv, filename, "text/csv", use_container_width=True)


def soft_delete(item, tipo, nombre):
    """Move an item to papelera instead of permanent delete."""
    from core.data import get_df, save_df, uid, now_ts
    papelera = get_df("papelera")
    new_row = {
        "id": uid(),
        "tipo": tipo,
        "nombre": nombre,
        "data": json.dumps(item if isinstance(item, dict) else item.to_dict(), ensure_ascii=False, default=str),
        "deleted_ts": now_ts(),
    }
    papelera = pd.concat([pd.DataFrame([new_row]), papelera], ignore_index=True)
    save_df("papelera", papelera)


def cascade_delete_project(project_id):
    """Delete a project and all its tasks, comments, sending everything to papelera."""
    from core.data import get_df, save_df
    tareas = get_df("tareas")
    comments = get_df("task_comments")

    # Move project tasks and their comments to trash
    proj_tasks = tareas[tareas["proyecto"] == project_id] if not tareas.empty else pd.DataFrame()
    for _, t in proj_tasks.iterrows():
        # Trash comments for this task
        task_comments = comments[comments["tarea_id"] == t["id"]] if not comments.empty else pd.DataFrame()
        for _, c in task_comments.iterrows():
            soft_delete(c, "comentario", f"Comentario en {t['titulo']}")
        comments = comments[comments["tarea_id"] != t["id"]]
        # Trash the task
        soft_delete(t, "tarea", t["titulo"])

    tareas = tareas[tareas["proyecto"] != project_id]
    save_df("tareas", tareas)
    save_df("task_comments", comments)
