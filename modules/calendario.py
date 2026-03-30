import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREA_LABELS, PRIORITY_LABELS
from core.utils import parse_checks, PRIORITY_EMOJIS


def render():
    st.header("\U0001f4c5 Calendario")

    tareas = get_df("tareas")
    habitos = get_df("habitos")
    proyectos = get_df("proyectos")

    # --- View toggle ---
    col_view, _ = st.columns([1, 5])
    with col_view:
        cal_view = st.selectbox("Vista", ["Mensual", "Semanal"], key="cal_view_mode", label_visibility="collapsed")

    if cal_view == "Semanal":
        _render_weekly(tareas, habitos, proyectos)
        return

    # --- Month navigation ---
    if "cal_offset" not in st.session_state:
        st.session_state["cal_offset"] = 0

    col_prev, col_title, col_next, col_today = st.columns([1, 3, 1, 1])
    with col_prev:
        if st.button("\u25c0 Anterior"):
            st.session_state["cal_offset"] -= 1
            st.rerun()
    with col_next:
        if st.button("Siguiente \u25b6"):
            st.session_state["cal_offset"] += 1
            st.rerun()
    with col_today:
        if st.button("Hoy"):
            st.session_state["cal_offset"] = 0
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

    # --- Month summary ---
    total_tasks_month = sum(len(v) for v in tasks_this_month.values())
    total_done_month = sum(1 for tasks in tasks_this_month.values() for t in tasks if t["done"])
    total_habit_days = sum(habits_this_month.values())

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Tareas del mes", total_tasks_month, help=f"{total_done_month} completadas")
    sc2.metric("Dias con habitos", len(habits_this_month))
    sc3.metric("Habitos cumplidos", total_habit_days)

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
                            title = t["titulo"][:12]
                            if t["done"]:
                                st.caption(f"~~{pri} {title}~~")
                            else:
                                st.caption(f"{pri} {title}")
                        if len(tasks_this_month[ds]) > 2:
                            st.caption(f"+{len(tasks_this_month[ds]) - 2} mas")

                    # Habits for this day
                    if ds in habits_this_month:
                        count = habits_this_month[ds]
                        st.caption(f"\u2705 {count} hab.")

                    day_num += 1

    st.divider()

    # --- Quick add task from calendar ---
    st.subheader("Agregar tarea rapida")
    with st.form("cal_quick_task", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        titulo = c1.text_input("Tarea", placeholder="Nombre de la tarea")
        fecha = c2.date_input("Fecha", value=today)

        c3, c4, c5 = st.columns(3)
        pri_opts = ["alta", "media", "baja"]
        prioridad = c3.selectbox("Prioridad", pri_opts, index=1,
                                  format_func=lambda x: PRIORITY_LABELS.get(x, x))

        # Project selector
        proj_options = ["Sin proyecto"]
        proj_ids = [""]
        if not proyectos.empty:
            for _, p in proyectos.iterrows():
                proj_emoji = p.get("emoji", "📁")
                proj_options.append(f"{proj_emoji} {p['nombre']}")
                proj_ids.append(p["id"])
        proj_idx = c4.selectbox("Proyecto", range(len(proj_options)),
                                format_func=lambda i: proj_options[i])

        area_ids = ["trabajo", "personal", "proyectos", "ideas"]
        area = c5.selectbox("Area", area_ids,
                            format_func=lambda x: AREA_LABELS.get(x, x))

        if st.form_submit_button("Agregar tarea", type="primary"):
            if titulo.strip():
                new_task = {
                    "id": uid(), "titulo": titulo.strip(), "area": area,
                    "prioridad": prioridad,
                    "fecha_inicio": "",
                    "fecha": str(fecha),
                    "proyecto": proj_ids[proj_idx],
                    "notas": "", "subtareas": "",
                    "recurrente": "", "depende_de": "", "etiqueta": "",
                    "done": False, "pinned": False, "archived": False,
                    "ts": now_ts(),
                }
                tareas = pd.concat([pd.DataFrame([new_task]), tareas], ignore_index=True)
                save_df("tareas", tareas)
                st.success(f"Tarea '{titulo.strip()}' agregada para {fecha}")
                st.rerun()

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


def _render_weekly(tareas, habitos, proyectos):
    """Render a weekly calendar view with detailed daily breakdown."""
    if "week_offset" not in st.session_state:
        st.session_state["week_offset"] = 0

    today = datetime.now()
    # Calculate Monday of current week + offset
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=st.session_state["week_offset"])
    sunday = monday + timedelta(days=6)

    col_prev, col_title, col_next, col_today = st.columns([1, 3, 1, 1])
    with col_prev:
        if st.button("\u25c0 Anterior", key="week_prev"):
            st.session_state["week_offset"] -= 1
            st.rerun()
    with col_title:
        st.subheader(f"{monday.strftime('%d/%m')} — {sunday.strftime('%d/%m/%Y')}")
    with col_next:
        if st.button("Siguiente \u25b6", key="week_next"):
            st.session_state["week_offset"] += 1
            st.rerun()
    with col_today:
        if st.button("Esta semana", key="week_today"):
            st.session_state["week_offset"] = 0
            st.rerun()

    # Weekly summary
    week_dates = [monday + timedelta(days=i) for i in range(7)]
    week_strs = [d.strftime("%Y-%m-%d") for d in week_dates]
    today_str = today.strftime("%Y-%m-%d")

    total_tasks = 0
    total_done = 0
    total_habits = 0
    if not tareas.empty:
        for ds in week_strs:
            day_tasks = tareas[tareas["fecha"] == ds]
            total_tasks += len(day_tasks)
            total_done += int(day_tasks["done"].sum()) if not day_tasks.empty else 0

    if not habitos.empty:
        for ds in week_strs:
            for _, h in habitos.iterrows():
                checks = parse_checks(h.get("checks", "{}"))
                if checks.get(ds, False):
                    total_habits += 1

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Tareas de la semana", total_tasks, help=f"{total_done} completadas")
    sc2.metric("Completadas", total_done)
    sc3.metric("Habitos cumplidos", total_habits)

    st.divider()

    # Render each day
    day_names = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    for i, (day_date, ds) in enumerate(zip(week_dates, week_strs)):
        is_today = ds == today_str
        day_name = day_names[i]
        day_num = day_date.strftime("%d/%m")

        header = f"{'**:orange[' if is_today else ''}{day_name} {day_num}{']**' if is_today else ''}"
        if not is_today:
            header = f"**{day_name} {day_num}**"

        with st.expander(header, expanded=is_today):
            # Tasks for this day
            day_tasks = tareas[tareas["fecha"] == ds] if not tareas.empty else pd.DataFrame()
            overdue_tasks = tareas[(~tareas["done"]) & (tareas["fecha"] != "") & (tareas["fecha"] < ds) & (tareas["fecha"] >= monday.strftime("%Y-%m-%d"))] if not tareas.empty and ds == today_str else pd.DataFrame()

            if not day_tasks.empty or (not overdue_tasks.empty and ds == today_str):
                st.markdown("**Tareas:**")
                for _, t in day_tasks.iterrows():
                    pri = PRIORITY_EMOJIS.get(t["prioridad"], "\u26aa")
                    status = "\u2705" if t["done"] else "\u2b1c"
                    proj_name = ""
                    if t.get("proyecto") and not proyectos.empty:
                        proj_match = proyectos[proyectos["id"] == t["proyecto"]]
                        if not proj_match.empty:
                            proj_name = f" — 📂 {proj_match.iloc[0]['nombre']}"
                    style = "~~" if t["done"] else ""
                    st.markdown(f"{status} {pri} {style}{t['titulo']}{style}{proj_name}")
            else:
                st.caption("Sin tareas")

            # Habits for this day
            if not habitos.empty:
                dow = day_date.weekday()
                day_habs = []
                for _, h in habitos.iterrows():
                    freq = h.get("freq", "diario")
                    if freq == "laborables" and dow >= 5:
                        continue
                    if freq == "fines" and dow < 5:
                        continue
                    day_habs.append(h)

                if day_habs:
                    st.markdown("**Habitos:**")
                    for h in day_habs:
                        checks = parse_checks(h.get("checks", "{}"))
                        done = checks.get(ds, False)
                        emoji = h.get("emoji", "\u2b50")
                        status = "\u2705" if done else "\u2b1c"
                        st.markdown(f"{status} {emoji} {h['name']}")
