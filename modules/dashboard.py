import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df
from core.constants import AREA_LABELS, fmt, HABIT_FREQ
from core.utils import is_done_today, parse_checks, PRIORITY_EMOJIS


def _get_today_habits(habitos_df):
    if habitos_df.empty:
        return habitos_df
    dow = datetime.now().weekday()
    mask = []
    for _, h in habitos_df.iterrows():
        freq = h.get("freq", "diario")
        if freq == "laborables":
            mask.append(dow < 5)
        elif freq == "fines":
            mask.append(dow >= 5)
        else:
            mask.append(True)
    return habitos_df[mask]


def _get_month_finance(txs_df, year=None, month=None):
    if txs_df.empty:
        return 0.0, 0.0
    now = datetime.now()
    y = year or now.year
    m = month or now.month
    prefix = f"{y}-{m:02d}"
    month_txs = txs_df[txs_df["fecha"].str.startswith(prefix)]
    ingresos = float(month_txs[month_txs["type"] == "ingreso"]["amt"].sum()) if not month_txs.empty else 0
    gastos = float(month_txs[month_txs["type"] == "gasto"]["amt"].sum()) if not month_txs.empty else 0
    return ingresos, gastos


def render():
    st.header("Dashboard")

    notas = get_df("notas")
    tareas = get_df("tareas")
    habitos = get_df("habitos")
    txs = get_df("txs")
    proyectos = get_df("proyectos")

    # --- Metrics ---
    pending = tareas[~tareas["done"]].shape[0] if not tareas.empty else 0
    completed = tareas[tareas["done"]].shape[0] if not tareas.empty else 0
    today_habs = _get_today_habits(habitos)
    habs_done = sum(1 for _, h in today_habs.iterrows() if is_done_today(h)) if not today_habs.empty else 0
    inc, exp = _get_month_finance(txs)
    balance = inc - exp

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Notas", len(notas), help="Total de notas documentadas")
    c2.metric("Tareas pendientes", pending, help=f"{completed} completadas")
    c3.metric("Habitos hoy", f"{habs_done}/{len(today_habs)}")
    c4.metric("Balance del mes", fmt(balance), delta=f"{fmt(inc)} ingresos" if inc > 0 else None)

    st.divider()

    # --- Charts ---
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("Finanzas (6 meses)")
        now = datetime.now()
        months_data = []
        for i in range(5, -1, -1):
            m = now.month - i
            y = now.year
            if m <= 0:
                m += 12
                y -= 1
            m_inc, m_exp = _get_month_finance(txs, y, m)
            months_data.append({"Mes": f"{y}-{m:02d}", "Ingresos": m_inc, "Gastos": m_exp})

        chart_df = pd.DataFrame(months_data)
        if chart_df[["Ingresos", "Gastos"]].sum().sum() > 0:
            st.bar_chart(chart_df.set_index("Mes"), color=["#4a9e7a", "#c96a6a"])
        else:
            st.info("Agrega ingresos o gastos para ver el grafico.")

    with col_chart2:
        st.subheader("Habitos (7 dias)")
        if not habitos.empty:
            days_data = []
            for d in range(6, -1, -1):
                day = datetime.now() - timedelta(days=d)
                ds = day.strftime("%Y-%m-%d")
                day_label = day.strftime("%a")
                done_count = 0
                for _, h in habitos.iterrows():
                    checks = parse_checks(h.get("checks", "{}"))
                    if checks.get(ds, False):
                        done_count += 1
                days_data.append({"Dia": day_label, "Completados": done_count})
            habit_chart = pd.DataFrame(days_data)
            st.bar_chart(habit_chart.set_index("Dia"), color=["#d4a853"])
        else:
            st.info("Agrega habitos para ver el grafico.")

    st.divider()

    # --- Recent activity + Priority tasks ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Actividad reciente")
        activities = []
        for _, n in notas.iterrows():
            activities.append({"icon": "\U0001f4dd", "name": n["titulo"], "type": "nota", "ts": n["ts"]})
        for _, t in tareas.iterrows():
            activities.append({"icon": "\u2705" if t["done"] else "\u25fb", "name": t["titulo"], "type": "tarea", "ts": t["ts"]})
        for _, p in proyectos.iterrows():
            activities.append({"icon": p.get("emoji", "\U0001f4c1"), "name": p["nombre"], "type": "proyecto", "ts": p["ts"]})
        for _, tx in txs.iterrows():
            sign = "+" if tx["type"] == "ingreso" else "-"
            activities.append({"icon": "\U0001f4b0" if tx["type"] == "ingreso" else "\U0001f4b8", "name": f"{sign}{fmt(tx['amt'])} {tx['desc']}", "type": tx["type"], "ts": tx["ts"]})

        activities.sort(key=lambda x: x["ts"], reverse=True)
        if activities:
            for a in activities[:8]:
                st.markdown(f"{a['icon']} **{a['name']}** `{a['type']}`")
        else:
            st.info("Sin actividad aun. Empieza creando notas, tareas o registrando gastos.")

    with col_right:
        st.subheader("Tareas prioritarias")
        if not tareas.empty:
            pri_order = {"alta": 0, "media": 1, "baja": 2}
            pending_tasks = tareas[~tareas["done"]].copy()
            if not pending_tasks.empty:
                pending_tasks["_pri_ord"] = pending_tasks["prioridad"].map(pri_order).fillna(2)
                pending_tasks = pending_tasks.sort_values("_pri_ord").head(5)
                for _, t in pending_tasks.iterrows():
                    pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "\u26aa")
                    area_label = AREA_LABELS.get(t["area"], t["area"])
                    fecha = f" \U0001f4c5 {t['fecha']}" if t.get("fecha") else ""
                    st.markdown(f"{pri_emoji} **{t['titulo']}** \u2022 {area_label}{fecha}")
            else:
                st.success("Sin tareas pendientes \u2713")
        else:
            st.info("No hay tareas.")

    st.divider()

    # --- Habits today + Finance summary ---
    col_h, col_f = st.columns(2)

    with col_h:
        st.subheader("Habitos de hoy")
        if not today_habs.empty:
            for _, h in today_habs.head(6).iterrows():
                done = is_done_today(h)
                emoji = h.get("emoji", "\u2b50")
                status = "\u2705" if done else "\u2b1c"
                st.markdown(f"{status} {emoji} {h['name']}")
        else:
            st.info("No hay habitos configurados.")

    with col_f:
        st.subheader("Resumen financiero del mes")
        st.markdown(f"**Ingresos:** :green[{fmt(inc)}]")
        st.markdown(f"**Gastos:** :red[{fmt(exp)}]")
        color = "green" if balance >= 0 else "red"
        st.markdown(f"**Balance:** :{color}[{fmt(balance)}]")

        # Project progress summary
        if not proyectos.empty:
            st.divider()
            st.subheader("Proyectos activos")
            for _, p in proyectos.head(4).iterrows():
                proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
                total = len(proj_tasks)
                done = proj_tasks["done"].sum() if total > 0 else 0
                pct = int(done / total * 100) if total > 0 else 0
                proj_emoji = p.get('emoji', '\U0001f4c1')
                st.markdown(f"{proj_emoji} **{p['nombre']}** - {pct}%")
                st.progress(pct / 100)
