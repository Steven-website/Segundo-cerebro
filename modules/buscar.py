import streamlit as st
from core.data import get_df
from core.constants import AREA_LABELS, CAT_ICONS, INV_CAT_ICONS, fmt


def render():
    st.header("\U0001f50d Busqueda global")

    query = st.text_input("Buscar en todo tu segundo cerebro...", placeholder="Escribe para buscar en notas, tareas, proyectos, inventario, transacciones...")

    if not query or not query.strip():
        st.info("Escribe algo para buscar en todas tus notas, tareas, proyectos, inventario y transacciones.")
        return

    q = query.strip().lower()
    results_found = False

    # --- Notas ---
    notas = get_df("notas")
    if not notas.empty:
        mask = notas["titulo"].str.lower().str.contains(q, na=False) | notas["body"].str.lower().str.contains(q, na=False) | notas["tags"].str.lower().str.contains(q, na=False)
        matches = notas[mask]
        if not matches.empty:
            results_found = True
            st.subheader(f"\U0001f4dd Notas ({len(matches)})")
            for _, n in matches.iterrows():
                area = AREA_LABELS.get(n["area"], n["area"])
                preview = (n["body"][:100] + "...") if len(n.get("body", "")) > 100 else n.get("body", "")
                with st.container(border=True):
                    st.markdown(f"**{n['titulo']}** \u2022 {area}")
                    if preview:
                        st.caption(preview)

    # --- Tareas ---
    tareas = get_df("tareas")
    if not tareas.empty:
        mask = tareas["titulo"].str.lower().str.contains(q, na=False) | tareas["notas"].str.lower().str.contains(q, na=False)
        matches = tareas[mask]
        if not matches.empty:
            results_found = True
            st.subheader(f"\u25f7 Tareas ({len(matches)})")
            for _, t in matches.iterrows():
                status = "\u2705" if t["done"] else "\u2b1c"
                area = AREA_LABELS.get(t["area"], t["area"])
                st.markdown(f"{status} **{t['titulo']}** \u2022 {area} \u2022 {t['prioridad']}")

    # --- Proyectos ---
    proyectos = get_df("proyectos")
    if not proyectos.empty:
        mask = proyectos["nombre"].str.lower().str.contains(q, na=False) | proyectos["desc"].str.lower().str.contains(q, na=False)
        matches = proyectos[mask]
        if not matches.empty:
            results_found = True
            st.subheader(f"\u25c8 Proyectos ({len(matches)})")
            for _, p in matches.iterrows():
                proj_emoji = p.get("emoji", "\U0001f4c1")
                st.markdown(f"{proj_emoji} **{p['nombre']}** \u2022 {p.get('desc', '')[:80]}")

    # --- Transacciones ---
    txs = get_df("txs")
    if not txs.empty:
        mask = txs["desc"].str.lower().str.contains(q, na=False) | txs["cat"].str.lower().str.contains(q, na=False)
        matches = txs[mask]
        if not matches.empty:
            results_found = True
            st.subheader(f"\u20a1 Transacciones ({len(matches)})")
            for _, tx in matches.head(10).iterrows():
                icon = CAT_ICONS.get(tx["cat"], "\U0001f4e6")
                sign = "+" if tx["type"] == "ingreso" else "-"
                color = "green" if tx["type"] == "ingreso" else "red"
                st.markdown(f"{icon} {tx['desc']} \u2022 :{color}[{sign}{fmt(tx['amt'])}] \u2022 `{tx['fecha']}`")

    # --- Inventario ---
    inventario = get_df("inventario")
    if not inventario.empty:
        mask = inventario["name"].str.lower().str.contains(q, na=False) | inventario["cat"].str.lower().str.contains(q, na=False) | inventario["notes"].str.lower().str.contains(q, na=False)
        matches = inventario[mask]
        if not matches.empty:
            results_found = True
            st.subheader(f"\u25a3 Inventario ({len(matches)})")
            for _, item in matches.iterrows():
                item_emoji = item.get("emoji", "\U0001f4e6")
                st.markdown(f"{item_emoji} **{item['name']}** \u2022 {fmt(item['val'])} \u2022 {item.get('loc', '')}")

    # --- Habitos ---
    habitos = get_df("habitos")
    if not habitos.empty:
        mask = habitos["name"].str.lower().str.contains(q, na=False)
        matches = habitos[mask]
        if not matches.empty:
            results_found = True
            st.subheader(f"\u25c9 Habitos ({len(matches)})")
            for _, h in matches.iterrows():
                hab_emoji = h.get("emoji", "\u2b50")
                st.markdown(f"{hab_emoji} **{h['name']}** \u2022 {h['freq']}")

    if not results_found:
        st.warning(f"No se encontraron resultados para '{query}'.")
