import streamlit as st
from core.styles import inject_css

st.set_page_config(
    page_title="Segundo Cerebro",
    page_icon="\U0001f9e0",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

# Sidebar
with st.sidebar:
    st.markdown("### \U0001f9e0 Segundo Cerebro")
    st.caption("v3 \u2022 PKM Personal")
    st.divider()

    page = st.radio(
        "Navegacion",
        [
            "\u25c8 Dashboard",
            "\u25fb Notas",
            "\u25f7 Tareas",
            "\u25c8 Proyectos",
            "\u20a1 Finanzas",
            "\u25ce Ahorros & Deudas",
            "\u25c9 Habitos",
            "\u25a3 Inventario",
            "\U0001f916 Buscar con IA",
        ],
        label_visibility="collapsed",
    )

# Routing
if page == "\u25c8 Dashboard":
    from modules.dashboard import render
    render()
elif page == "\u25fb Notas":
    from modules.notas import render
    render()
elif page == "\u25f7 Tareas":
    from modules.tareas import render
    render()
elif page == "\u25c8 Proyectos":
    from modules.proyectos import render
    render()
elif page == "\u20a1 Finanzas":
    from modules.finanzas import render
    render()
elif page == "\u25ce Ahorros & Deudas":
    from modules.ahorros import render
    render()
elif page == "\u25c9 Habitos":
    from modules.habitos import render
    render()
elif page == "\u25a3 Inventario":
    from modules.inventario import render
    render()
elif page == "\U0001f916 Buscar con IA":
    from modules.ia import render
    render()
