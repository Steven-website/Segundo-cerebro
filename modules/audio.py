import streamlit as st
import pandas as pd
import json
import io
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_OPTIONS
from core.utils import confirm_delete


def _transcribe_audio(audio_bytes):
    """Transcribe audio bytes using SpeechRecognition + Google free API."""
    import speech_recognition as sr
    recognizer = sr.Recognizer()

    # Convert bytes to WAV AudioData
    audio_file = io.BytesIO(audio_bytes)
    try:
        with sr.AudioFile(audio_file) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="es-CR")
        return text
    except sr.UnknownValueError:
        return None
    except Exception as e:
        raise e


def _convert_to_wav(audio_bytes, filename):
    """Convert uploaded audio to WAV format for speech_recognition."""
    from pydub import AudioSegment
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
    if ext == "wav":
        return audio_bytes
    audio_seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format=ext)
    wav_buf = io.BytesIO()
    audio_seg.export(wav_buf, format="wav")
    return wav_buf.getvalue()


def _analyze_with_ai(transcript, api_key):
    """Send transcript to Claude to extract key points and pending tasks."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Analiza la siguiente transcripcion de audio y devuelve un JSON con exactamente esta estructura:
{{
  "resumen": "Resumen breve del audio en 2-3 oraciones",
  "puntos_clave": ["punto 1", "punto 2", ...],
  "pendientes": ["tarea pendiente 1", "tarea pendiente 2", ...]
}}

Reglas:
- "puntos_clave": los puntos o ideas principales mencionados
- "pendientes": cualquier tarea, compromiso, accion a realizar, cosa por hacer, o recordatorio mencionado
- Si no hay pendientes claros, devuelve lista vacia
- Responde SOLO el JSON, sin texto adicional
- Todo en espanol

Transcripcion:
{transcript}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    result_text = "".join(block.text for block in response.content if hasattr(block, "text"))

    # Parse JSON from response
    result_text = result_text.strip()
    if result_text.startswith("```"):
        result_text = result_text.split("\n", 1)[1]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

    return json.loads(result_text)


def _create_tasks_from_pendientes(pendientes, source_title, proyecto="", area="personal"):
    """Create tasks in the tareas module from extracted pendientes."""
    tareas = get_df("tareas")
    new_rows = []
    for p in pendientes:
        new_rows.append({
            "id": uid(),
            "titulo": p,
            "area": area,
            "prioridad": "media",
            "fecha": "",
            "proyecto": proyecto,
            "notas": f"Extraido de audio: {source_title}",
            "subtareas": "[]",
            "recurrente": "",
            "done": False,
            "pinned": False,
            "archived": False,
            "ts": now_ts(),
        })
    if new_rows:
        tareas = pd.concat([pd.DataFrame(new_rows), tareas], ignore_index=True)
        save_df("tareas", tareas)
    return len(new_rows)


def render():
    st.header("Audios")
    st.caption("Graba o sube audios y la IA extrae puntos clave y tareas pendientes")

    audios = get_df("audios")

    # --- API Key check ---
    api_key = st.session_state.get("ai_key", "")
    if not api_key:
        st.warning("Configura tu API Key de Anthropic en la pagina **Buscar con IA** para usar el analisis.")

    # ═══════════════════════════════
    #  RECORD / UPLOAD
    # ═══════════════════════════════
    # --- Project / Area selector for tasks ---
    proyectos = get_df("proyectos")
    proy_list = ["Sin proyecto"]
    if not proyectos.empty:
        proy_list += proyectos["nombre"].tolist()
    area_labels = list(AREA_OPTIONS.keys())

    col_proy, col_area = st.columns(2)
    with col_proy:
        sel_proy = st.selectbox("Asignar pendientes a proyecto", proy_list, key="audio_proy")
    with col_area:
        sel_area = st.selectbox("Area", area_labels, key="audio_area")

    proyecto_name = sel_proy if sel_proy != "Sin proyecto" else ""
    area_id = AREA_OPTIONS.get(sel_area, "personal")

    tab_record, tab_upload = st.tabs(["Grabar audio", "Subir archivo"])

    with tab_record:
        st.markdown("Presiona el boton para grabar desde tu microfono:")
        audio_input = st.audio_input("Grabar audio", key="audio_rec", label_visibility="collapsed")

        if audio_input is not None:
            st.audio(audio_input)
            titulo = st.text_input("Titulo para esta grabacion", value="", key="rec_titulo",
                                   placeholder="Ej: Reunion de trabajo, Ideas proyecto...")

            if st.button("Analizar grabacion", type="primary", key="btn_analyze_rec"):
                if not api_key:
                    st.error("Configura tu API key primero en Buscar con IA.")
                    return

                audio_bytes = audio_input.getvalue()
                title = titulo.strip() or "Grabacion sin titulo"

                with st.spinner("Transcribiendo audio..."):
                    try:
                        transcript = _transcribe_audio(audio_bytes)
                    except Exception as e:
                        st.error(f"Error al transcribir: {e}")
                        return

                if not transcript:
                    st.error("No se pudo reconocer texto en el audio. Intenta hablar mas claro o mas cerca del microfono.")
                    return

                st.success("Audio transcrito correctamente")
                st.markdown(f"**Transcripcion:** {transcript}")

                with st.spinner("Analizando con IA..."):
                    try:
                        analysis = _analyze_with_ai(transcript, api_key)
                    except Exception as e:
                        st.error(f"Error al analizar: {e}")
                        return

                # Save to audios dataframe
                new_audio = {
                    "id": uid(),
                    "titulo": title,
                    "transcript": transcript,
                    "resumen": analysis.get("resumen", ""),
                    "puntos_clave": json.dumps(analysis.get("puntos_clave", []), ensure_ascii=False),
                    "pendientes": json.dumps(analysis.get("pendientes", []), ensure_ascii=False),
                    "ts": now_ts(),
                }
                audios = pd.concat([pd.DataFrame([new_audio]), audios], ignore_index=True)
                save_df("audios", audios)

                # Auto-create tasks
                pends = analysis.get("pendientes", [])
                if pends:
                    count = _create_tasks_from_pendientes(pends, title, proyecto_name, area_id)
                    st.success(f"Se crearon {count} tarea(s) en el modulo de Tareas.")

                st.rerun()

    with tab_upload:
        uploaded = st.file_uploader(
            "Sube un archivo de audio",
            type=["wav", "mp3", "m4a", "ogg", "flac", "wma"],
            key="audio_upload",
        )

        if uploaded is not None:
            st.audio(uploaded)
            titulo_up = st.text_input("Titulo para este audio", value="", key="up_titulo",
                                      placeholder="Ej: Nota de voz, Entrevista...")

            if st.button("Analizar archivo", type="primary", key="btn_analyze_up"):
                if not api_key:
                    st.error("Configura tu API key primero en Buscar con IA.")
                    return

                audio_bytes = uploaded.getvalue()
                title = titulo_up.strip() or uploaded.name

                with st.spinner("Convirtiendo audio..."):
                    try:
                        wav_bytes = _convert_to_wav(audio_bytes, uploaded.name)
                    except Exception as e:
                        st.error(f"Error al convertir audio: {e}")
                        return

                with st.spinner("Transcribiendo audio..."):
                    try:
                        transcript = _transcribe_audio(wav_bytes)
                    except Exception as e:
                        st.error(f"Error al transcribir: {e}")
                        return

                if not transcript:
                    st.error("No se pudo reconocer texto en el audio. Verifica que el archivo tenga voz clara.")
                    return

                st.success("Audio transcrito correctamente")
                st.markdown(f"**Transcripcion:** {transcript}")

                with st.spinner("Analizando con IA..."):
                    try:
                        analysis = _analyze_with_ai(transcript, api_key)
                    except Exception as e:
                        st.error(f"Error al analizar: {e}")
                        return

                new_audio = {
                    "id": uid(),
                    "titulo": title,
                    "transcript": transcript,
                    "resumen": analysis.get("resumen", ""),
                    "puntos_clave": json.dumps(analysis.get("puntos_clave", []), ensure_ascii=False),
                    "pendientes": json.dumps(analysis.get("pendientes", []), ensure_ascii=False),
                    "ts": now_ts(),
                }
                audios = pd.concat([pd.DataFrame([new_audio]), audios], ignore_index=True)
                save_df("audios", audios)

                pends = analysis.get("pendientes", [])
                if pends:
                    count = _create_tasks_from_pendientes(pends, title, proyecto_name, area_id)
                    st.success(f"Se crearon {count} tarea(s) en el modulo de Tareas.")

                st.rerun()

    # ═══════════════════════════════
    #  HISTORY
    # ═══════════════════════════════
    st.divider()
    st.subheader("Historial de audios analizados")

    if audios.empty:
        st.info("No hay audios analizados aun. Graba o sube uno para empezar.")
        return

    for _, a in audios.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                from datetime import datetime
                ts_str = datetime.fromtimestamp(a["ts"]).strftime("%d/%m/%Y %H:%M") if a["ts"] else ""
                st.markdown(f"### {a['titulo']}")
                st.caption(ts_str)
            with col2:
                if confirm_delete(a["id"], a["titulo"], "audio"):
                    audios = audios[audios["id"] != a["id"]]
                    save_df("audios", audios)
                    st.rerun()

            # Resumen
            if a.get("resumen"):
                st.markdown(f"**Resumen:** {a['resumen']}")

            # Puntos clave
            try:
                puntos = json.loads(a.get("puntos_clave", "[]"))
            except (json.JSONDecodeError, TypeError):
                puntos = []
            if puntos:
                st.markdown("**Puntos clave:**")
                for p in puntos:
                    st.markdown(f"- {p}")

            # Pendientes
            try:
                pends = json.loads(a.get("pendientes", "[]"))
            except (json.JSONDecodeError, TypeError):
                pends = []
            if pends:
                st.markdown("**Pendientes extraidos:**")
                for p in pends:
                    st.markdown(f"- [ ] {p}")

            # Transcripcion completa
            with st.expander("Ver transcripcion completa"):
                st.markdown(a.get("transcript", ""))
