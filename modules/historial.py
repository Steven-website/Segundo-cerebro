import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df, save_df
from core.constants import fmt


def render():
    st.header("Historial")

    tab_tareas, tab_ejercicio, tab_lectura, tab_finanzas = st.tabs(
        ["Tareas", "Ejercicio", "Lectura", "Finanzas"]
    )

    with tab_tareas:
        _render_tareas()
    with tab_ejercicio:
        _render_ejercicio()
    with tab_lectura:
        _render_lectura()
    with tab_finanzas:
        _render_finanzas()


def _render_tareas():
    st.caption("Tareas completadas agrupadas por semana")

    tareas = get_df("tareas")
    proyectos = get_df("proyectos")

    if tareas.empty:
        st.info("No hay tareas registradas.")
        return

    done = tareas[tareas["done"] == True].copy()
    if done.empty:
        st.info("No hay tareas completadas aun.")
        return

    # Use fecha_completada first, fallback to fecha, then ts
    def _get_done_date(row):
        fc = row.get("fecha_completada", "")
        if fc and str(fc) not in ("", "nan"):
            return str(fc)
        if row.get("fecha"):
            return row["fecha"]
        try:
            return datetime.fromtimestamp(row["ts"]).strftime("%Y-%m-%d")
        except Exception:
            return ""

    done["done_date"] = done.apply(_get_done_date, axis=1)
    done = done[done["done_date"] != ""].sort_values("done_date", ascending=False)

    now = datetime.now()

    # --- Filter ---
    filter_options = {
        "4sem": "Ultimas 4 semanas",
        "8sem": "Ultimas 8 semanas",
        "3mes": "Ultimos 3 meses",
        "todo": "Todo",
    }
    col_f, col_p = st.columns(2)
    with col_f:
        filtro = st.selectbox("Periodo", list(filter_options.keys()),
                              format_func=lambda x: filter_options[x],
                              label_visibility="collapsed")
    with col_p:
        proj_options = ["Todos"]
        proj_ids = [""]
        if not proyectos.empty:
            for _, p in proyectos.iterrows():
                proj_options.append(f"{p.get('emoji', '📁')} {p['nombre']}")
                proj_ids.append(p["id"])
        proj_sel = st.selectbox("Proyecto", range(len(proj_options)),
                                format_func=lambda i: proj_options[i],
                                label_visibility="collapsed")

    if filtro == "4sem":
        cutoff = (now - timedelta(weeks=4)).strftime("%Y-%m-%d")
        done = done[done["done_date"] >= cutoff]
    elif filtro == "8sem":
        cutoff = (now - timedelta(weeks=8)).strftime("%Y-%m-%d")
        done = done[done["done_date"] >= cutoff]
    elif filtro == "3mes":
        cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        done = done[done["done_date"] >= cutoff]

    if proj_sel > 0:
        done = done[done["proyecto"] == proj_ids[proj_sel]]

    if done.empty:
        st.info("No hay tareas completadas en este periodo.")
        return

    # --- Metrics ---
    total_done = len(done)
    weeks_set = set()
    for _, t in done.iterrows():
        try:
            d = datetime.strptime(t["done_date"], "%Y-%m-%d")
            monday = d - timedelta(days=d.weekday())
            weeks_set.add(monday.strftime("%Y-%m-%d"))
        except (ValueError, TypeError):
            pass
    num_weeks = max(len(weeks_set), 1)
    avg_per_week = total_done / num_weeks

    c1, c2, c3 = st.columns(3)
    c1.metric("Total completadas", total_done)
    c2.metric("Semanas", num_weeks)
    c3.metric("Promedio/semana", f"{avg_per_week:.1f}")

    st.divider()

    # --- Group by week ---
    weeks = {}
    for _, t in done.iterrows():
        try:
            d = datetime.strptime(t["done_date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        wk_key = monday.strftime("%Y-%m-%d")
        if wk_key not in weeks:
            weeks[wk_key] = {"start": monday, "end": sunday, "tasks": []}

        proj_name = ""
        if t.get("proyecto") and not proyectos.empty:
            pm = proyectos[proyectos["id"] == t["proyecto"]]
            if not pm.empty:
                proj_name = pm.iloc[0].get("emoji", "📁") + " " + pm.iloc[0]["nombre"]

        weeks[wk_key]["tasks"].append({
            "id": t["id"],
            "titulo": t["titulo"],
            "fecha": t["done_date"],
            "proyecto": proj_name,
        })

    for wk_key in sorted(weeks.keys(), reverse=True):
        wk = weeks[wk_key]
        start_label = wk["start"].strftime("%d/%m/%Y")
        end_label = wk["end"].strftime("%d/%m/%Y")
        is_current = wk["start"].date() <= now.date() <= wk["end"].date()
        icon = "📌" if is_current else "📅"

        with st.expander(f"{icon} Semana {start_label} — {end_label} ({len(wk['tasks'])} tareas)", expanded=is_current):
            by_proj = {}
            for task in wk["tasks"]:
                proj = task["proyecto"] or "Sin proyecto"
                if proj not in by_proj:
                    by_proj[proj] = []
                by_proj[proj].append(task)

            for proj, tasks in by_proj.items():
                st.markdown(f"**{proj}** ({len(tasks)})")
                for task in tasks:
                    col_t, col_d = st.columns([5, 2])
                    with col_t:
                        st.markdown(f"- ✅ {task['titulo']} — `{task['fecha']}`")
                    with col_d:
                        new_date = st.date_input(
                            "fecha", value=datetime.strptime(task["fecha"], "%Y-%m-%d").date(),
                            key=f"hist_date_{task['id']}", label_visibility="collapsed",
                        )
                        new_date_str = new_date.strftime("%Y-%m-%d")
                        if new_date_str != task["fecha"]:
                            tareas = get_df("tareas")
                            tareas.loc[tareas["id"] == task["id"], "fecha_completada"] = new_date_str
                            save_df("tareas", tareas)
                            st.rerun()


def _render_ejercicio():
    st.caption("Historial de sesiones de ejercicio")

    exercise = get_df("exercise_log")
    if exercise.empty:
        st.info("No hay sesiones de ejercicio registradas.")
        return

    now = datetime.now()
    filter_options = {"1mes": "Ultimo mes", "3mes": "3 meses", "6mes": "6 meses", "todo": "Todo"}
    filtro = st.selectbox("Periodo", list(filter_options.keys()),
                          format_func=lambda x: filter_options[x],
                          label_visibility="collapsed", key="hist_ex_filter")

    if filtro == "1mes":
        cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        exercise = exercise[exercise["fecha"] >= cutoff]
    elif filtro == "3mes":
        cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        exercise = exercise[exercise["fecha"] >= cutoff]
    elif filtro == "6mes":
        cutoff = (now - timedelta(days=180)).strftime("%Y-%m-%d")
        exercise = exercise[exercise["fecha"] >= cutoff]

    if exercise.empty:
        st.info("No hay sesiones en este periodo.")
        return

    total = len(exercise)
    total_mins = int(exercise["duracion"].sum())
    sports = exercise["deporte"].nunique()

    c1, c2, c3 = st.columns(3)
    c1.metric("Sesiones", total)
    c2.metric("Minutos totales", total_mins)
    c3.metric("Deportes", sports)

    st.divider()

    # Group by month
    exercise["month"] = exercise["fecha"].str[:7]
    for month in sorted(exercise["month"].unique(), reverse=True):
        m_data = exercise[exercise["month"] == month]
        m_mins = int(m_data["duracion"].sum())
        with st.expander(f"📅 {month} — {len(m_data)} sesiones, {m_mins} min"):
            for _, s in m_data.sort_values("fecha", ascending=False).iterrows():
                notas = f" — {s['notas']}" if s.get("notas") else ""
                st.caption(f"{s['fecha']} | {s['deporte']} | {int(s['duracion'])} min{notas}")


def _render_lectura():
    st.caption("Historial de lectura")

    books = get_df("books")
    sessions = get_df("reading_sessions")

    if books.empty:
        st.info("No hay libros registrados.")
        return

    completed = books[books["estado"] == "completado"].copy()
    reading_now = books[books["estado"] == "leyendo"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Completados", len(completed))
    c2.metric("Leyendo", len(reading_now))
    total_pages = int(sessions["paginas"].sum()) if not sessions.empty else 0
    c3.metric("Paginas totales", total_pages)

    if not completed.empty:
        st.divider()
        st.subheader("Libros completados")
        for _, b in completed.sort_values("fecha_fin", ascending=False).iterrows():
            stars = "⭐" * int(b["rating"]) if b["rating"] > 0 else ""
            fecha_label = f" | {b['fecha_fin']}" if b.get("fecha_fin") else ""
            st.markdown(f"📗 **{b['titulo']}** — {b['autor']}{fecha_label} {stars}")

    if not reading_now.empty:
        st.divider()
        st.subheader("Leyendo ahora")
        for _, b in reading_now.iterrows():
            pct = int(b["paginas_leidas"] / b["paginas"] * 100) if b["paginas"] > 0 else 0
            st.markdown(f"📖 **{b['titulo']}** — {b['autor']} ({pct}%)")
            st.progress(min(pct / 100, 1.0))


def _render_finanzas():
    st.caption("Historial de transacciones")

    txs = get_df("txs")
    if txs.empty:
        st.info("No hay transacciones registradas.")
        return

    now = datetime.now()
    filter_options = {"1mes": "Ultimo mes", "3mes": "3 meses", "6mes": "6 meses", "todo": "Todo"}
    filtro = st.selectbox("Periodo", list(filter_options.keys()),
                          format_func=lambda x: filter_options[x],
                          label_visibility="collapsed", key="hist_fin_filter")

    if filtro == "1mes":
        cutoff = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        txs = txs[txs["fecha"] >= cutoff]
    elif filtro == "3mes":
        cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        txs = txs[txs["fecha"] >= cutoff]
    elif filtro == "6mes":
        cutoff = (now - timedelta(days=180)).strftime("%Y-%m-%d")
        txs = txs[txs["fecha"] >= cutoff]

    if txs.empty:
        st.info("No hay transacciones en este periodo.")
        return

    inc = float(txs[txs["type"] == "ingreso"]["amt"].sum())
    exp = float(txs[txs["type"] == "gasto"]["amt"].sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(inc))
    c2.metric("Gastos", fmt(exp))
    c3.metric("Balance", fmt(inc - exp))

    st.divider()

    # Group by month
    txs["month"] = txs["fecha"].str[:7]
    for month in sorted(txs["month"].unique(), reverse=True):
        m_data = txs[txs["month"] == month]
        m_inc = float(m_data[m_data["type"] == "ingreso"]["amt"].sum())
        m_exp = float(m_data[m_data["type"] == "gasto"]["amt"].sum())
        with st.expander(f"📅 {month} — Ing: {fmt(m_inc)} | Gas: {fmt(m_exp)}"):
            for _, tx in m_data.sort_values("fecha", ascending=False).iterrows():
                icon = "💰" if tx["type"] == "ingreso" else "💸"
                st.caption(f"{tx['fecha']} | {icon} {fmt(tx['amt'])} | {tx['desc']}")
