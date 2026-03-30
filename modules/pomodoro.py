import streamlit as st
import time as time_module
from core.data import get_df
from core.constants import AREA_LABELS
from core.utils import PRIORITY_EMOJIS


def render():
    st.header("\U0001f345 Pomodoro")
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
            # Timer finished
            st.session_state["pomo_running"] = False
            if st.session_state["pomo_mode"] == "work":
                st.session_state["pomo_count"] += 1
                st.session_state["pomo_mode"] = "break"
                st.balloons()
                st.success(f"\U0001f389 Pomodoro #{st.session_state['pomo_count']} completado! Toma un descanso.")
            else:
                st.session_state["pomo_mode"] = "work"
                st.info("\u2615 Descanso terminado. Listo para otro pomodoro?")
        else:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            mode_label = "\U0001f4aa Trabajando" if st.session_state["pomo_mode"] == "work" else "\u2615 Descanso"
            mode_color = "red" if st.session_state["pomo_mode"] == "work" else "green"

            st.markdown(f"### {mode_label}")
            st.markdown(f"# :{mode_color}[{mins:02d}:{secs:02d}]")

            if selected_task != "Ninguna (enfoque libre)":
                st.caption(f"\U0001f3af Enfocado en: **{selected_task}**")

            if st.button("\u23f9 Detener", type="primary", use_container_width=True):
                st.session_state["pomo_running"] = False
                st.rerun()

            # Auto-refresh every second
            time_module.sleep(1)
            st.rerun()
    else:
        # Not running
        mode = st.session_state["pomo_mode"]
        duration = work_min if mode == "work" else break_min
        label = "Iniciar trabajo" if mode == "work" else "Iniciar descanso"
        icon = "\U0001f680" if mode == "work" else "\u2615"

        st.markdown(f"### {icon} {label} ({duration} min)")

        if st.button(f"{icon} {label}", type="primary", use_container_width=True):
            st.session_state["pomo_running"] = True
            st.session_state["pomo_end_time"] = time_module.time() + (duration * 60)
            st.rerun()

    st.divider()

    # --- Stats ---
    st.subheader("Sesion de hoy")
    col_s1, col_s2, col_s3 = st.columns(3)
    col_s1.metric("Pomodoros", f"\U0001f345 {st.session_state['pomo_count']}")
    col_s2.metric("Minutos enfocado", f"{st.session_state['pomo_count'] * work_min}")
    col_s3.metric("Modo actual", "Trabajo" if st.session_state["pomo_mode"] == "work" else "Descanso")
