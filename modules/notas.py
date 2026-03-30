import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, AREA_MAP
from core.utils import confirm_delete, export_csv, get_area_id


def render():
    st.header("Notas")

    notas = get_df("notas")

    # --- Toolbar ---
    col_search, col_filter, col_status, col_export, col_add = st.columns([3, 2, 1, 1, 1])
    with col_search:
        search = st.text_input("Buscar", placeholder="Buscar por titulo o contenido...", label_visibility="collapsed")
    with col_filter:
        filter_options = ["Todas"] + [f'{a["emoji"]} {a["name"]}' for a in AREAS]
        filt = st.selectbox("Area", filter_options, label_visibility="collapsed")
    with col_status:
        status = st.selectbox("Estado", ["Activas", "Fijadas", "Archivadas", "Todas"], label_visibility="collapsed", key="notas_status")
    with col_export:
        export_csv(notas, "notas.csv", "CSV")
    with col_add:
        add_nota = st.button("+ Nota", type="primary", use_container_width=True)

    # --- Filter logic ---
    filtered = notas.copy()
    if not filtered.empty:
        if status == "Activas":
            filtered = filtered[~filtered["archived"].fillna(False)]
        elif status == "Fijadas":
            filtered = filtered[filtered["pinned"].fillna(False)]
        elif status == "Archivadas":
            filtered = filtered[filtered["archived"].fillna(False)]

        if filt != "Todas":
            area_id = get_area_id(filt)
            if area_id:
                filtered = filtered[filtered["area"] == area_id]
        if search:
            mask = filtered["titulo"].str.contains(search, case=False, na=False) | filtered["body"].str.contains(search, case=False, na=False)
            filtered = filtered[mask]

        # Sort: pinned first, then by timestamp
        if "pinned" in filtered.columns:
            filtered["_pin"] = (~filtered["pinned"].fillna(False)).astype(int)
            filtered = filtered.sort_values(["_pin", "ts"], ascending=[True, False])
        else:
            filtered = filtered.sort_values("ts", ascending=False)

    # --- Add/Edit form ---
    if add_nota:
        st.session_state["nota_editing"] = True
        st.session_state["nota_edit_id"] = None

    if st.session_state.get("nota_editing"):
        edit_id = st.session_state.get("nota_edit_id")
        existing = None
        if edit_id and not notas.empty:
            matches = notas[notas["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("nota_form", clear_on_submit=True):
            st.subheader("Editar nota" if existing is not None else "Nueva nota")
            titulo = st.text_input("Titulo", value=existing["titulo"] if existing is not None else "")
            area_ids = [a["id"] for a in AREAS]
            area = st.selectbox(
                "Area", area_ids,
                format_func=lambda x: AREA_LABELS.get(x, x),
                index=area_ids.index(existing["area"]) if existing is not None and existing["area"] in area_ids else 0,
            )
            tags = st.text_input("Tags (separados por coma)", value=existing["tags"] if existing is not None else "")
            body = st.text_area("Contenido (soporta Markdown)", value=existing["body"] if existing is not None else "", height=200)

            col_save, col_cancel = st.columns(2)
            submitted = col_save.form_submit_button("Guardar", type="primary")
            cancelled = col_cancel.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                new_row = {
                    "id": edit_id or uid(),
                    "titulo": titulo.strip(),
                    "area": area,
                    "tags": tags,
                    "body": body,
                    "pinned": existing.get("pinned", False) if existing is not None else False,
                    "archived": existing.get("archived", False) if existing is not None else False,
                    "ts": now_ts(),
                }
                if edit_id and not notas.empty:
                    notas = notas[notas["id"] != edit_id]
                new_df = pd.concat([pd.DataFrame([new_row]), notas], ignore_index=True)
                save_df("notas", new_df)
                st.session_state["nota_editing"] = False
                st.session_state["nota_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["nota_editing"] = False
                st.session_state["nota_edit_id"] = None
                st.rerun()

    # --- Markdown reader view ---
    viewing_id = st.session_state.get("nota_viewing")
    if viewing_id and not notas.empty:
        matches = notas[notas["id"] == viewing_id]
        if not matches.empty:
            nota_view = matches.iloc[0]
            with st.container(border=True):
                st.markdown(f"## {nota_view['titulo']}")
                st.caption(f"{AREA_LABELS.get(nota_view['area'], nota_view['area'])}")
                if nota_view.get("tags"):
                    tags_list = [t.strip() for t in nota_view["tags"].split(",") if t.strip()]
                    st.markdown(" ".join([f"`{t}`" for t in tags_list]))
                st.divider()
                st.markdown(nota_view.get("body", ""))
                if st.button("Cerrar vista"):
                    st.session_state["nota_viewing"] = None
                    st.rerun()
            st.divider()

    # --- Display notes grid ---
    if filtered.empty:
        st.info("No hay notas. Crea tu primera nota con el boton '+ Nota'.")
        return

    cols = st.columns(3)
    for i, (_, nota) in enumerate(filtered.iterrows()):
        with cols[i % 3]:
            area_label = AREA_LABELS.get(nota["area"], nota["area"])
            preview = (nota["body"][:120] + "...") if len(nota.get("body", "")) > 120 else nota.get("body", "")
            is_pinned = nota.get("pinned", False)
            is_archived = nota.get("archived", False)

            with st.container(border=True):
                pin_icon = "📌 " if is_pinned else ""
                archive_icon = "📦 " if is_archived else ""
                st.markdown(f"**{pin_icon}{archive_icon}{nota['titulo']}**")
                if preview:
                    st.caption(preview)
                st.caption(f"{area_label}")
                if nota.get("tags"):
                    tags_list = [t.strip() for t in nota["tags"].split(",") if t.strip()]
                    st.caption(" ".join([f"`{t}`" for t in tags_list]))

                col_v, col_pin, col_arch, col_e, col_d = st.columns(5)
                with col_v:
                    if st.button("📖", key=f"view_{nota['id']}", use_container_width=True, help="Ver"):
                        st.session_state["nota_viewing"] = nota["id"]
                        st.rerun()
                with col_pin:
                    pin_label = "📌" if not is_pinned else "❌"
                    if st.button(pin_label, key=f"pin_{nota['id']}", use_container_width=True, help="Fijar" if not is_pinned else "Desfijar"):
                        notas.loc[notas["id"] == nota["id"], "pinned"] = not is_pinned
                        save_df("notas", notas)
                        st.rerun()
                with col_arch:
                    arch_label = "📦" if not is_archived else "📤"
                    if st.button(arch_label, key=f"arch_{nota['id']}", use_container_width=True, help="Archivar" if not is_archived else "Desarchivar"):
                        notas.loc[notas["id"] == nota["id"], "archived"] = not is_archived
                        save_df("notas", notas)
                        st.rerun()
                with col_e:
                    if st.button("✏️", key=f"edit_{nota['id']}", use_container_width=True, help="Editar"):
                        st.session_state["nota_editing"] = True
                        st.session_state["nota_edit_id"] = nota["id"]
                        st.rerun()
                with col_d:
                    if confirm_delete(nota["id"], nota["titulo"], "nota"):
                        notas = notas[notas["id"] != nota["id"]]
                        save_df("notas", notas)
                        st.rerun()
