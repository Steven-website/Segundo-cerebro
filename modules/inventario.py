import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import INV_CATS, INV_CAT_ICONS, INV_STATUS, fmt
from core.utils import confirm_delete, export_csv


def render():
    st.header("Inventario del Hogar")

    inventario = get_df("inventario")

    # --- Toolbar ---
    col_filter, col_search, col_export, col_add = st.columns([2, 3, 1, 1])
    with col_filter:
        cat_options = ["Todas"] + INV_CATS
        cat_filter = st.selectbox("Categoria", cat_options, label_visibility="collapsed")
    with col_search:
        search = st.text_input("Buscar", placeholder="Buscar item...", label_visibility="collapsed")
    with col_export:
        export_csv(inventario, "inventario.csv", "\U0001f4e5 CSV")
    with col_add:
        if st.button("+ Item", type="primary", use_container_width=True):
            st.session_state["inv_editing"] = True
            st.session_state["inv_edit_id"] = None

    # --- Add/Edit form ---
    if st.session_state.get("inv_editing"):
        edit_id = st.session_state.get("inv_edit_id")
        existing = None
        if edit_id and not inventario.empty:
            matches = inventario[inventario["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("inv_form", clear_on_submit=True):
            st.subheader("Editar item" if existing is not None else "Nuevo item")
            c1, c2 = st.columns([3, 1])
            name = c1.text_input("Nombre", value=existing["name"] if existing is not None else "")
            emoji = c2.text_input("Emoji", value=existing.get("emoji", "\U0001f4e6") if existing is not None else "\U0001f4e6")

            c3, c4, c5 = st.columns(3)
            cat = c3.selectbox("Categoria", INV_CATS, format_func=lambda x: f"{INV_CAT_ICONS.get(x, '')} {x.capitalize()}",
                               index=INV_CATS.index(existing["cat"]) if existing is not None and existing["cat"] in INV_CATS else 0)
            val = c4.number_input("Valor (\u20a1)", min_value=0.0, step=5000.0, value=float(existing["val"]) if existing is not None else 0.0)
            qty = c5.number_input("Cantidad", min_value=1, step=1, value=int(existing["qty"]) if existing is not None else 1)

            c6, c7 = st.columns(2)
            loc = c6.text_input("Ubicacion", value=existing.get("loc", "") if existing is not None else "")
            status_opts = ["bueno", "regular", "malo"]
            status = c7.selectbox("Estado", status_opts, format_func=lambda x: f"{INV_STATUS.get(x, '')} {x.capitalize()}",
                                  index=status_opts.index(existing["status"]) if existing is not None and existing.get("status") in status_opts else 0)

            date = st.date_input("Fecha de compra (opcional)", value=None)
            notes = st.text_input("Notas (serial, garantia, etc.)", value=existing.get("notes", "") if existing is not None else "")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip():
                new_row = {
                    "id": edit_id or uid(), "name": name.strip(), "cat": cat,
                    "emoji": emoji or "\U0001f4e6", "val": val, "qty": qty,
                    "loc": loc, "date": str(date) if date else "",
                    "notes": notes, "status": status, "ts": now_ts(),
                }
                if edit_id and not inventario.empty:
                    inventario = inventario[inventario["id"] != edit_id]
                save_df("inventario", pd.concat([pd.DataFrame([new_row]), inventario], ignore_index=True))
                st.session_state["inv_editing"] = False
                st.session_state["inv_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["inv_editing"] = False
                st.session_state["inv_edit_id"] = None
                st.rerun()

    # --- Filter ---
    filtered = inventario.copy()
    if not filtered.empty:
        if cat_filter != "Todas":
            filtered = filtered[filtered["cat"] == cat_filter]
        if search:
            filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]

    # --- Summary ---
    if not inventario.empty:
        total_items = len(inventario)
        total_value = (inventario["val"] * inventario["qty"]).sum()
        st.caption(f"{total_items} items \u2022 Valor total: {fmt(total_value)}")
    st.divider()

    # --- Display ---
    if filtered.empty:
        st.info("No hay items en el inventario.")
        return

    cols = st.columns(3)
    for i, (_, item) in enumerate(filtered.iterrows()):
        with cols[i % 3]:
            cat_icon = INV_CAT_ICONS.get(item["cat"], "\U0001f4e6")
            status_icon = INV_STATUS.get(item.get("status", "bueno"), "\U0001f7e2")

            with st.container(border=True):
                item_emoji = item.get('emoji', '\U0001f4e6')
                st.markdown(f"### {item_emoji} {item['name']}")
                st.caption(f"{cat_icon} {item['cat'].capitalize()}")

                if item.get("loc"):
                    st.markdown(f"\U0001f4cd {item['loc']}")

                c1, c2 = st.columns(2)
                c1.markdown(f"**{fmt(item['val'])}** x{item['qty']}")
                c2.markdown(f"{status_icon} {item.get('status', 'bueno').capitalize()}")

                if item.get("notes"):
                    st.caption(item["notes"])

                c_edit, c_del = st.columns(2)
                with c_edit:
                    if st.button("\u270f\ufe0f Editar", key=f"invedit_{item['id']}", use_container_width=True):
                        st.session_state["inv_editing"] = True
                        st.session_state["inv_edit_id"] = item["id"]
                        st.rerun()
                with c_del:
                    if confirm_delete(item["id"], item["name"], "inv"):
                        inventario = inventario[inventario["id"] != item["id"]]
                        save_df("inventario", inventario)
                        st.rerun()
