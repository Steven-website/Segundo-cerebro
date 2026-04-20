import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
from core.data import get_df, save_df, uid, now_ts
from core.constants import AREAS, AREA_LABELS, AREA_MAP
from core.utils import mark_task_done

DAYS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
DAYS_SHORT = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
HOURS = [f"{h:02d}:00" for h in range(7, 23)]
DUR_OPTIONS = [15, 30, 45, 60, 90, 120]


def _monday_of(d):
    return d - timedelta(days=d.weekday())


def _week_dates(monday):
    return [monday + timedelta(days=i) for i in range(7)]


def _shift_hour(hora, delta):
    try:
        idx = HOURS.index(hora)
    except ValueError:
        return hora
    new_idx = max(0, min(len(HOURS) - 1, idx + delta))
    return HOURS[new_idx]


def _materialize_recurring(blocks, week_iso):
    """For each weekly-recurring template, create a copy in the current week if missing."""
    if blocks.empty:
        return blocks
    templates = blocks[blocks["recurrente"] == "semanal"]
    if templates.empty:
        return blocks

    new_rows = []
    for _, t in templates.iterrows():
        try:
            t_date = date.fromisoformat(t["fecha"])
        except (ValueError, TypeError):
            continue
        dow = t_date.weekday()
        target_fecha = week_iso[dow]
        if target_fecha == t["fecha"]:
            continue  # template itself lives on this day
        # Already materialized (by parent_id or title+hour match)?
        existing = blocks[
            (blocks["fecha"] == target_fecha)
            & (blocks["hora"] == t["hora"])
            & ((blocks["parent_id"] == t["id"]) | (blocks["titulo"] == t["titulo"]))
        ]
        if not existing.empty:
            continue
        new_rows.append({
            "id": uid(),
            "fecha": target_fecha,
            "hora": t["hora"],
            "tarea_id": t.get("tarea_id", ""),
            "titulo": t["titulo"],
            "duracion": int(t["duracion"]) if t.get("duracion") else 60,
            "completado": False,
            "recurrente": "",
            "parent_id": t["id"],
            "ts": now_ts(),
        })

    if new_rows:
        blocks = pd.concat([pd.DataFrame(new_rows), blocks], ignore_index=True)
        save_df("plan_blocks", blocks)
    return blocks


def render():
    st.header("Semana")

    tareas = get_df("tareas")
    proyectos = get_df("proyectos")
    blocks = get_df("plan_blocks")

    # --- Week state ---
    if "semana_monday" not in st.session_state:
        st.session_state["semana_monday"] = _monday_of(date.today()).isoformat()

    monday = date.fromisoformat(st.session_state["semana_monday"])
    week = _week_dates(monday)
    week_iso = [d.isoformat() for d in week]

    # Materialize recurring templates into this week
    blocks = _materialize_recurring(blocks, week_iso)

    # --- Navigation bar ---
    col_prev, col_label, col_today, col_next = st.columns([1, 4, 1, 1])
    with col_prev:
        if st.button("← Semana", use_container_width=True, key="sem_prev"):
            st.session_state["semana_monday"] = (monday - timedelta(days=7)).isoformat()
            st.rerun()
    with col_label:
        label = f"**Semana del {week[0].strftime('%d/%m')} al {week[6].strftime('%d/%m/%Y')}**"
        st.markdown(f"<div style='text-align:center;padding-top:6px'>{label}</div>", unsafe_allow_html=True)
    with col_today:
        if st.button("Hoy", use_container_width=True, key="sem_today"):
            st.session_state["semana_monday"] = _monday_of(date.today()).isoformat()
            st.rerun()
    with col_next:
        if st.button("Semana →", use_container_width=True, key="sem_next"):
            st.session_state["semana_monday"] = (monday + timedelta(days=7)).isoformat()
            st.rerun()

    # --- Filters ---
    col_area, col_add = st.columns([3, 1])
    with col_area:
        area_opts = ["Todas las areas"] + [f'{a["emoji"]} {a["name"]}' for a in AREAS]
        area_filter = st.selectbox("Area", area_opts, index=1, key="sem_area", label_visibility="collapsed")
    with col_add:
        if st.button("+ Bloque", type="primary", use_container_width=True, key="sem_add_btn"):
            st.session_state["sem_adding"] = True

    area_id = None
    if area_filter != "Todas las areas":
        for a in AREAS:
            if f'{a["emoji"]} {a["name"]}' == area_filter:
                area_id = a["id"]
                break

    # --- Filter blocks by week and area ---
    week_blocks = blocks[blocks["fecha"].isin(week_iso)] if not blocks.empty else pd.DataFrame()
    if area_id and not week_blocks.empty and not tareas.empty:
        task_area = dict(zip(tareas["id"], tareas["area"]))
        week_blocks = week_blocks[week_blocks["tarea_id"].apply(lambda tid: task_area.get(tid) == area_id if tid else False)]

    # --- Summary ---
    total = len(week_blocks)
    done = int(week_blocks["completado"].sum()) if not week_blocks.empty else 0
    hours = week_blocks["duracion"].sum() / 60 if not week_blocks.empty else 0
    pending = total - done

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bloques", f"{done}/{total}")
    c2.metric("Horas", f"{hours:.1f}h")
    c3.metric("Pendientes", pending)
    c4.metric("Completado", f"{int(done/total*100) if total else 0}%")

    # --- Rollover pending to next week ---
    if pending > 0:
        next_monday = (monday + timedelta(days=7)).isoformat()
        next_label = f"{(monday + timedelta(days=7)).strftime('%d/%m')}"
        if st.button(f"↪ Pasar {pending} pendiente(s) a semana del {next_label}", key="sem_rollover"):
            pend_blocks = week_blocks[~week_blocks["completado"]]
            for _, b in pend_blocks.iterrows():
                try:
                    cur = date.fromisoformat(b["fecha"])
                    new_fecha = (cur + timedelta(days=7)).isoformat()
                except Exception:
                    new_fecha = next_monday
                blocks.loc[blocks["id"] == b["id"], "fecha"] = new_fecha
                if b["tarea_id"] and not tareas.empty:
                    tareas.loc[tareas["id"] == b["tarea_id"], "fecha"] = new_fecha
            save_df("plan_blocks", blocks)
            save_df("tareas", tareas)
            st.session_state["semana_monday"] = next_monday
            st.rerun()

    # --- Add block form ---
    if st.session_state.get("sem_adding"):
        with st.form("sem_add_form", clear_on_submit=True):
            st.subheader("Nuevo bloque")
            today_dow = date.today().weekday() if date.today().isoformat() in week_iso else 0
            day_idxs = st.multiselect(
                "Dias (elegi uno o varios)",
                range(7),
                default=[today_dow],
                format_func=lambda i: f"{DAYS[i]} {week[i].strftime('%d/%m')}",
                help="Seleccioná varios dias para crear el mismo bloque en cada uno.",
            )
            c2, c3 = st.columns(2)
            hora = c2.selectbox("Hora", HOURS, index=2)
            duracion = c3.selectbox("Duracion", DUR_OPTIONS, index=3,
                                    format_func=lambda x: f"{x} min ({x/60:.1f}h)" if x >= 60 else f"{x} min")

            # Task selector filtered by area if set
            pending_tasks = tareas[~tareas["done"]] if not tareas.empty else pd.DataFrame()
            if area_id and not pending_tasks.empty:
                pending_tasks = pending_tasks[pending_tasks["area"] == area_id]
            task_options = ["Actividad libre"]
            task_ids = [""]
            if not pending_tasks.empty:
                for _, t in pending_tasks.iterrows():
                    pri = {"alta": "🔴", "media": "🟡", "baja": "🟢"}.get(t["prioridad"], "")
                    task_options.append(f"{pri} {t['titulo']}")
                    task_ids.append(t["id"])
            task_sel = st.selectbox("Tarea", range(len(task_options)), format_func=lambda i: task_options[i])
            titulo = ""
            if task_sel == 0:
                titulo = st.text_input("Titulo del bloque", placeholder="Que vas a hacer?")

            repetir = st.checkbox("🔁 Repetir cada semana (mismo dia y hora)", value=False,
                                  help="Crea el bloque como plantilla semanal. Cada nueva semana se generara automaticamente.")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Agregar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted:
                block_titulo = titulo.strip() if task_sel == 0 else task_options[task_sel]
                if (block_titulo or task_ids[task_sel]) and day_idxs:
                    new_rows = []
                    for di in day_idxs:
                        new_rows.append({
                            "id": uid(),
                            "fecha": week_iso[di],
                            "hora": hora,
                            "tarea_id": task_ids[task_sel],
                            "titulo": block_titulo,
                            "duracion": duracion,
                            "completado": False,
                            "recurrente": "semanal" if repetir else "",
                            "parent_id": "",
                            "ts": now_ts(),
                        })
                    blocks = pd.concat([pd.DataFrame(new_rows), blocks], ignore_index=True)
                    save_df("plan_blocks", blocks)
                st.session_state["sem_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["sem_adding"] = False
                st.rerun()

    st.divider()

    # --- Day tabs ---
    today_iso = date.today().isoformat()
    tab_labels = []
    for i, d in enumerate(week):
        marker = " ●" if d.isoformat() == today_iso else ""
        day_blocks = week_blocks[week_blocks["fecha"] == d.isoformat()] if not week_blocks.empty else pd.DataFrame()
        count = len(day_blocks)
        count_str = f" ({count})" if count else ""
        tab_labels.append(f"{DAYS_SHORT[i]} {d.day}{marker}{count_str}")

    tabs = st.tabs(tab_labels)
    for i, tab in enumerate(tabs):
        with tab:
            _render_day(week_iso[i], week_blocks, blocks, tareas, proyectos)


def _render_day(fecha_iso, week_blocks, all_blocks, tareas, proyectos):
    day_blocks = week_blocks[week_blocks["fecha"] == fecha_iso].sort_values("hora") if not week_blocks.empty else pd.DataFrame()

    if day_blocks.empty:
        st.info("Sin bloques. Usa '+ Bloque' arriba para agregar uno.")
        return

    current_hora = datetime.now().strftime("%H:00") if fecha_iso == date.today().isoformat() else None

    for _, b in day_blocks.iterrows():
        is_now = b["hora"] == current_hora
        done = bool(b["completado"])

        col_time, col_info, col_move, col_done, col_del = st.columns([1.4, 5, 0.7, 0.7, 0.7])
        with col_time:
            hora_txt = f":orange[{b['hora']}]" if is_now else b["hora"]
            st.markdown(f"**{hora_txt}** · {b['duracion']}m")
        with col_info:
            style = "~~" if done else ""
            title = b["titulo"] or ""
            area_emoji = ""
            if b["tarea_id"] and not tareas.empty:
                tm = tareas[tareas["id"] == b["tarea_id"]]
                if not tm.empty:
                    t = tm.iloc[0]
                    if not title:
                        title = t["titulo"]
                    area = AREA_MAP.get(t["area"])
                    if area:
                        area_emoji = area["emoji"] + " "
            recur_icon = " 🔁" if (b.get("recurrente") == "semanal" or b.get("parent_id")) else ""
            st.markdown(f"{area_emoji}{style}{title}{style}{recur_icon}")
        with col_move:
            with st.popover("⋯", use_container_width=True, help="Mover"):
                mv1, mv2 = st.columns(2)
                with mv1:
                    if st.button("← dia", key=f"sem_mvl_{b['id']}", use_container_width=True):
                        cur = date.fromisoformat(b["fecha"])
                        all_blocks.loc[all_blocks["id"] == b["id"], "fecha"] = (cur - timedelta(days=1)).isoformat()
                        save_df("plan_blocks", all_blocks)
                        st.rerun()
                with mv2:
                    if st.button("dia →", key=f"sem_mvr_{b['id']}", use_container_width=True):
                        cur = date.fromisoformat(b["fecha"])
                        all_blocks.loc[all_blocks["id"] == b["id"], "fecha"] = (cur + timedelta(days=1)).isoformat()
                        save_df("plan_blocks", all_blocks)
                        st.rerun()
                mv3, mv4 = st.columns(2)
                with mv3:
                    if st.button("↑ hora", key=f"sem_mvu_{b['id']}", use_container_width=True):
                        all_blocks.loc[all_blocks["id"] == b["id"], "hora"] = _shift_hour(b["hora"], -1)
                        save_df("plan_blocks", all_blocks)
                        st.rerun()
                with mv4:
                    if st.button("↓ hora", key=f"sem_mvd_{b['id']}", use_container_width=True):
                        all_blocks.loc[all_blocks["id"] == b["id"], "hora"] = _shift_hour(b["hora"], 1)
                        save_df("plan_blocks", all_blocks)
                        st.rerun()
        with col_done:
            if not done:
                if st.button("✅", key=f"sem_ok_{b['id']}", help="Completar", use_container_width=True):
                    all_blocks.loc[all_blocks["id"] == b["id"], "completado"] = True
                    if b["tarea_id"] and not tareas.empty:
                        mark_task_done(tareas, b["tarea_id"])
                        save_df("tareas", tareas)
                    save_df("plan_blocks", all_blocks)
                    st.rerun()
            else:
                if st.button("↩", key=f"sem_undo_{b['id']}", help="Desmarcar", use_container_width=True):
                    all_blocks.loc[all_blocks["id"] == b["id"], "completado"] = False
                    save_df("plan_blocks", all_blocks)
                    st.rerun()
        with col_del:
            if st.button("🗑", key=f"sem_del_{b['id']}", help="Eliminar", use_container_width=True):
                st.session_state[f"sem_confirm_del_{b['id']}"] = True
                st.rerun()

        if st.session_state.get(f"sem_confirm_del_{b['id']}"):
            is_template = b.get("recurrente") == "semanal"
            msg = "¿Eliminar esta plantilla recurrente y todas sus copias futuras?" if is_template else "¿Eliminar este bloque?"
            st.warning(msg)
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Si, eliminar", key=f"sem_yes_{b['id']}", type="primary", use_container_width=True):
                    if is_template:
                        all_blocks = all_blocks[(all_blocks["id"] != b["id"]) & (all_blocks["parent_id"] != b["id"])]
                    else:
                        all_blocks = all_blocks[all_blocks["id"] != b["id"]]
                    save_df("plan_blocks", all_blocks)
                    st.session_state[f"sem_confirm_del_{b['id']}"] = False
                    st.rerun()
            with col_no:
                if st.button("Cancelar", key=f"sem_no_{b['id']}", use_container_width=True):
                    st.session_state[f"sem_confirm_del_{b['id']}"] = False
                    st.rerun()
