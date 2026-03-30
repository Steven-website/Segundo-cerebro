import streamlit as st
from core.data import get_df
from core.constants import AREA_LABELS, fmt
from core.utils import PRIORITY_EMOJIS


def render():
    st.header("Buscar")
    st.caption("Busca en todas tus notas, tareas, proyectos, transacciones, inventario y habitos")

    search = st.text_input("Buscar...", placeholder="Escribe para buscar en todo tu cerebro", key="global_search")

    # --- Tag search ---
    col_tag, col_spacer = st.columns([2, 4])
    with col_tag:
        tag_search = st.text_input("Buscar por tag", placeholder="#tag", key="tag_search")

    if not search and not tag_search:
        _show_tags_summary()
        return

    query = search.strip().lower() if search else ""
    tag_query = tag_search.strip().lower().replace("#", "") if tag_search else ""

    results = []

    # Notas
    notas = get_df("notas")
    if not notas.empty:
        for _, n in notas.iterrows():
            match = False
            if query and (query in n["titulo"].lower() or query in n.get("body", "").lower() or query in n.get("tags", "").lower()):
                match = True
            if tag_query and tag_query in n.get("tags", "").lower():
                match = True
            if match:
                area_label = AREA_LABELS.get(n["area"], n["area"])
                tags_display = f" | Tags: {n['tags']}" if n.get("tags") else ""
                results.append({"icon": "📝", "type": "Nota", "name": n["titulo"], "detail": f"{area_label}{tags_display}", "ts": n["ts"]})

    # Tareas
    tareas = get_df("tareas")
    if not tareas.empty:
        for _, t in tareas.iterrows():
            match = False
            if query and (query in t["titulo"].lower() or query in t.get("notas", "").lower()):
                match = True
            if match:
                pri = PRIORITY_EMOJIS.get(t["prioridad"], "")
                status = "✅" if t["done"] else "⬜"
                results.append({"icon": status, "type": "Tarea", "name": f"{pri} {t['titulo']}", "detail": AREA_LABELS.get(t["area"], t["area"]), "ts": t["ts"]})

    # Proyectos
    proyectos = get_df("proyectos")
    if not proyectos.empty:
        for _, p in proyectos.iterrows():
            match = False
            if query and (query in p["nombre"].lower() or query in p.get("desc", "").lower()):
                match = True
            if match:
                emoji = p.get("emoji", "📁")
                results.append({"icon": emoji, "type": "Proyecto", "name": p["nombre"], "detail": p.get("desc", "")[:60], "ts": p["ts"]})

    # Transacciones
    txs = get_df("txs")
    if not txs.empty:
        for _, tx in txs.iterrows():
            if query and (query in tx["desc"].lower() or query in tx["cat"].lower()):
                icon = "💰" if tx["type"] == "ingreso" else "💸"
                results.append({"icon": icon, "type": tx["type"].capitalize(), "name": f"{fmt(tx['amt'])} - {tx['desc']}", "detail": f"{tx['cat']} | {tx['fecha']}", "ts": tx["ts"]})

    # Inventario
    inventario = get_df("inventario")
    if not inventario.empty:
        for _, item in inventario.iterrows():
            if query and (query in item["name"].lower() or query in item.get("cat", "").lower() or query in item.get("notes", "").lower()):
                results.append({"icon": "📦", "type": "Inventario", "name": item["name"], "detail": f"{item['cat']} | {fmt(item['val'])}", "ts": item["ts"]})

    # Habitos
    habitos = get_df("habitos")
    if not habitos.empty:
        for _, h in habitos.iterrows():
            if query and (query in h["name"].lower() or query in h.get("cat", "").lower()):
                emoji = h.get("emoji", "⭐")
                results.append({"icon": emoji, "type": "Habito", "name": h["name"], "detail": f"{h['cat']} | {h['freq']}", "ts": h["ts"]})

    # Audios
    audios = get_df("audios")
    if not audios.empty:
        for _, a in audios.iterrows():
            if query and (query in a["titulo"].lower() or query in a.get("transcript", "").lower() or query in a.get("resumen", "").lower()):
                results.append({"icon": "🎤", "type": "Audio", "name": a["titulo"], "detail": a.get("resumen", "")[:60], "ts": a["ts"]})

    # Display results
    st.divider()
    st.subheader(f"{len(results)} resultado(s)")

    if not results:
        st.info("No se encontraron resultados.")
        return

    results.sort(key=lambda x: x["ts"], reverse=True)
    for r in results:
        with st.container(border=True):
            st.markdown(f"{r['icon']} **{r['name']}** `{r['type']}`")
            if r["detail"]:
                st.caption(r["detail"])


def _show_tags_summary():
    """Show all unique tags across notas."""
    st.divider()
    st.subheader("Tags")

    notas = get_df("notas")
    if notas.empty:
        st.info("No hay tags. Agrega tags a tus notas para verlos aqui.")
        return

    all_tags = {}
    for _, n in notas.iterrows():
        if n.get("tags"):
            for tag in n["tags"].split(","):
                tag = tag.strip()
                if tag:
                    all_tags[tag] = all_tags.get(tag, 0) + 1

    if not all_tags:
        st.info("No hay tags. Agrega tags a tus notas para verlos aqui.")
        return

    sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
    tag_cols = st.columns(4)
    for i, (tag, count) in enumerate(sorted_tags):
        with tag_cols[i % 4]:
            st.markdown(f"`{tag}` ({count})")
