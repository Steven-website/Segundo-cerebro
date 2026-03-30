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

    tareas = get_df("tareas")
    habitos = get_df("habitos")
    txs = get_df("txs")
    proyectos = get_df("proyectos")
    debts = get_df("debts")

    # ═══ NEEDS ATTENTION ═══
    alerts = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Overdue tasks
    if not tareas.empty:
        overdue = tareas[(~tareas["done"]) & (tareas["fecha"] != "") & (tareas["fecha"] < today_str)]
        if not overdue.empty:
            alerts.append(("warning", f"⚠️ {len(overdue)} tarea(s) vencida(s)", "Revisa tus proyectos"))

    # Tasks due in next 3 days
    if not tareas.empty:
        soon_str = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        upcoming = tareas[(~tareas["done"]) & (tareas["fecha"] != "") & (tareas["fecha"] >= today_str) & (tareas["fecha"] <= soon_str)]
        if not upcoming.empty:
            names = ", ".join(upcoming["titulo"].head(3).tolist())
            extra = f" (+{len(upcoming)-3} mas)" if len(upcoming) > 3 else ""
            alerts.append(("info", f"📅 {len(upcoming)} tarea(s) vence(n) pronto", f"{names}{extra}"))

    # Habits not done today
    today_habs = _get_today_habits(habitos)
    if not today_habs.empty:
        not_done = sum(1 for _, h in today_habs.iterrows() if not is_done_today(h))
        if not_done > 0:
            alerts.append(("info", f"⬜ {not_done} habito(s) pendiente(s) hoy", "Ve a Habitos"))

    # Overdue debts
    if not debts.empty:
        for _, d in debts.iterrows():
            if d.get("due") and d["due"] <= today_str and d["paid"] < d["total"]:
                remaining = d["total"] - d["paid"]
                alerts.append(("error", f"🔴 Deuda vencida: {d['name']}", f"Pendiente: {fmt(remaining)}"))

    # Budget exceeded
    budget_df = get_df("budget")
    from core.constants import BUDGET_DEFAULT
    budget = dict(zip(budget_df["cat"], budget_df["amt"])) if not budget_df.empty else BUDGET_DEFAULT.copy()
    month_txs = txs[txs["fecha"].str.startswith(today_str[:7])] if not txs.empty else pd.DataFrame()
    for cat, limit in budget.items():
        if cat == "ingreso" or limit <= 0:
            continue
        spent = float(month_txs[(month_txs["type"] == "gasto") & (month_txs["cat"] == cat)]["amt"].sum()) if not month_txs.empty else 0
        if spent > limit:
            alerts.append(("error", f"💸 {cat.capitalize()}: excede presupuesto", f"{fmt(spent)} / {fmt(limit)}"))

    if alerts:
        st.subheader("Necesita atencion")
        for alert_type, msg, detail in alerts:
            with st.container(border=True):
                if alert_type == "error":
                    st.error(f"{msg} — {detail}")
                elif alert_type == "warning":
                    st.warning(f"{msg} — {detail}")
                else:
                    st.info(f"{msg} — {detail}")
        st.divider()

    # --- Widget config ---
    with st.expander("Personalizar widgets"):
        st.caption("Elige que secciones mostrar en tu dashboard")
        show_metrics = st.checkbox("Metricas principales", value=st.session_state.get("dash_metrics", True), key="dash_metrics")
        show_finance_chart = st.checkbox("Grafico de finanzas", value=st.session_state.get("dash_fin_chart", True), key="dash_fin_chart")
        show_habits_chart = st.checkbox("Grafico de habitos", value=st.session_state.get("dash_hab_chart", True), key="dash_hab_chart")
        show_savings_chart = st.checkbox("Grafico de ahorros", value=st.session_state.get("dash_sav_chart", True), key="dash_sav_chart")
        show_inventory_chart = st.checkbox("Grafico de inventario", value=st.session_state.get("dash_inv_chart", True), key="dash_inv_chart")
        show_activity = st.checkbox("Actividad reciente", value=st.session_state.get("dash_activity", True), key="dash_activity")
        show_priority = st.checkbox("Tareas prioritarias", value=st.session_state.get("dash_priority", True), key="dash_priority")
        show_today_habits = st.checkbox("Habitos de hoy", value=st.session_state.get("dash_today_hab", True), key="dash_today_hab")
        show_finance_summary = st.checkbox("Resumen financiero", value=st.session_state.get("dash_fin_sum", True), key="dash_fin_sum")
        show_metas = st.checkbox("Metas activas", value=st.session_state.get("dash_metas", True), key="dash_metas")
        show_pomo = st.checkbox("Pomodoro de hoy", value=st.session_state.get("dash_pomo", True), key="dash_pomo")

    # --- Metrics ---
    if show_metrics:
        pending = tareas[~tareas["done"]].shape[0] if not tareas.empty else 0
        completed = tareas[tareas["done"]].shape[0] if not tareas.empty else 0
        today_habs = _get_today_habits(habitos)
        habs_done = sum(1 for _, h in today_habs.iterrows() if is_done_today(h)) if not today_habs.empty else 0
        inc, exp = _get_month_finance(txs)
        balance = inc - exp

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Proyectos", len(proyectos))
        c2.metric("Tareas pendientes", pending, help=f"{completed} completadas")
        c3.metric("Habitos hoy", f"{habs_done}/{len(today_habs)}")
        c4.metric("Balance del mes", fmt(balance), delta=f"{fmt(inc)} ingresos" if inc > 0 else None)

        st.divider()

    # --- Charts row 1 ---
    col_chart1, col_chart2 = st.columns(2)

    if show_finance_chart:
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

    if show_habits_chart:
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

    # --- Charts row 2 ---
    savings = get_df("savings")
    inventario = get_df("inventario")

    col_chart3, col_chart4 = st.columns(2)

    if show_savings_chart:
        with col_chart3:
            st.subheader("Metas de ahorro")
            if not savings.empty:
                sav_data = []
                for _, s in savings.iterrows():
                    pct = min(s["current"] / s["goal"] * 100, 100) if s["goal"] > 0 else 0
                    sav_data.append({"Meta": s["name"][:20], "Progreso %": pct})
                sav_chart = pd.DataFrame(sav_data)
                st.bar_chart(sav_chart.set_index("Meta"), color=["#4a9e7a"])
            else:
                st.info("Agrega metas de ahorro.")

    if show_inventory_chart:
        with col_chart4:
            st.subheader("Inventario por categoria")
            if not inventario.empty:
                inv_grouped = inventario.groupby("cat").apply(lambda g: (g["val"] * g["qty"]).sum()).reset_index()
                inv_grouped.columns = ["Categoria", "Valor"]
                inv_grouped["Categoria"] = inv_grouped["Categoria"].str.capitalize()
                st.bar_chart(inv_grouped.set_index("Categoria"), color=["#8a6ac9"])
            else:
                st.info("Agrega items al inventario.")

    st.divider()

    # --- Pomodoro today ---
    if show_pomo:
        pomo_sessions = get_df("pomo_sessions")
        if not pomo_sessions.empty:
            today_pomo = pomo_sessions[pomo_sessions["fecha"] == today_str]
            if not today_pomo.empty:
                st.subheader("Pomodoro hoy")
                cp1, cp2 = st.columns(2)
                cp1.metric("Sesiones", len(today_pomo))
                cp2.metric("Minutos enfocados", int(today_pomo["minutos"].sum()))
                st.divider()

    # --- Metas activas ---
    if show_metas:
        metas = get_df("metas")
        if not metas.empty:
            active_metas = metas[~metas["completada"].fillna(False)]
            if not active_metas.empty:
                st.subheader("Metas activas")
                for _, m in active_metas.head(4).iterrows():
                    pct = min(m["progreso"] / 100, 1.0)
                    st.markdown(f"**{m['titulo']}** - {m['periodo'].capitalize()}")
                    st.progress(pct, text=f"{int(m['progreso'])}%")
                st.divider()

    # --- Activity + Priority ---
    col_left, col_right = st.columns(2)

    if show_activity:
        with col_left:
            st.subheader("Actividad reciente")
            activities = []
            for _, t in tareas.iterrows():
                activities.append({"icon": "✅" if t["done"] else "⬜", "name": t["titulo"], "type": "tarea", "ts": t["ts"]})
            for _, p in proyectos.iterrows():
                activities.append({"icon": p.get("emoji", "📁"), "name": p["nombre"], "type": "proyecto", "ts": p["ts"]})
            for _, tx in txs.iterrows():
                sign = "+" if tx["type"] == "ingreso" else "-"
                activities.append({"icon": "💰" if tx["type"] == "ingreso" else "💸", "name": f"{sign}{fmt(tx['amt'])} {tx['desc']}", "type": tx["type"], "ts": tx["ts"]})

            activities.sort(key=lambda x: x["ts"], reverse=True)
            if activities:
                for a in activities[:8]:
                    st.markdown(f"{a['icon']} **{a['name']}** `{a['type']}`")
            else:
                st.info("Sin actividad aun.")

    if show_priority:
        with col_right:
            st.subheader("Tareas prioritarias")
            if not tareas.empty:
                pri_order = {"alta": 0, "media": 1, "baja": 2}
                pending_tasks = tareas[~tareas["done"]].copy()
                if not pending_tasks.empty:
                    pending_tasks["_pri_ord"] = pending_tasks["prioridad"].map(pri_order).fillna(2)
                    pending_tasks = pending_tasks.sort_values("_pri_ord").head(5)
                    for _, t in pending_tasks.iterrows():
                        pri_emoji = PRIORITY_EMOJIS.get(t["prioridad"], "")
                        area_label = AREA_LABELS.get(t["area"], t["area"])
                        fecha = f" {t['fecha']}" if t.get("fecha") else ""
                        st.markdown(f"{pri_emoji} **{t['titulo']}** - {area_label}{fecha}")
                else:
                    st.success("Sin tareas pendientes!")
            else:
                st.info("No hay tareas.")

    st.divider()

    # --- Habits today + Finance summary ---
    col_h, col_f = st.columns(2)

    if show_today_habits:
        with col_h:
            st.subheader("Habitos de hoy")
            today_habs = _get_today_habits(habitos)
            if not today_habs.empty:
                for _, h in today_habs.head(6).iterrows():
                    done = is_done_today(h)
                    emoji = h.get("emoji", "⭐")
                    status = "✅" if done else "⬜"
                    st.markdown(f"{status} {emoji} {h['name']}")
            else:
                st.info("No hay habitos configurados.")

    if show_finance_summary:
        with col_f:
            inc, exp = _get_month_finance(txs)
            balance = inc - exp
            st.subheader("Resumen financiero del mes")
            st.markdown(f"**Ingresos:** :green[{fmt(inc)}]")
            st.markdown(f"**Gastos:** :red[{fmt(exp)}]")
            color = "green" if balance >= 0 else "red"
            st.markdown(f"**Balance:** :{color}[{fmt(balance)}]")

            if not proyectos.empty:
                st.divider()
                st.subheader("Proyectos activos")
                for _, p in proyectos.head(4).iterrows():
                    proj_tasks = tareas[tareas["proyecto"] == p["id"]] if not tareas.empty else pd.DataFrame()
                    total = len(proj_tasks)
                    done = proj_tasks["done"].sum() if total > 0 else 0
                    pct = int(done / total * 100) if total > 0 else 0
                    proj_emoji = p.get('emoji', '📁')
                    st.markdown(f"{proj_emoji} **{p['nombre']}** - {pct}%")
                    st.progress(pct / 100)
