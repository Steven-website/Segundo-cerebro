import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREA_LABELS, fmt, HABIT_FREQ
from core.utils import is_done_today, parse_checks, PRIORITY_EMOJIS


def _get_today_habits(habitos_df):
    if habitos_df.empty:
        return habitos_df
    from core.utils import habit_applies_today
    mask = [habit_applies_today(h) for _, h in habitos_df.iterrows()]
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
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    hour = now.hour
    saludo = "Buenos dias" if hour < 12 else "Buenas tardes" if hour < 18 else "Buenas noches"

    tareas = get_df("tareas")
    habitos = get_df("habitos")
    txs = get_df("txs")
    proyectos = get_df("proyectos")
    savings = get_df("savings")

    st.markdown(f"### {saludo} 👋")
    st.caption(now.strftime("%A %d de %B, %Y").capitalize())

    # ═══ QUICK METRICS ═══
    pending = tareas[~tareas["done"]].shape[0] if not tareas.empty else 0
    today_habs = _get_today_habits(habitos)
    habs_done = sum(1 for _, h in today_habs.iterrows() if is_done_today(h)) if not today_habs.empty else 0
    habs_total = len(today_habs)
    inc, exp = _get_month_finance(txs)
    balance = inc - exp
    active_projects = len(proyectos[proyectos["estado"] != "completado"]) if not proyectos.empty and "estado" in proyectos.columns else len(proyectos)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Pendientes", pending)
    c2.metric("◉ Habitos", f"{habs_done}/{habs_total}")
    c3.metric("◈ Proyectos", active_projects)
    bal_color = "normal" if balance >= 0 else "inverse"
    c4.metric("₡ Balance", fmt(balance), delta=f"{fmt(inc)} ing." if inc > 0 else None, delta_color=bal_color)

    st.divider()

    # ═══ ALERTS ═══
    alerts = []
    if not tareas.empty:
        overdue = tareas[(~tareas["done"]) & (tareas["fecha"] != "") & (tareas["fecha"] < today_str)]
        if not overdue.empty:
            alerts.append(("⚠️", f"{len(overdue)} tarea(s) vencida(s)", "warning"))
        soon_str = (now + timedelta(days=3)).strftime("%Y-%m-%d")
        upcoming = tareas[(~tareas["done"]) & (tareas["fecha"] != "") & (tareas["fecha"] >= today_str) & (tareas["fecha"] <= soon_str)]
        if not upcoming.empty:
            alerts.append(("📅", f"{len(upcoming)} tarea(s) vence(n) pronto", "info"))

    if habs_total > 0:
        not_done = habs_total - habs_done
        if not_done > 0:
            alerts.append(("⬜", f"{not_done} habito(s) pendiente(s)", "info"))

    if alerts:
        for icon, msg, atype in alerts:
            if atype == "warning":
                st.warning(f"{icon} {msg}")
            elif atype == "error":
                st.error(f"{icon} {msg}")
            else:
                st.info(f"{icon} {msg}")
        st.divider()

    # ═══ TODAY'S FOCUS ═══
    col_tasks, col_habits = st.columns(2)

    with col_tasks:
        st.markdown("**📌 Tareas prioritarias**")
        if not tareas.empty:
            pri_order = {"alta": 0, "media": 1, "baja": 2}
            pending_tasks = tareas[~tareas["done"]].copy()
            if not pending_tasks.empty:
                pending_tasks["_pri_ord"] = pending_tasks["prioridad"].map(pri_order).fillna(2)
                for _, t in pending_tasks.sort_values("_pri_ord").head(5).iterrows():
                    pri = PRIORITY_EMOJIS.get(t["prioridad"], "")
                    fecha = f" · `{t['fecha']}`" if t.get("fecha") else ""
                    st.markdown(f"{pri} {t['titulo']}{fecha}")
            else:
                st.success("Todo al dia!")
        else:
            st.caption("Sin tareas")

    with col_habits:
        st.markdown("**◉ Habitos de hoy**")
        if not today_habs.empty:
            for _, h in today_habs.iterrows():
                done = is_done_today(h)
                icon = "✅" if done else "⬜"
                emoji = h.get("emoji", "⭐")
                st.markdown(f"{icon} {emoji} {h['name']}")
        else:
            st.caption("Sin habitos para hoy")

    st.divider()

    # ═══ CHARTS ═══
    col_fin, col_hab = st.columns(2)

    with col_fin:
        st.markdown("**₡ Finanzas (6 meses)**")
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
            st.caption("Sin datos de finanzas aun")

    with col_hab:
        st.markdown("**◉ Habitos (7 dias)**")
        if not habitos.empty:
            days_data = []
            for d in range(6, -1, -1):
                day = now - timedelta(days=d)
                ds = day.strftime("%Y-%m-%d")
                day_label = day.strftime("%a")
                done_count = sum(1 for _, h in habitos.iterrows() if parse_checks(h.get("checks", "{}")).get(ds, False))
                days_data.append({"Dia": day_label, "Hechos": done_count})
            st.bar_chart(pd.DataFrame(days_data).set_index("Dia"), color=["#d4a853"])
        else:
            st.caption("Sin habitos configurados")

    st.divider()

    # ═══ SAVINGS + PROJECTS ═══
    col_sav, col_proj = st.columns(2)

    with col_sav:
        st.markdown("**🏦 Metas de ahorro**")
        if not savings.empty:
            for _, s in savings.head(4).iterrows():
                pct = min(s["current"] / s["goal"], 1.0) if s["goal"] > 0 else 0
                st.markdown(f"**{s['name']}**")
                st.progress(pct, text=f"{fmt(s['current'])} / {fmt(s['goal'])}")
        else:
            st.caption("Sin metas de ahorro")

    with col_proj:
        st.markdown("**◈ Proyectos activos**")
        if not proyectos.empty:
            for _, p in proyectos.head(4).iterrows():
                proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
                total = len(proj_tasks)
                done = proj_tasks["done"].sum() if total > 0 else 0
                pct = int(done / total * 100) if total > 0 else 0
                emoji = p.get('emoji', '📁')
                st.markdown(f"{emoji} **{p['nombre']}**")
                st.progress(pct / 100, text=f"{pct}% ({int(done)}/{total})")
        else:
            st.caption("Sin proyectos")

    st.divider()

    # ═══ QUICK NOTES ═══
    _render_quick_notes(tareas, proyectos)

    # ═══ RECENT ACTIVITY ═══
    with st.expander("📋 Actividad reciente"):
        activities = []
        if not tareas.empty:
            for _, t in tareas.iterrows():
                activities.append({"icon": "✅" if t["done"] else "⬜", "text": t["titulo"], "type": "tarea", "ts": t["ts"]})
        if not txs.empty:
            for _, tx in txs.head(10).iterrows():
                sign = "+" if tx["type"] == "ingreso" else "-"
                activities.append({"icon": "💰" if tx["type"] == "ingreso" else "💸", "text": f"{sign}{fmt(tx['amt'])} {tx['desc']}", "type": tx["type"], "ts": tx["ts"]})
        activities.sort(key=lambda x: x["ts"], reverse=True)
        for a in activities[:10]:
            st.markdown(f"{a['icon']} {a['text']}")
        if not activities:
            st.caption("Sin actividad aun")


def _render_quick_notes(tareas, proyectos):
    """Quick capture notes with convert-to-task action."""
    notas = get_df("notas_rapidas")

    with st.expander("💡 Notas rapidas", expanded=False):
        with st.form("quick_note_form", clear_on_submit=True):
            col_input, col_btn = st.columns([5, 1])
            texto = col_input.text_input("Captura una idea...", placeholder="Escribe algo rapido", label_visibility="collapsed")
            submitted = col_btn.form_submit_button("💡", type="primary")
            if submitted and texto.strip():
                new_note = {
                    "id": uid(), "texto": texto.strip(),
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "ts": now_ts(),
                }
                notas = pd.concat([pd.DataFrame([new_note]), notas], ignore_index=True)
                save_df("notas_rapidas", notas)
                st.rerun()

        if notas.empty:
            st.caption("Escribe ideas o recordatorios.")
        else:
            for _, n in notas.sort_values("ts", ascending=False).head(10).iterrows():
                col_note, col_actions = st.columns([5, 2])
                with col_note:
                    st.markdown(f"💡 {n['texto']}")
                    st.caption(n["fecha"])
                with col_actions:
                    ca, cb = st.columns(2)
                    with ca:
                        if st.button("📋", key=f"qn_task_{n['id']}", help="Crear tarea"):
                            st.session_state["qn_to_task"] = n["id"]
                            st.rerun()
                    with cb:
                        if st.button("🗑️", key=f"qn_del_{n['id']}", help="Eliminar"):
                            notas = notas[notas["id"] != n["id"]]
                            save_df("notas_rapidas", notas)
                            st.rerun()

        if st.session_state.get("qn_to_task"):
            note_id = st.session_state["qn_to_task"]
            note_match = notas[notas["id"] == note_id] if not notas.empty else pd.DataFrame()
            if not note_match.empty:
                note = note_match.iloc[0]
                with st.form("qn_task_form"):
                    st.subheader("Convertir en tarea")
                    titulo = st.text_input("Titulo", value=note["texto"])
                    proj_options = ["Sin proyecto"]
                    proj_ids = [""]
                    if not proyectos.empty:
                        for _, p in proyectos.iterrows():
                            proj_options.append(f"{p.get('emoji', '📁')} {p['nombre']}")
                            proj_ids.append(p["id"])
                    proj_sel = st.selectbox("Proyecto", range(len(proj_options)), format_func=lambda i: proj_options[i])

                    col_s, col_c = st.columns(2)
                    if col_s.form_submit_button("Crear tarea", type="primary"):
                        new_task = {
                            "id": uid(), "titulo": titulo.strip(), "area": "personal",
                            "prioridad": "media", "fecha_inicio": "", "fecha": "",
                            "proyecto": proj_ids[proj_sel], "notas": "", "subtareas": "",
                            "recurrente": "", "depende_de": "", "etiqueta": "",
                            "done": False, "pinned": False, "archived": False, "ts": now_ts(),
                        }
                        tareas = pd.concat([pd.DataFrame([new_task]), tareas], ignore_index=True)
                        save_df("tareas", tareas)
                        notas = notas[notas["id"] != note_id]
                        save_df("notas_rapidas", notas)
                        st.session_state["qn_to_task"] = None
                        st.rerun()
                    if col_c.form_submit_button("Cancelar"):
                        st.session_state["qn_to_task"] = None
                        st.rerun()
