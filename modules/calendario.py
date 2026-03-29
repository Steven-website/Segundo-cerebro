import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df
from core.constants import AREA_LABELS
from core.utils import parse_checks, PRIORITY_EMOJIS


def render():
    st.header("\U0001f4c5 Calendario")

    tareas = get_df("tareas")
    habitos = get_df("habitos")

    # --- Month navigation ---
    if "cal_offset" not in st.session_state:
        st.session_state["cal_offset"] = 0

    col_prev, col_title, col_next = st.columns([1, 4, 1])
    with col_prev:
        if st.button("\u25c0 Anterior"):
            st.session_state["cal_offset"] -= 1
            st.rerun()
    with col_next:
        if st.button("Siguiente \u25b6"):
            st.session_state["cal_offset"] += 1
            st.rerun()

    today = datetime.now()
    target_month = today.month + st.session_state["cal_offset"]
    target_year = today.year
    while target_month <= 0:
        target_month += 12
        target_year -= 1
    while target_month > 12:
        target_month -= 12
        target_year += 1

    MONTH_NAMES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    with col_title:
        st.subheader(f"{MONTH_NAMES[target_month]} {target_year}")

    # --- Build calendar data ---
    first_day = datetime(target_year, target_month, 1)
    if target_month == 12:
        last_day = datetime(target_year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(target_year, target_month + 1, 1) - timedelta(days=1)

    # Get tasks with dates in this month
    prefix = f"{target_year}-{target_month:02d}"
    tasks_this_month = {}
    if not tareas.empty:
        month_tasks = tareas[tareas["fecha"].str.startswith(prefix)]
        for _, t in month_tasks.iterrows():
            day = t["fecha"]
            if day not in tasks_this_month:
                tasks_this_month[day] = []
            tasks_this_month[day].append(t)

    # Get habits checks for this month
    habits_this_month = {}
    if not habitos.empty:
        for _, h in habitos.iterrows():
            checks = parse_checks(h.get("checks", "{}"))
            for ds, done in checks.items():
                if ds.startswith(prefix) and done:
                    if ds not in habits_this_month:
                        habits_this_month[ds] = 0
                    habits_this_month[ds] += 1

    # --- Render calendar grid ---
    st.markdown("---")
    day_headers = st.columns(7)
    day_names = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    for i, name in enumerate(day_names):
        day_headers[i].markdown(f"**{name}**")

    # Fill in days
    start_weekday = first_day.weekday()  # 0=Monday
    total_days = last_day.day
    today_str = today.strftime("%Y-%m-%d")

    day_num = 1
    for week in range(6):
        if day_num > total_days:
            break
        cols = st.columns(7)
        for weekday in range(7):
            with cols[weekday]:
                if week == 0 and weekday < start_weekday:
                    st.markdown("")
                elif day_num <= total_days:
                    ds = f"{target_year}-{target_month:02d}-{day_num:02d}"
                    is_today = ds == today_str

                    # Day header
                    if is_today:
                        st.markdown(f"**:orange[{day_num}]**")
                    else:
                        st.markdown(f"**{day_num}**")

                    # Tasks for this day
                    if ds in tasks_this_month:
                        for t in tasks_this_month[ds][:2]:
                            pri = PRIORITY_EMOJIS.get(t["prioridad"], "\u26aa")
                            done = "\u0336" if t["done"] else ""
                            title = t["titulo"][:15]
                            st.caption(f"{pri} {title}")

                    # Habits for this day
                    if ds in habits_this_month:
                        count = habits_this_month[ds]
                        st.caption(f"\u2705 {count} hab.")

                    day_num += 1

    st.divider()

    # --- Today's summary ---
    st.subheader("Hoy")
    today_ds = today.strftime("%Y-%m-%d")

    col_tasks, col_habits = st.columns(2)
    with col_tasks:
        st.markdown("**Tareas para hoy:**")
        if today_ds in tasks_this_month:
            for t in tasks_this_month[today_ds]:
                pri = PRIORITY_EMOJIS.get(t["prioridad"], "\u26aa")
                status = "\u2705" if t["done"] else "\u2b1c"
                st.markdown(f"{status} {pri} {t['titulo']}")
        else:
            st.caption("Sin tareas para hoy.")

    with col_habits:
        st.markdown("**Habitos de hoy:**")
        if not habitos.empty:
            for _, h in habitos.iterrows():
                checks = parse_checks(h.get("checks", "{}"))
                done = checks.get(today_ds, False)
                emoji = h.get("emoji", "\u2b50")
                status = "\u2705" if done else "\u2b1c"
                st.markdown(f"{status} {emoji} {h['name']}")
        else:
            st.caption("Sin habitos configurados.")
