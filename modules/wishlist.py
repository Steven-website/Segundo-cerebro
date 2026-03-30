import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import fmt
from core.utils import confirm_delete


# --- Exchange rate ---
TIPO_CAMBIO_DEFAULT = 510.0  # fallback CRC per USD


def _get_tipo_cambio():
    """Get USD→CRC exchange rate. Caches for the session."""
    if "tipo_cambio" in st.session_state:
        return st.session_state["tipo_cambio"]
    try:
        import urllib.request
        import json
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            rate = float(data["rates"].get("CRC", TIPO_CAMBIO_DEFAULT))
            st.session_state["tipo_cambio"] = rate
            return rate
    except Exception:
        st.session_state["tipo_cambio"] = TIPO_CAMBIO_DEFAULT
        return TIPO_CAMBIO_DEFAULT


def _fmt_usd(val):
    return f"${val:,.2f}"


def render():
    st.header("Lista de deseos")

    cats = get_df("wishlist_cats")
    items = get_df("wishlist")
    tc = _get_tipo_cambio()

    st.caption(f"Tipo de cambio: **1 USD = ₡{tc:,.0f}**")

    # ═══ MANAGE CATEGORIES ═══
    col_add_cat, col_add_item = st.columns(2)
    with col_add_cat:
        if st.button("+ Segmento", use_container_width=True):
            st.session_state["wl_cat_editing"] = True
            st.session_state["wl_cat_edit_id"] = None
    with col_add_item:
        if st.button("+ Articulo", use_container_width=True, type="primary"):
            st.session_state["wl_item_editing"] = True
            st.session_state["wl_item_edit_id"] = None

    # --- Category form ---
    if st.session_state.get("wl_cat_editing"):
        edit_id = st.session_state.get("wl_cat_edit_id")
        existing = None
        if edit_id and not cats.empty:
            matches = cats[cats["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("wl_cat_form", clear_on_submit=True):
            st.subheader("Editar segmento" if existing is not None else "Nuevo segmento")
            c1, c2 = st.columns([3, 1])
            nombre = c1.text_input("Nombre", value=existing["nombre"] if existing is not None else "", placeholder="Ej: Camisas, Zapatos...")
            emoji = c2.text_input("Emoji", value=existing.get("emoji", "") if existing is not None else "🛍️", max_chars=4)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and nombre.strip():
                orden = int(existing.get("orden", 0)) if existing is not None else (len(cats) + 1)
                new_row = {
                    "id": edit_id or uid(), "nombre": nombre.strip(),
                    "emoji": emoji.strip() or "🛍️", "orden": orden, "ts": now_ts(),
                }
                if edit_id and not cats.empty:
                    cats = cats[cats["id"] != edit_id]
                cats = pd.concat([pd.DataFrame([new_row]), cats], ignore_index=True)
                save_df("wishlist_cats", cats)
                st.session_state["wl_cat_editing"] = False
                st.session_state["wl_cat_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["wl_cat_editing"] = False
                st.session_state["wl_cat_edit_id"] = None
                st.rerun()

    # --- Item form ---
    if st.session_state.get("wl_item_editing"):
        edit_id = st.session_state.get("wl_item_edit_id")
        existing = None
        if edit_id and not items.empty:
            matches = items[items["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        if cats.empty:
            st.warning("Crea al menos un segmento primero.")
            st.session_state["wl_item_editing"] = False
        else:
            with st.form("wl_item_form", clear_on_submit=True):
                st.subheader("Editar articulo" if existing is not None else "Nuevo articulo")

                nombre = st.text_input("Nombre", value=existing["nombre"] if existing is not None else "")

                # Category selector
                cat_ids = cats["id"].tolist()
                cat_labels = [f"{r['emoji']} {r['nombre']}" for _, r in cats.iterrows()]
                cat_idx = 0
                if existing is not None and existing.get("cat_id") in cat_ids:
                    cat_idx = cat_ids.index(existing["cat_id"])
                cat_id = st.selectbox("Segmento", cat_ids, index=cat_idx, format_func=lambda x: cat_labels[cat_ids.index(x)])

                link = st.text_input("Link de compra", value=existing.get("link", "") if existing is not None else "", placeholder="https://...")
                imagen = st.text_input("URL de imagen", value=existing.get("imagen", "") if existing is not None else "", placeholder="https://...imagen.jpg")

                # Price inputs
                st.caption("Ingresa el precio en dolares O colones — el otro se calcula automatico.")
                c_usd, c_crc = st.columns(2)
                default_usd = float(existing["precio_usd"]) if existing is not None and existing.get("precio_usd", 0) > 0 else 0.0
                default_crc = float(existing["precio_crc"]) if existing is not None and existing.get("precio_crc", 0) > 0 else 0.0
                precio_usd = c_usd.number_input("Precio USD ($)", min_value=0.0, step=5.0, value=default_usd)
                precio_crc = c_crc.number_input("Precio CRC (₡)", min_value=0.0, step=1000.0, value=default_crc)

                prioridad = st.selectbox("Prioridad", ["alta", "media", "baja"],
                                         index=["alta", "media", "baja"].index(existing["prioridad"]) if existing is not None and existing.get("prioridad") in ["alta", "media", "baja"] else 1,
                                         format_func=lambda x: {"alta": "🔴 Alta", "media": "🟡 Media", "baja": "🟢 Baja"}[x])
                notas = st.text_area("Notas", value=existing.get("notas", "") if existing is not None else "", height=80)

                col_s, col_c = st.columns(2)
                submitted = col_s.form_submit_button("Guardar", type="primary")
                cancelled = col_c.form_submit_button("Cancelar")

                if submitted and nombre.strip():
                    # Auto-convert prices
                    final_usd = precio_usd
                    final_crc = precio_crc
                    if final_usd > 0 and final_crc == 0:
                        final_crc = round(final_usd * tc, 2)
                    elif final_crc > 0 and final_usd == 0:
                        final_usd = round(final_crc / tc, 2)

                    new_row = {
                        "id": edit_id or uid(), "cat_id": cat_id,
                        "nombre": nombre.strip(), "link": link.strip(),
                        "imagen": imagen.strip(), "precio_usd": final_usd,
                        "precio_crc": final_crc, "prioridad": prioridad,
                        "comprado": existing.get("comprado", False) if existing is not None else False,
                        "notas": notas.strip(), "ts": now_ts(),
                    }
                    if edit_id and not items.empty:
                        items = items[items["id"] != edit_id]
                    items = pd.concat([pd.DataFrame([new_row]), items], ignore_index=True)
                    save_df("wishlist", items)
                    st.session_state["wl_item_editing"] = False
                    st.session_state["wl_item_edit_id"] = None
                    st.rerun()
                if cancelled:
                    st.session_state["wl_item_editing"] = False
                    st.session_state["wl_item_edit_id"] = None
                    st.rerun()

    st.divider()

    # ═══ DISPLAY BY CATEGORY ═══
    if cats.empty:
        st.info("Crea tu primer segmento con el boton '+ Segmento'.")
        return

    # Summary
    if not items.empty:
        pending = items[~items["comprado"].fillna(False)]
        total_usd = pending["precio_usd"].sum()
        total_crc = pending["precio_crc"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Articulos pendientes", len(pending))
        c2.metric("Total USD", _fmt_usd(total_usd))
        c3.metric("Total CRC", fmt(total_crc))
        st.divider()

    sorted_cats = cats.sort_values("orden") if not cats.empty else cats

    for _, cat in sorted_cats.iterrows():
        cat_items = items[items["cat_id"] == cat["id"]] if not items.empty else pd.DataFrame()
        pending_items = cat_items[~cat_items["comprado"].fillna(False)] if not cat_items.empty else pd.DataFrame()
        bought_items = cat_items[cat_items["comprado"].fillna(False)] if not cat_items.empty else pd.DataFrame()

        with st.expander(f"{cat['emoji']} {cat['nombre']} ({len(pending_items)} pendientes)", expanded=len(pending_items) > 0):
            # Category actions
            ca, cb = st.columns([1, 1])
            with ca:
                if st.button("✏️ Editar segmento", key=f"wl_cat_edit_{cat['id']}", use_container_width=True):
                    st.session_state["wl_cat_editing"] = True
                    st.session_state["wl_cat_edit_id"] = cat["id"]
                    st.rerun()
            with cb:
                if confirm_delete(cat["id"], cat["nombre"], "wl_cat"):
                    cats = cats[cats["id"] != cat["id"]]
                    save_df("wishlist_cats", cats)
                    # Also delete items in this category
                    if not items.empty:
                        items = items[items["cat_id"] != cat["id"]]
                        save_df("wishlist", items)
                    st.rerun()

            # Pending items
            pri_order = {"alta": 0, "media": 1, "baja": 2}
            if not pending_items.empty:
                pending_items = pending_items.copy()
                pending_items["_pri"] = pending_items["prioridad"].map(pri_order).fillna(1)
                pending_items = pending_items.sort_values("_pri")

            for _, item in pending_items.iterrows():
                _render_item(item, items, tc)

            # Bought items
            if not bought_items.empty:
                st.caption(f"✅ Comprados ({len(bought_items)})")
                for _, item in bought_items.iterrows():
                    _render_item(item, items, tc, bought=True)


def _render_item(item, items_df, tc, bought=False):
    """Render a single wishlist item."""
    pri_icons = {"alta": "🔴", "media": "🟡", "baja": "🟢"}
    pri = pri_icons.get(item.get("prioridad", "media"), "🟡")

    with st.container(border=True):
        # Image if available
        if item.get("imagen") and str(item["imagen"]).startswith("http"):
            try:
                st.image(item["imagen"], width=120)
            except Exception:
                pass

        status = "~~" if bought else ""
        st.markdown(f"{pri} {status}**{item['nombre']}**{status}")

        # Prices
        usd = item.get("precio_usd", 0) or 0
        crc = item.get("precio_crc", 0) or 0
        if usd > 0 or crc > 0:
            st.markdown(f"💲 {_fmt_usd(usd)} — ₡{crc:,.0f}")

        # Link
        if item.get("link") and str(item["link"]).startswith("http"):
            st.markdown(f"[🔗 Comprar]({item['link']})")

        # Notes
        if item.get("notas"):
            st.caption(item["notas"])

        # Actions
        c1, c2, c3 = st.columns(3)
        with c1:
            check_label = "Desmarcar" if bought else "✅ Comprado"
            if st.button(check_label, key=f"wl_buy_{item['id']}", use_container_width=True):
                items_df.loc[items_df["id"] == item["id"], "comprado"] = not bought
                save_df("wishlist", items_df)
                st.rerun()
        with c2:
            if st.button("✏️", key=f"wl_edit_{item['id']}", use_container_width=True):
                st.session_state["wl_item_editing"] = True
                st.session_state["wl_item_edit_id"] = item["id"]
                st.rerun()
        with c3:
            if confirm_delete(item["id"], item["nombre"], "wl_item"):
                items_df = items_df[items_df["id"] != item["id"]]
                save_df("wishlist", items_df)
                st.rerun()
