import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts
from core.constants import HABIT_CATS, HABIT_FREQ
from core.utils import parse_checks, is_done_today, confirm_delete, export_csv


def _calc_streak(h):
    checks = parse_checks(h.get("checks", "{}"))
    streak = 0
    day = datetime.now()
    while True:
        ds = day.strftime("%Y-%m-%d")
        if checks.get(ds, False):
            streak += 1
            day -= timedelta(days=1)
        else:
            if day.date() == datetime.now().date():
                day -= timedelta(days=1)
                continue
            break
    return streak


def render():
    st.header("Habitos")

    habitos = get_df("habitos")

    col_exp, col_add = st.columns([5, 1])
    with col_exp:
        export_csv(habitos, "habitos.csv", "\U0001f4e5 Exportar CSV")
    with col_add:
        if st.button("+ Habito", type="primary", use_container_width=True):
            st.session_state["hab_editing"] = True
            st.session_state["hab_edit_id"] = None

    if st.session_state.get("hab_editing"):
        edit_id = st.session_state.get("hab_edit_id")
        existing = None
        if edit_id and not habitos.empty:
            matches = habitos[habitos["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("hab_form", clear_on_submit=True):
            st.subheader("Editar habito" if existing is not None else "Nuevo habito")
            c1, c2 = st.columns([3, 1])
            name = c1.text_input("Nombre", value=existing["name"] if existing is not None else "")
            emoji = c2.text_input("Emoji", value=existing.get("emoji", "\u2b50") if existing is not None else "\u2b50")
            c3, c4 = st.columns(2)
            cat_keys = list(HABIT_CATS.keys())
            cat = c3.selectbox("Categoria", cat_keys, format_func=lambda x: f"{HABIT_CATS[x]} {x.capitalize()}",
                               index=cat_keys.index(existing["cat"]) if existing is not None and existing["cat"] in cat_keys else 0)
            freq_keys = list(HABIT_FREQ.keys())
            freq = c4.selectbox("Frecuencia", freq_keys, format_func=lambda x: HABIT_FREQ[x],
                                index=freq_keys.index(existing["freq"]) if existing is not None and existing["freq"] in freq_keys else 0)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip():
                new_row = {
                    "id": edit_id or uid(), "name": name.strip(), "emoji": emoji or "\u2b50",
                    "cat": cat, "freq": freq,
                    "checks": existing["checks"] if existing is not None else "{}",
                    "streak": existing["streak"] if existing is not None else 0,
                    "ts": now_ts(),
                }
                if edit_id and not habitos.empty:
                    habitos = habitos[habitos["id"] != edit_id]
                save_df("habitos", pd.concat([pd.DataFrame([new_row]), habitos], ignore_index=True))
                st.session_state["hab_editing"] = False
                st.session_state["hab_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["hab_editing"] = False
                st.session_state["hab_edit_id"] = None
                st.rerun()

    # --- Display habits ---
    if habitos.empty:
        st.info("No hay habitos configurados.")
        return

    cols = st.columns(2)
    for i, (idx, h) in enumerate(habitos.iterrows()):
        with cols[i % 2]:
            checks = parse_checks(h.get("checks", "{}"))
            today_str = datetime.now().strftime("%Y-%m-%d")
            done_today = checks.get(today_str, False)
            streak = _calc_streak(h)

            with st.container(border=True):
                # Header
                c_emoji, c_name, c_edit, c_del = st.columns([1, 5, 1, 1])
                with c_emoji:
                    hab_emoji = h.get('emoji', '\u2b50')
                    st.markdown(f"### {hab_emoji}")
                with c_name:
                    st.markdown(f"**{h['name']}**")
                    st.caption(f"{HABIT_CATS.get(h['cat'], '')} {h['cat'].capitalize()} \u2022 {HABIT_FREQ.get(h['freq'], h['freq'])}")
                with c_edit:
                    if st.button("\u270f\ufe0f", key=f"hedit_{h['id']}"):
                        st.session_state["hab_editing"] = True
                        st.session_state["hab_edit_id"] = h["id"]
                        st.rerun()
                with c_del:
                    if confirm_delete(h["id"], h["name"], "hab"):
                        habitos = habitos[habitos["id"] != h["id"]]
                        save_df("habitos", habitos)
                        st.rerun()

                # Mini calendar (last 7 days)
                days = []
                for d in range(6, -1, -1):
                    day = datetime.now() - timedelta(days=d)
                    ds = day.strftime("%Y-%m-%d")
                    day_name = day.strftime("%a")[0]
                    done = checks.get(ds, False)
                    is_today = ds == today_str
                    days.append((day_name, done, is_today, ds))

                day_cols = st.columns(7)
                for j, (day_name, done, is_today, ds) in enumerate(days):
                    with day_cols[j]:
                        if done:
                            st.markdown(f"**:green[{day_name}]**")
                        elif is_today:
                            st.markdown(f"**:orange[{day_name}]**")
                        else:
                            st.markdown(f"*{day_name}*")

                # Today toggle + streak
                c_toggle, c_streak = st.columns([3, 1])
                with c_toggle:
                    new_done = st.checkbox(
                        "Hecho hoy" if not done_today else "Completado",
                        value=done_today,
                        key=f"htoggle_{h['id']}",
                    )
                    if new_done != done_today:
                        checks[today_str] = new_done
                        habitos.loc[habitos["id"] == h["id"], "checks"] = json.dumps(checks)
                        habitos.loc[habitos["id"] == h["id"], "streak"] = _calc_streak({"checks": json.dumps(checks)})
                        save_df("habitos", habitos)
                        st.rerun()
                with c_streak:
                    st.metric("Racha", f"\U0001f525 {streak}")
