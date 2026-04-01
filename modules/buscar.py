import streamlit as st
from core.data import get_df, save_df
from core.constants import AREA_LABELS, fmt
from core.utils import PRIORITY_EMOJIS, mark_task_done


def render():
    st.header("Buscar")
    st.caption("Busca en tareas, proyectos, transacciones, inventario, habitos y audios")

    col_search, col_filter = st.columns([4, 1])
    with col_search:
        search = st.text_input("Buscar...", placeholder="Escribe para buscar en todo tu cerebro", key="global_search")
    with col_filter:
        type_filter = st.selectbox("Filtrar por", ["Todos", "Tareas", "Proyectos", "Finanzas", "Inventario", "Habitos", "Audios", "Comentarios"],
                                   key="search_type_filter")

    if not search or not search.strip():
        st.info("Escribe algo para buscar en todos tus datos.")
        return

    query = search.strip().lower()
    results = []

    # Tareas
    if type_filter in ["Todos", "Tareas"]:
        tareas = get_df("tareas")
        if not tareas.empty:
            for _, t in tareas.iterrows():
                if query in t["titulo"].lower() or query in t.get("notas", "").lower() or query in t.get("subtareas", "").lower():
                    pri = PRIORITY_EMOJIS.get(t["prioridad"], "")
                    status = "✅" if t["done"] else "⬜"
                    results.append({"icon": status, "type": "Tarea", "name": f"{pri} {t['titulo']}", "detail": AREA_LABELS.get(t["area"], t["area"]), "ts": t["ts"], "id": t["id"], "done": t["done"], "proyecto": t.get("proyecto", "")})

    # Proyectos
    if type_filter in ["Todos", "Proyectos"]:
        proyectos = get_df("proyectos")
        if not proyectos.empty:
            for _, p in proyectos.iterrows():
                if query in p["nombre"].lower() or query in p.get("desc", "").lower():
                    emoji = p.get("emoji", "📁")
                    results.append({"icon": emoji, "type": "Proyecto", "name": p["nombre"], "detail": p.get("desc", "")[:60], "ts": p["ts"], "id": p["id"]})

    # Transacciones
    if type_filter in ["Todos", "Finanzas"]:
        txs = get_df("txs")
        if not txs.empty:
            for _, tx in txs.iterrows():
                if query in tx["desc"].lower() or query in tx["cat"].lower():
                    icon = "💰" if tx["type"] == "ingreso" else "💸"
                    results.append({"icon": icon, "type": tx["type"].capitalize(), "name": f"{fmt(tx['amt'])} - {tx['desc']}", "detail": f"{tx['cat']} | {tx['fecha']}", "ts": tx["ts"]})

    # Inventario
    if type_filter in ["Todos", "Inventario"]:
        inventario = get_df("inventario")
        if not inventario.empty:
            for _, item in inventario.iterrows():
                if query in item["name"].lower() or query in item.get("cat", "").lower() or query in item.get("notes", "").lower():
                    results.append({"icon": "📦", "type": "Inventario", "name": item["name"], "detail": f"{item['cat']} | {fmt(item['val'])}", "ts": item["ts"]})

    # Habitos
    if type_filter in ["Todos", "Habitos"]:
        habitos = get_df("habitos")
        if not habitos.empty:
            for _, h in habitos.iterrows():
                if query in h["name"].lower() or query in h.get("cat", "").lower():
                    emoji = h.get("emoji", "⭐")
                    results.append({"icon": emoji, "type": "Habito", "name": h["name"], "detail": f"{h['cat']} | {h['freq']}", "ts": h["ts"]})

    # Audios
    if type_filter in ["Todos", "Audios"]:
        audios = get_df("audios")
        if not audios.empty:
            for _, a in audios.iterrows():
                if query in a["titulo"].lower() or query in a.get("transcript", "").lower() or query in a.get("resumen", "").lower():
                    results.append({"icon": "🎤", "type": "Audio", "name": a["titulo"], "detail": a.get("resumen", "")[:60], "ts": a["ts"]})

    # Comments
    if type_filter in ["Todos", "Comentarios"]:
        comments = get_df("task_comments")
        if not comments.empty:
            for _, c in comments.iterrows():
                if query in c["texto"].lower():
                    results.append({"icon": "💬", "type": "Comentario", "name": c["texto"][:80], "detail": f"En tarea | {c['autor']}", "ts": c["ts"]})

    # Display results
    st.divider()
    st.subheader(f"{len(results)} resultado(s)")

    if not results:
        st.info("No se encontraron resultados.")
        return

    results.sort(key=lambda x: x["ts"], reverse=True)
    for i, r in enumerate(results):
        with st.container(border=True):
            col_info, col_actions = st.columns([5, 2])
            with col_info:
                st.markdown(f"{r['icon']} **{r['name']}** `{r['type']}`")
                if r["detail"]:
                    st.caption(r["detail"])
            with col_actions:
                _render_search_actions(r, i)


def _render_search_actions(result, index):
    """Render quick action buttons based on result type."""
    r_type = result["type"]
    r_id = result.get("id", "")

    if r_type == "Tarea" and r_id:
        c1, c2 = st.columns(2)
        with c1:
            if not result.get("done", False):
                if st.button("✅", key=f"sr_done_{index}", help="Completar", use_container_width=True):
                    tareas = get_df("tareas")
                    mark_task_done(tareas, r_id)
                    save_df("tareas", tareas)
                    st.rerun()
        with c2:
            if st.button("📂", key=f"sr_open_{index}", help="Abrir en proyecto", use_container_width=True):
                st.session_state["nav_page"] = "◈ Proyectos"
                if result.get("proyecto"):
                    st.session_state["proj_viewing"] = result["proyecto"]
                st.session_state["task_detail_id"] = r_id
                st.rerun()

    elif r_type == "Proyecto" and r_id:
        if st.button("📂 Abrir", key=f"sr_proj_{index}", use_container_width=True):
            st.session_state["nav_page"] = "◈ Proyectos"
            st.session_state["proj_viewing"] = r_id
            st.rerun()

    elif r_type == "Comentario":
        pass  # No direct action needed

    else:
        # For other types, show the type's page
        page_map = {
            "Ingreso": "₡ Finanzas", "Gasto": "₡ Finanzas",
            "Inventario": "◣ Inventario", "Habito": "◉ Habitos",
            "Audio": "🎤 Audios",
        }
        target = page_map.get(r_type)
        if target:
            if st.button("Ir", key=f"sr_go_{index}", use_container_width=True):
                st.session_state["nav_page"] = target
                st.rerun()
