import streamlit as st
import pandas as pd
import io
from datetime import datetime
from core.data import get_df, save_df, uid, now_ts
from core.utils import confirm_delete


def render():
    st.header("Audios")
    st.caption("Graba o sube audios, agrega comentarios y descargalos")

    audios = get_df("audios")

    # ═══════════════════════════════
    #  RECORD / UPLOAD
    # ═══════════════════════════════
    tab_record, tab_upload = st.tabs(["Grabar audio", "Subir archivo"])

    with tab_record:
        st.markdown("Presiona el boton para grabar desde tu microfono:")
        audio_input = st.audio_input("Grabar audio", key="audio_rec", label_visibility="collapsed")

        if audio_input is not None:
            st.audio(audio_input)
            with st.form("save_recording", clear_on_submit=True):
                titulo = st.text_input("Titulo", placeholder="Ej: Reunion de trabajo, Nota de voz...")
                fecha = st.date_input("Fecha", value=datetime.now())
                comentario = st.text_area("Comentario", placeholder="Agrega una nota sobre este audio...", height=80)

                if st.form_submit_button("Guardar grabacion", type="primary"):
                    title = titulo.strip() or "Grabacion sin titulo"
                    audio_bytes = audio_input.getvalue()

                    new_audio = {
                        "id": uid(),
                        "titulo": title,
                        "fecha": str(fecha),
                        "comentario": comentario.strip(),
                        "formato": "wav",
                        "tamano": len(audio_bytes),
                        "transcript": "",
                        "resumen": "",
                        "puntos_clave": "[]",
                        "pendientes": "[]",
                        "ts": now_ts(),
                    }
                    audios = pd.concat([pd.DataFrame([new_audio]), audios], ignore_index=True)
                    save_df("audios", audios)

                    # Save audio file locally for download
                    _save_audio_file(new_audio["id"], audio_bytes, "wav")
                    st.success(f"Audio '{title}' guardado")
                    st.rerun()

    with tab_upload:
        uploaded = st.file_uploader(
            "Sube un archivo de audio",
            type=["wav", "mp3", "m4a", "ogg", "flac", "wma"],
            key="audio_upload",
        )

        if uploaded is not None:
            st.audio(uploaded)
            with st.form("save_upload", clear_on_submit=True):
                titulo_up = st.text_input("Titulo", value=uploaded.name.rsplit(".", 1)[0] if "." in uploaded.name else uploaded.name)
                fecha_up = st.date_input("Fecha", value=datetime.now(), key="up_fecha")
                comentario_up = st.text_area("Comentario", placeholder="Agrega una nota sobre este audio...", height=80, key="up_comentario")

                if st.form_submit_button("Guardar archivo", type="primary"):
                    title = titulo_up.strip() or uploaded.name
                    audio_bytes = uploaded.getvalue()
                    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else "wav"

                    new_audio = {
                        "id": uid(),
                        "titulo": title,
                        "fecha": str(fecha_up),
                        "comentario": comentario_up.strip(),
                        "formato": ext,
                        "tamano": len(audio_bytes),
                        "transcript": "",
                        "resumen": "",
                        "puntos_clave": "[]",
                        "pendientes": "[]",
                        "ts": now_ts(),
                    }
                    audios = pd.concat([pd.DataFrame([new_audio]), audios], ignore_index=True)
                    save_df("audios", audios)

                    _save_audio_file(new_audio["id"], audio_bytes, ext)
                    st.success(f"Audio '{title}' guardado")
                    st.rerun()

    # ═══════════════════════════════
    #  HISTORY
    # ═══════════════════════════════
    st.divider()
    st.subheader("Mis audios")

    if audios.empty:
        st.info("No hay audios guardados. Graba o sube uno para empezar.")
        return

    # Filter by date
    col_filter, col_count = st.columns([3, 1])
    with col_filter:
        filter_opt = st.selectbox("Ordenar", ["Mas recientes", "Mas antiguos", "Por fecha"], key="audio_filter")
    with col_count:
        st.metric("Total", len(audios))

    sorted_audios = audios.copy()
    if filter_opt == "Mas recientes":
        sorted_audios = sorted_audios.sort_values("ts", ascending=False)
    elif filter_opt == "Mas antiguos":
        sorted_audios = sorted_audios.sort_values("ts", ascending=True)
    elif filter_opt == "Por fecha":
        if "fecha" in sorted_audios.columns:
            sorted_audios = sorted_audios.sort_values("fecha", ascending=False)

    for _, a in sorted_audios.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"### {a['titulo']}")
                info_parts = []
                if a.get("fecha"):
                    info_parts.append(f"📅 {a['fecha']}")
                if a.get("formato"):
                    info_parts.append(f"📁 {a['formato'].upper()}")
                if a.get("tamano"):
                    size_kb = a["tamano"] / 1024
                    if size_kb > 1024:
                        info_parts.append(f"{size_kb/1024:.1f} MB")
                    else:
                        info_parts.append(f"{size_kb:.0f} KB")
                ts_str = datetime.fromtimestamp(a["ts"]).strftime("%d/%m/%Y %H:%M") if a["ts"] else ""
                if ts_str:
                    info_parts.append(ts_str)
                st.caption(" | ".join(info_parts))

            with col2:
                # Download button
                audio_bytes = _load_audio_file(a["id"], a.get("formato", "wav"))
                if audio_bytes:
                    ext = a.get("formato", "wav")
                    st.download_button(
                        "Descargar",
                        audio_bytes,
                        file_name=f"{a['titulo']}.{ext}",
                        mime=f"audio/{ext}",
                        key=f"dl_{a['id']}",
                        use_container_width=True,
                    )
                if confirm_delete(a["id"], a["titulo"], "audio"):
                    _delete_audio_file(a["id"], a.get("formato", "wav"))
                    audios = audios[audios["id"] != a["id"]]
                    save_df("audios", audios)
                    st.rerun()

            # Comment
            if a.get("comentario"):
                st.markdown(f"💬 {a['comentario']}")

            # Play audio
            audio_bytes = _load_audio_file(a["id"], a.get("formato", "wav"))
            if audio_bytes:
                st.audio(audio_bytes, format=f"audio/{a.get('formato', 'wav')}")

            # Edit comment
            if st.button("✏️ Editar comentario", key=f"edit_com_{a['id']}"):
                st.session_state[f"editing_audio_{a['id']}"] = True

            if st.session_state.get(f"editing_audio_{a['id']}"):
                with st.form(f"edit_audio_{a['id']}"):
                    new_titulo = st.text_input("Titulo", value=a["titulo"])
                    new_fecha = st.date_input("Fecha", value=None, key=f"ef_{a['id']}")
                    new_comentario = st.text_area("Comentario", value=a.get("comentario", ""), key=f"ec_{a['id']}")
                    cs, cc = st.columns(2)
                    if cs.form_submit_button("Guardar", type="primary"):
                        audios.loc[audios["id"] == a["id"], "titulo"] = new_titulo.strip() or a["titulo"]
                        if new_fecha:
                            audios.loc[audios["id"] == a["id"], "fecha"] = str(new_fecha)
                        audios.loc[audios["id"] == a["id"], "comentario"] = new_comentario.strip()
                        save_df("audios", audios)
                        st.session_state[f"editing_audio_{a['id']}"] = False
                        st.rerun()
                    if cc.form_submit_button("Cancelar"):
                        st.session_state[f"editing_audio_{a['id']}"] = False
                        st.rerun()


def _get_audio_dir():
    """Get directory for storing audio files."""
    import os
    user = st.session_state.get("current_user", "default")
    audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", user, "audios")
    os.makedirs(audio_dir, exist_ok=True)
    return audio_dir


def _save_audio_file(audio_id, audio_bytes, ext):
    """Save audio bytes to local file."""
    import os
    path = os.path.join(_get_audio_dir(), f"{audio_id}.{ext}")
    with open(path, "wb") as f:
        f.write(audio_bytes)


def _load_audio_file(audio_id, ext):
    """Load audio bytes from local file."""
    import os
    path = os.path.join(_get_audio_dir(), f"{audio_id}.{ext}")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def _delete_audio_file(audio_id, ext):
    """Delete audio file."""
    import os
    path = os.path.join(_get_audio_dir(), f"{audio_id}.{ext}")
    if os.path.exists(path):
        os.remove(path)
