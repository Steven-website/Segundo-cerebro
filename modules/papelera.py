import streamlit as st
import pandas as pd
import json
from datetime import datetime
from core.data import get_df, save_df


def render():
    st.header("Papelera")

    papelera = get_df("papelera")

    if papelera.empty:
        st.info("La papelera esta vacia.")
        return

    # Sort by most recently deleted
    papelera = papelera.sort_values("deleted_ts", ascending=False)

    st.caption(f"{len(papelera)} elemento(s) en la papelera")

    col_empty, _ = st.columns([1, 5])
    with col_empty:
        if st.button("Vaciar papelera", type="primary"):
            st.session_state["confirm_empty_trash"] = True

    if st.session_state.get("confirm_empty_trash"):
        st.warning("Esto eliminara permanentemente todos los elementos.")
        c1, c2 = st.columns(2)
        if c1.button("Si, vaciar todo", type="primary"):
            save_df("papelera", pd.DataFrame(columns=papelera.columns))
            st.session_state["confirm_empty_trash"] = False
            st.rerun()
        if c2.button("Cancelar"):
            st.session_state["confirm_empty_trash"] = False
            st.rerun()

    st.divider()

    tipo_icons = {
        "proyecto": "📁", "tarea": "☑️", "comentario": "💬",
        "transaccion": "💰", "habito": "◉", "inventario": "📦",
    }

    for _, item in papelera.iterrows():
        icon = tipo_icons.get(item["tipo"], "📄")
        ts = datetime.fromtimestamp(item["deleted_ts"]).strftime("%d/%m/%Y %H:%M") if item["deleted_ts"] else ""

        with st.container(border=True):
            col_info, col_actions = st.columns([5, 2])
            with col_info:
                st.markdown(f"{icon} **{item['nombre']}**")
                st.caption(f"{item['tipo'].capitalize()} — Eliminado: {ts}")
            with col_actions:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Restaurar", key=f"restore_{item['id']}", use_container_width=True):
                        _restore_item(item, papelera)
                        st.rerun()
                with c2:
                    if st.button("Eliminar", key=f"perm_del_{item['id']}", use_container_width=True):
                        papelera = papelera[papelera["id"] != item["id"]]
                        save_df("papelera", papelera)
                        st.rerun()


def _restore_item(trash_item, papelera):
    """Restore an item from papelera back to its original dataframe."""
    try:
        data = json.loads(trash_item["data"])
    except (json.JSONDecodeError, TypeError):
        st.error("No se pudo restaurar: datos corruptos.")
        return

    tipo = trash_item["tipo"]
    target_map = {
        "proyecto": "proyectos",
        "tarea": "tareas",
        "comentario": "task_comments",
        "transaccion": "txs",
        "habito": "habitos",
        "inventario": "inventario",
    }

    target_name = target_map.get(tipo)
    if not target_name:
        st.error(f"Tipo desconocido: {tipo}")
        return

    target_df = get_df(target_name)
    restored = pd.DataFrame([data])
    target_df = pd.concat([restored, target_df], ignore_index=True)
    save_df(target_name, target_df)

    # Remove from papelera
    papelera = papelera[papelera["id"] != trash_item["id"]]
    save_df("papelera", papelera)
    st.success(f"Restaurado: {trash_item['nombre']}")
