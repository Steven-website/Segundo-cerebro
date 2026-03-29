import streamlit as st
from core.styles import inject_css

st.set_page_config(
    page_title="Segundo Cerebro",
    page_icon="\U0001f9e0",
    layout="wide",
    initial_sidebar_state="expanded",
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
    from core.constants import BUDGET_DEFAULT
    from datetime import datetime

    tareas = get_df("tareas")
    if not tareas.empty:
        today = datetime.now().strftime("%Y-%m-%d")
        overdue = tareas[(~tareas["done"]) & (tareas["fecha"] != "") & (tareas["fecha"] < today)]
        if not overdue.empty:
            st.warning(f"\u26a0\ufe0f {len(overdue)} tarea(s) vencida(s)")

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
                st.error(f"\U0001f4b8 {cat.capitalize()}: excede presupuesto")
                break


# --- Navigation pages ---
PAGES = [
    "\u25c8 Dashboard",
    "\U0001f50d Buscar",
    "\u25fb Notas",
    "\u25f7 Tareas",
    "\u25c8 Proyectos",
    "\u20a1 Finanzas",
    "\u25ce Ahorros & Deudas",
    "\u25c9 Habitos",
    "\U0001f4c5 Calendario",
    "\u25a3 Inventario",
    "\U0001f916 Buscar con IA",
]

# --- Sidebar ---
with st.sidebar:
    st.markdown("### \U0001f9e0 Segundo Cerebro")
    st.caption("v4 \u2022 PKM Personal")

    user = st.session_state.get("current_user", "")
    if user:
        st.markdown(f"\U0001f464 **{user}**")
        if st.button("Cerrar sesion", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key.startswith("df_"):
                    del st.session_state[key]
            st.session_state["logged_in"] = False
            st.session_state["current_user"] = ""
            st.rerun()

    st.divider()
    show_alerts()

    page = st.radio(
        "Navegacion",
        PAGES,
        key="nav_page",
        label_visibility="collapsed",
    )

# --- Routing ---
if page == "\u25c8 Dashboard":
    from modules.dashboard import render
elif page == "\U0001f50d Buscar":
    from modules.buscar import render
elif page == "\u25fb Notas":
    from modules.notas import render
elif page == "\u25f7 Tareas":
    from modules.tareas import render
elif page == "\u25c8 Proyectos":
    from modules.proyectos import render
elif page == "\u20a1 Finanzas":
    from modules.finanzas import render
elif page == "\u25ce Ahorros & Deudas":
    from modules.ahorros import render
elif page == "\u25c9 Habitos":
    from modules.habitos import render
elif page == "\U0001f4c5 Calendario":
    from modules.calendario import render
elif page == "\u25a3 Inventario":
    from modules.inventario import render
elif page == "\U0001f916 Buscar con IA":
    from modules.ia import render

render()
