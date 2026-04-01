import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df, save_df
from core.constants import fmt


def render():
    st.header("Historial de trabajo")
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

    # --- Filter ---
    now = datetime.now()
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
        # Project filter
        proj_options = ["Todos"]
        proj_ids = [""]
        if not proyectos.empty:
            for _, p in proyectos.iterrows():
                proj_options.append(f"{p.get('emoji', '📁')} {p['nombre']}")
                proj_ids.append(p["id"])
        proj_sel = st.selectbox("Proyecto", range(len(proj_options)),
                                format_func=lambda i: proj_options[i],
                                label_visibility="collapsed")

    # Apply date filter
    if filtro == "4sem":
        cutoff = (now - timedelta(weeks=4)).strftime("%Y-%m-%d")
        done = done[done["done_date"] >= cutoff]
    elif filtro == "8sem":
        cutoff = (now - timedelta(weeks=8)).strftime("%Y-%m-%d")
        done = done[done["done_date"] >= cutoff]
    elif filtro == "3mes":
        cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%d")
        done = done[done["done_date"] >= cutoff]

    # Apply project filter
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

        # Get project name
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
            "area": t.get("area", ""),
        })

    # --- Render weeks ---
    for wk_key in sorted(weeks.keys(), reverse=True):
        wk = weeks[wk_key]
        start_label = wk["start"].strftime("%d/%m/%Y")
        end_label = wk["end"].strftime("%d/%m/%Y")
        is_current = wk["start"].date() <= now.date() <= wk["end"].date()
        icon = "📌" if is_current else "📅"

        with st.expander(f"{icon} Semana {start_label} — {end_label} ({len(wk['tasks'])} tareas)", expanded=is_current):
            # Group by project within week
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
