import streamlit as st
import json
import os
from core.styles import inject_css

st.set_page_config(
    page_title="Segundo Cerebro",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_css()

# --- Auth check ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    from core.auth import render_auth
    render_auth()
    st.stop()


# --- Alerts helper ---
def show_alerts():
    from core.data import get_df
    from core.constants import BUDGET_DEFAULT, fmt
    from datetime import datetime

    alerts = []

    tareas = get_df("tareas")
    if not tareas.empty:
        today = datetime.now().strftime("%Y-%m-%d")
        overdue = tareas[(~tareas["done"]) & (tareas["fecha"] != "") & (tareas["fecha"] < today)]
        if not overdue.empty:
            alerts.append(("warning", f"⚠️ {len(overdue)} tarea(s) vencida(s)"))

        due_today = tareas[(~tareas["done"]) & (tareas["fecha"] == today)]
        if not due_today.empty:
            alerts.append(("info", f"📋 {len(due_today)} tarea(s) para hoy"))

    txs = get_df("txs")
    budget_df = get_df("budget")
    if not txs.empty:
        budget = dict(zip(budget_df["cat"], budget_df["amt"])) if not budget_df.empty else BUDGET_DEFAULT.copy()
        now = datetime.now()
        prefix = f"{now.year}-{now.month:02d}"
        month_txs = txs[(txs["fecha"].str.startswith(prefix)) & (txs["type"] == "gasto")]
        for cat, limit in budget.items():
            if cat == "ingreso":
                continue
            spent = float(month_txs[month_txs["cat"] == cat]["amt"].sum()) if not month_txs.empty else 0
            if limit > 0 and spent > limit:
                alerts.append(("error", f"💸 {cat.capitalize()}: excede presupuesto ({fmt(spent)}/{fmt(limit)})"))

    debts = get_df("debts")
    if not debts.empty:
        today = datetime.now().strftime("%Y-%m-%d")
        for _, d in debts.iterrows():
            if d.get("due") and d["due"] <= today and d["paid"] < d["total"]:
                alerts.append(("error", f"🔴 Deuda vencida: {d['name']}"))

    metas = get_df("metas")
    if not metas.empty:
        active = metas[~metas["completada"].fillna(False)]
        high_progress = active[active["progreso"] >= 80]
        if not high_progress.empty:
            alerts.append(("success", f"🎯 {len(high_progress)} meta(s) casi completada(s)!"))

    for alert_type, msg in alerts:
        if alert_type == "warning":
            st.warning(msg)
        elif alert_type == "error":
            st.error(msg)
        elif alert_type == "success":
            st.success(msg)
        elif alert_type == "info":
            st.info(msg)


# --- Navigation pages ---
PAGES = [
    "◈ Dashboard",
    "📌 Hoy",
    "🔍 Buscar",
    "📝 Notas",
    "◈ Proyectos",
    "🎯 Metas",
    "₡ Finanzas",
    "◎ Ahorros & Deudas",
    "◉ Habitos",
    "📅 Calendario",
    "◣ Inventario",
    "🎤 Audios",
    "🍅 Pomodoro",
    "📊 Reportes",
    "💾 Backup & Importar",
    "🗑️ Papelera",
    "👤 Perfil",
]

# --- Top navigation bar (works on mobile) ---
user = st.session_state.get("current_user", "")
avatar = "👤"
if user:
    users_file = os.path.join(os.path.dirname(__file__), "data", "users.json")
    try:
        if os.path.exists(users_file):
            with open(users_file) as f:
                users_data = json.load(f)
            avatar = users_data.get(user, {}).get("avatar", "👤")
    except Exception:
        pass

col_title, col_user, col_logout = st.columns([4, 2, 1])
with col_title:
    st.markdown("### 🧠 Segundo Cerebro")
with col_user:
    st.caption(f"{avatar} {user}")
with col_logout:
    if st.button("Salir", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("df_"):
                del st.session_state[key]
        st.session_state["logged_in"] = False
        st.session_state["current_user"] = ""
        st.rerun()

# Navigation selector
page = st.selectbox(
    "Navegacion",
    PAGES,
    key="nav_page",
    label_visibility="collapsed",
)

# Alerts
show_alerts()

st.divider()

# --- Routing ---
if page == "◈ Dashboard":
    from modules.dashboard import render
elif page == "📌 Hoy":
    from modules.hoy import render
elif page == "🔍 Buscar":
    from modules.buscar import render
elif page == "📝 Notas":
    from modules.notas import render
elif page == "◈ Proyectos":
    from modules.proyectos import render
elif page == "🎯 Metas":
    from modules.metas import render
elif page == "₡ Finanzas":
    from modules.finanzas import render
elif page == "◎ Ahorros & Deudas":
    from modules.ahorros import render
elif page == "◉ Habitos":
    from modules.habitos import render
elif page == "📅 Calendario":
    from modules.calendario import render
elif page == "◣ Inventario":
    from modules.inventario import render
elif page == "🎤 Audios":
    from modules.audio import render
elif page == "🍅 Pomodoro":
    from modules.pomodoro import render
elif page == "📊 Reportes":
    from modules.reportes import render
elif page == "💾 Backup & Importar":
    from modules.backup import render
elif page == "🗑️ Papelera":
    from modules.papelera import render
elif page == "👤 Perfil":
    from modules.perfil import render

render()
