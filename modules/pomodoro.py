import streamlit as st
import pandas as pd
import time as time_module
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREA_LABELS, fmt
from core.utils import PRIORITY_EMOJIS


def render():
    st.header("Pomodoro")
    st.caption("Temporizador de enfoque para tus tareas")

    # Settings
    if "pomo_work" not in st.session_state:
        st.session_state["pomo_work"] = 25
    if "pomo_break" not in st.session_state:
        st.session_state["pomo_break"] = 5
    if "pomo_running" not in st.session_state:
        st.session_state["pomo_running"] = False
    if "pomo_end_time" not in st.session_state:
        st.session_state["pomo_end_time"] = 0
    if "pomo_mode" not in st.session_state:
        st.session_state["pomo_mode"] = "work"
    if "pomo_count" not in st.session_state:
        st.session_state["pomo_count"] = 0

    # --- Select task ---
    tareas = get_df("tareas")
    pending = tareas[~tareas["done"]] if not tareas.empty else tareas

    st.subheader("Selecciona una tarea")
    if not pending.empty:
        task_options = ["Ninguna (enfoque libre)"] + pending["titulo"].tolist()
        selected_task = st.selectbox("Tarea", task_options, label_visibility="collapsed")
    else:
        selected_task = "Ninguna (enfoque libre)"
        st.info("No hay tareas pendientes.")

    st.divider()

    # --- Timer settings ---
    col_work, col_break = st.columns(2)
    with col_work:
        work_min = st.number_input("Minutos de trabajo", min_value=1, max_value=90, value=st.session_state["pomo_work"], step=5)
        st.session_state["pomo_work"] = work_min
    with col_break:
        break_min = st.number_input("Minutos de descanso", min_value=1, max_value=30, value=st.session_state["pomo_break"], step=1)
        st.session_state["pomo_break"] = break_min

    st.divider()

    # --- Timer display ---
    if st.session_state["pomo_running"]:
        remaining = st.session_state["pomo_end_time"] - time_module.time()
        if remaining <= 0:
            st.session_state["pomo_running"] = False
            if st.session_state["pomo_mode"] == "work":
                st.session_state["pomo_count"] += 1
                st.session_state["pomo_mode"] = "break"
                st.balloons()
                st.success(f"Pomodoro #{st.session_state['pomo_count']} completado! Toma un descanso.")
                # Save session persistently
                _save_pomo_session(selected_task, work_min)
            else:
                st.session_state["pomo_mode"] = "work"
                st.info("Descanso terminado. Listo para otro pomodoro?")
        else:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            mode_label = "Trabajando" if st.session_state["pomo_mode"] == "work" else "Descanso"
            mode_color = "red" if st.session_state["pomo_mode"] == "work" else "green"

            st.markdown(f"### {mode_label}")
            st.markdown(f"# :{mode_color}[{mins:02d}:{secs:02d}]")

            if selected_task != "Ninguna (enfoque libre)":
                st.caption(f"Enfocado en: **{selected_task}**")

            if st.button("Detener", type="primary", use_container_width=True):
                st.session_state["pomo_running"] = False
                st.rerun()

            time_module.sleep(1)
            st.rerun()
    else:
        mode = st.session_state["pomo_mode"]
        duration = work_min if mode == "work" else break_min
        label = "Iniciar trabajo" if mode == "work" else "Iniciar descanso"

        st.markdown(f"### {label} ({duration} min)")

        if st.button(label, type="primary", use_container_width=True):
            st.session_state["pomo_running"] = True
            st.session_state["pomo_end_time"] = time_module.time() + (duration * 60)
            st.rerun()

    st.divider()

    # --- Session stats (today) ---
    st.subheader("Sesion de hoy")
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("Pomodoros", f"{st.session_state['pomo_count']}")
    col_s2.metric("Minutos enfocado", f"{st.session_state['pomo_count'] * work_min}")
    col_s3.metric("Modo actual", "Trabajo" if st.session_state["pomo_mode"] == "work" else "Descanso")

    st.divider()

    # --- Persistent history ---
    st.subheader("Historial de enfoque")
    pomo_sessions = get_df("pomo_sessions")

    if pomo_sessions.empty:
        st.info("No hay sesiones guardadas aun. Completa un pomodoro para empezar el historial.")
        return

    # Stats
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_sessions = pomo_sessions[pomo_sessions["fecha"] == today_str]
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_sessions = pomo_sessions[pomo_sessions["fecha"] >= week_ago]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hoy", f"{len(today_sessions)} ses.")
    c2.metric("Min hoy", f"{int(today_sessions['minutos'].sum())}" if not today_sessions.empty else "0")
    c3.metric("Esta semana", f"{len(week_sessions)} ses.")
    c4.metric("Min semana", f"{int(week_sessions['minutos'].sum())}" if not week_sessions.empty else "0")

    # Chart: last 7 days
    st.subheader("Enfoque (7 dias)")
    days_data = []
    for d in range(6, -1, -1):
        day = datetime.now() - timedelta(days=d)
        ds = day.strftime("%Y-%m-%d")
        day_label = day.strftime("%a")
        day_sessions = pomo_sessions[pomo_sessions["fecha"] == ds]
        total_min = int(day_sessions["minutos"].sum()) if not day_sessions.empty else 0
        days_data.append({"Dia": day_label, "Minutos": total_min})

    chart_df = pd.DataFrame(days_data)
    st.bar_chart(chart_df.set_index("Dia"), color=["#c96a6a"])

    # --- Time per task ---
    st.subheader("Tiempo por tarea")
    task_sessions = pomo_sessions[pomo_sessions["tarea"] != ""]
    if not task_sessions.empty:
        task_time = task_sessions.groupby("tarea")["minutos"].agg(["sum", "count"]).reset_index()
        task_time.columns = ["Tarea", "Minutos", "Sesiones"]
        task_time = task_time.sort_values("Minutos", ascending=False)

        for _, row in task_time.head(10).iterrows():
            hours = row["Minutos"] / 60
            with st.container(border=True):
                ct1, ct2, ct3 = st.columns([4, 1, 1])
                ct1.markdown(f"**{row['Tarea']}**")
                ct2.metric("Tiempo", f"{hours:.1f}h", label_visibility="collapsed")
                ct3.caption(f"{int(row['Sesiones'])} ses. | {int(row['Minutos'])} min")
    else:
        st.caption("Selecciona una tarea al iniciar un pomodoro para ver el tiempo por tarea.")

    # Recent sessions table
    with st.expander("Sesiones recientes"):
        recent = pomo_sessions.sort_values("ts", ascending=False).head(20)
        for _, s in recent.iterrows():
            tarea_label = s["tarea"] if s["tarea"] else "Enfoque libre"
            st.caption(f"{s['fecha']} | {s['minutos']} min | {tarea_label}")


def _save_pomo_session(task_name, minutes):
    """Save a completed Pomodoro session to persistent storage."""
    sessions = get_df("pomo_sessions")
    new_session = {
        "id": uid(),
        "tarea": task_name if task_name != "Ninguna (enfoque libre)" else "",
        "minutos": minutes,
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "ts": now_ts(),
    }
    sessions = pd.concat([pd.DataFrame([new_session]), sessions], ignore_index=True)
    save_df("pomo_sessions", sessions)
