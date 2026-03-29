import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import INV_CATS, INV_CAT_ICONS, INV_STATUS, fmt


def render():
    st.header("Inventario del Hogar")

    inventario = get_df("inventario")

    # --- Toolbar ---
    col_filter, col_search, col_add = st.columns([2, 3, 1])
    with col_filter:
        cat_options = ["Todas"] + INV_CATS
        cat_filter = st.selectbox("Categoria", cat_options, label_visibility="collapsed")
    with col_search:
        search = st.text_input("Buscar", placeholder="Buscar item...", label_visibility="collapsed")
    with col_add:
        if st.button("+ Item", type="primary", use_container_width=True):
            st.session_state["inv_adding"] = True

    # --- Add form ---
    if st.session_state.get("inv_adding"):
        with st.form("inv_form", clear_on_submit=True):
            st.subheader("Nuevo item")
            c1, c2 = st.columns([3, 1])
            name = c1.text_input("Nombre")
            emoji = c2.text_input("Emoji", value="\U0001f4e6")

            c3, c4, c5 = st.columns(3)
            cat = c3.selectbox("Categoria", INV_CATS, format_func=lambda x: f"{INV_CAT_ICONS.get(x, '')} {x.capitalize()}")
            val = c4.number_input("Valor estimado (\u20a1)", min_value=0.0, step=5000.0)
            qty = c5.number_input("Cantidad", min_value=1, step=1, value=1)

            c6, c7 = st.columns(2)
            loc = c6.text_input("Ubicacion")
            status = c7.selectbox("Estado", ["bueno", "regular", "malo"], format_func=lambda x: f"{INV_STATUS.get(x, '')} {x.capitalize()}")

            date = st.date_input("Fecha de compra (opcional)", value=None)
            notes = st.text_input("Notas (serial, garantia, etc.)")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip():
                new_row = {
                    "id": uid(), "name": name.strip(), "cat": cat,
                    "emoji": emoji or "\U0001f4e6", "val": val, "qty": qty,
                    "loc": loc, "date": str(date) if date else "",
                    "notes": notes, "status": status, "ts": now_ts(),
                }
                save_df("inventario", pd.concat([pd.DataFrame([new_row]), inventario], ignore_index=True))
                st.session_state["inv_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["inv_adding"] = False
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

                if st.button("\U0001f5d1 Eliminar", key=f"invdel_{item['id']}", use_container_width=True):
                    inventario = inventario[inventario["id"] != item["id"]]
                    save_df("inventario", inventario)
                    st.rerun()
