import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts


BOOK_CATS = ["Ficcion", "No ficcion", "Negocios", "Desarrollo personal", "Tecnologia", "Ciencia", "Historia", "Biografia", "Otro"]
BOOK_STATES = {"leyendo": "Leyendo", "pendiente": "Pendiente", "completado": "Completado", "abandonado": "Abandonado"}


def render():
    st.header("Lectura")

    books = get_df("books")
    sessions = get_df("reading_sessions")

    # --- Metrics ---
    _render_metrics(books, sessions)

    st.divider()

    tab_books, tab_stats = st.tabs(["Mis libros", "Estadisticas"])

    with tab_books:
        _render_books(books, sessions)

    with tab_stats:
        _render_stats(books, sessions)


def _render_metrics(books, sessions):
    now = datetime.now()
    month_prefix = now.strftime("%Y-%m")

    reading_now = len(books[books["estado"] == "leyendo"]) if not books.empty else 0
    completed = len(books[books["estado"] == "completado"]) if not books.empty else 0
    month_mins = int(sessions[sessions["fecha"].str.startswith(month_prefix)]["minutos"].sum()) if not sessions.empty else 0
    month_pages = int(sessions[sessions["fecha"].str.startswith(month_prefix)]["paginas"].sum()) if not sessions.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leyendo", reading_now)
    c2.metric("Completados", completed)
    c3.metric("Min este mes", month_mins)
    c4.metric("Pag este mes", month_pages)


def _render_books(books, sessions):
    # --- Add book ---
    if st.button("+ Libro", type="primary", use_container_width=True):
        st.session_state["book_adding"] = True

    if st.session_state.get("book_adding"):
        with st.form("add_book_form", clear_on_submit=True):
            st.subheader("Nuevo libro")
            c1, c2 = st.columns(2)
            titulo = c1.text_input("Titulo")
            autor = c2.text_input("Autor")
            c3, c4 = st.columns(2)
            paginas = c3.number_input("Total paginas", min_value=1, value=200)
            categoria = c4.selectbox("Categoria", BOOK_CATS)
            estado = st.selectbox("Estado", list(BOOK_STATES.keys()), format_func=lambda x: BOOK_STATES[x])

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and titulo.strip():
                new_book = {
                    "id": uid(), "titulo": titulo.strip(), "autor": autor.strip(),
                    "paginas": paginas, "paginas_leidas": 0, "estado": estado,
                    "categoria": categoria, "fecha_inicio": datetime.now().strftime("%Y-%m-%d") if estado == "leyendo" else "",
                    "fecha_fin": "", "rating": 0, "notas": "", "ts": now_ts(),
                }
                books = pd.concat([pd.DataFrame([new_book]), books], ignore_index=True)
                save_df("books", books)
                st.session_state["book_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["book_adding"] = False
                st.rerun()

    if books.empty:
        st.info("No hay libros registrados. Agrega uno con '+ Libro'.")
        return

    # --- Filter by state ---
    filter_state = st.pills("Filtro", ["Todos"] + list(BOOK_STATES.values()),
                            default="Todos", label_visibility="collapsed", key="book_filter")

    state_key = None
    if filter_state and filter_state != "Todos":
        state_key = [k for k, v in BOOK_STATES.items() if v == filter_state][0]

    filtered = books[books["estado"] == state_key] if state_key else books

    if filtered.empty:
        st.info("No hay libros en esta categoria.")
        return

    # --- Display books ---
    for _, book in filtered.iterrows():
        _render_book_card(book, books, sessions)


def _render_book_card(book, books, sessions):
    pct = int(book["paginas_leidas"] / book["paginas"] * 100) if book["paginas"] > 0 else 0
    state_icons = {"leyendo": "📖", "pendiente": "📚", "completado": "✅", "abandonado": "⏸️"}
    icon = state_icons.get(book["estado"], "📕")

    with st.container(border=True):
        col_info, col_pct = st.columns([5, 1])
        with col_info:
            st.markdown(f"{icon} **{book['titulo']}**")
            st.caption(f"{book['autor']} | {book['categoria']} | {book['paginas_leidas']}/{book['paginas']} pag")
        with col_pct:
            st.markdown(f"**{pct}%**")

        if book["estado"] == "leyendo":
            st.progress(min(pct / 100, 1.0))

        # Stars rating
        if book["estado"] == "completado" and book["rating"] > 0:
            stars = "⭐" * int(book["rating"])
            st.caption(stars)

        with st.expander("Detalles"):
            # --- Log reading session ---
            if book["estado"] == "leyendo":
                st.markdown("**Registrar lectura**")
                with st.form(f"session_form_{book['id']}", clear_on_submit=True):
                    sc1, sc2 = st.columns(2)
                    s_fecha = sc1.date_input("Fecha", value=datetime.now().date(), key=f"sf_{book['id']}")
                    s_mins = sc2.number_input("Minutos", min_value=1, value=30, key=f"sm_{book['id']}")
                    sc3, sc4 = st.columns(2)
                    s_pags = sc3.number_input("Paginas leidas", min_value=0, value=0, key=f"sp_{book['id']}")
                    s_notas = sc4.text_input("Notas", key=f"sn_{book['id']}", placeholder="Opcional")

                    if st.form_submit_button("Registrar", type="primary", use_container_width=True):
                        new_session = {
                            "id": uid(), "book_id": book["id"],
                            "fecha": s_fecha.strftime("%Y-%m-%d"),
                            "minutos": s_mins, "paginas": s_pags,
                            "notas": s_notas.strip(), "ts": now_ts(),
                        }
                        sessions = get_df("reading_sessions")
                        sessions = pd.concat([pd.DataFrame([new_session]), sessions], ignore_index=True)
                        save_df("reading_sessions", sessions)

                        # Update pages read
                        new_total = int(book["paginas_leidas"]) + s_pags
                        books.loc[books["id"] == book["id"], "paginas_leidas"] = min(new_total, int(book["paginas"]))

                        # Auto-complete if all pages read
                        if new_total >= int(book["paginas"]):
                            books.loc[books["id"] == book["id"], "estado"] = "completado"
                            books.loc[books["id"] == book["id"], "fecha_fin"] = datetime.now().strftime("%Y-%m-%d")

                        save_df("books", books)
                        st.rerun()

                st.divider()

            # --- Session history ---
            book_sessions = sessions[sessions["book_id"] == book["id"]] if not sessions.empty else pd.DataFrame()
            if not book_sessions.empty:
                st.markdown("**Historial de lectura**")
                for _, s in book_sessions.sort_values("fecha", ascending=False).head(5).iterrows():
                    mins_label = f"{s['minutos']} min"
                    pags_label = f", {int(s['paginas'])} pag" if s["paginas"] > 0 else ""
                    notas_label = f" — {s['notas']}" if s.get("notas") else ""
                    st.caption(f"📅 {s['fecha']}: {mins_label}{pags_label}{notas_label}")
                st.divider()

            # --- Edit book ---
            st.markdown("**Editar libro**")
            with st.form(f"edit_book_{book['id']}"):
                ec1, ec2 = st.columns(2)
                e_titulo = ec1.text_input("Titulo", value=book["titulo"], key=f"et_{book['id']}")
                e_autor = ec2.text_input("Autor", value=book["autor"], key=f"ea_{book['id']}")
                ec3, ec4 = st.columns(2)
                e_paginas = ec3.number_input("Total paginas", min_value=1, value=int(book["paginas"]), key=f"ep_{book['id']}")
                e_pag_leidas = ec4.number_input("Paginas leidas", min_value=0, max_value=int(e_paginas), value=int(book["paginas_leidas"]), key=f"epl_{book['id']}")
                ec5, ec6 = st.columns(2)
                estado_keys = list(BOOK_STATES.keys())
                e_estado = ec5.selectbox("Estado", estado_keys, index=estado_keys.index(book["estado"]), format_func=lambda x: BOOK_STATES[x], key=f"es_{book['id']}")
                e_rating = ec6.slider("Rating", 0, 5, value=int(book["rating"]), key=f"er_{book['id']}")
                e_notas = st.text_area("Notas", value=book.get("notas", ""), key=f"en_{book['id']}")

                if st.form_submit_button("Guardar cambios", type="primary"):
                    books.loc[books["id"] == book["id"], "titulo"] = e_titulo.strip()
                    books.loc[books["id"] == book["id"], "autor"] = e_autor.strip()
                    books.loc[books["id"] == book["id"], "paginas"] = e_paginas
                    books.loc[books["id"] == book["id"], "paginas_leidas"] = e_pag_leidas
                    books.loc[books["id"] == book["id"], "estado"] = e_estado
                    books.loc[books["id"] == book["id"], "rating"] = e_rating
                    books.loc[books["id"] == book["id"], "notas"] = e_notas.strip()

                    if e_estado == "leyendo" and not book["fecha_inicio"]:
                        books.loc[books["id"] == book["id"], "fecha_inicio"] = datetime.now().strftime("%Y-%m-%d")
                    if e_estado == "completado" and not book.get("fecha_fin"):
                        books.loc[books["id"] == book["id"], "fecha_fin"] = datetime.now().strftime("%Y-%m-%d")
                    if e_pag_leidas >= e_paginas and e_estado == "leyendo":
                        books.loc[books["id"] == book["id"], "estado"] = "completado"
                        books.loc[books["id"] == book["id"], "fecha_fin"] = datetime.now().strftime("%Y-%m-%d")

                    save_df("books", books)
                    st.rerun()

            # --- Delete ---
            if st.button("🗑️ Eliminar", key=f"del_book_{book['id']}", use_container_width=True):
                books = books[books["id"] != book["id"]]
                save_df("books", books)
                # Also delete sessions
                if not sessions.empty:
                    sessions = sessions[sessions["book_id"] != book["id"]]
                    save_df("reading_sessions", sessions)
                st.rerun()


def _render_stats(books, sessions):
    if sessions.empty:
        st.info("No hay sesiones de lectura registradas.")
        return

    st.subheader("Tendencia de lectura")

    # --- Daily reading last 30 days ---
    today = datetime.now()
    days_data = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        day_sessions = sessions[sessions["fecha"] == ds]
        mins = int(day_sessions["minutos"].sum()) if not day_sessions.empty else 0
        pags = int(day_sessions["paginas"].sum()) if not day_sessions.empty else 0
        days_data.append({"Fecha": ds, "Minutos": mins, "Paginas": pags})

    chart_df = pd.DataFrame(days_data)
    if chart_df["Minutos"].sum() > 0:
        st.bar_chart(chart_df.set_index("Fecha")["Minutos"], color="#d4a853")
        st.caption("Minutos de lectura por dia (ultimos 30 dias)")

    st.divider()

    # --- Monthly summary ---
    st.subheader("Resumen mensual")
    sessions["month"] = sessions["fecha"].str[:7]
    monthly = sessions.groupby("month").agg({"minutos": "sum", "paginas": "sum", "id": "count"}).reset_index()
    monthly.columns = ["Mes", "Minutos", "Paginas", "Sesiones"]
    monthly = monthly.sort_values("Mes", ascending=False)

    for _, m in monthly.head(6).iterrows():
        hours = m["Minutos"] / 60
        st.markdown(f"**{m['Mes']}**: {int(m['Minutos'])} min ({hours:.1f}h) | {int(m['Paginas'])} pag | {int(m['Sesiones'])} sesiones")

    st.divider()

    # --- Reading by book ---
    if not books.empty:
        st.subheader("Tiempo por libro")
        book_time = sessions.groupby("book_id")["minutos"].sum().reset_index()
        book_time.columns = ["book_id", "minutos"]
        book_names = dict(zip(books["id"], books["titulo"]))
        book_time["Libro"] = book_time["book_id"].map(book_names).fillna("Desconocido")
        book_time = book_time.sort_values("minutos", ascending=False)

        if not book_time.empty:
            chart_data = book_time[["Libro", "minutos"]].copy()
            chart_data.columns = ["Libro", "Minutos"]
            st.bar_chart(chart_data.set_index("Libro"), color="#5a8fc9")

    # --- Meta anual ---
    st.divider()
    st.subheader("Meta anual")
    year = today.year
    completed_year = len(books[(books["estado"] == "completado") & (books["fecha_fin"].str.startswith(str(year)))]) if not books.empty else 0

    goal = st.number_input("Libros meta para este ano", min_value=1, value=12, key="reading_goal")
    pct = min(completed_year / goal * 100, 100)
    st.metric("Libros completados", f"{completed_year}/{goal}")
    st.progress(min(pct / 100, 1.0))
