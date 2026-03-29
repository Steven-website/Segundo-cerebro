import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts
from core.constants import HABIT_CATS, HABIT_FREQ


def _parse_checks(checks_str):
    if isinstance(checks_str, dict):
        return checks_str
    if isinstance(checks_str, str) and checks_str:
        try:
            return json.loads(checks_str)
        except Exception:
            return {}
    return {}


def _is_done_today(h):
    checks = _parse_checks(h.get("checks", "{}"))
    today = datetime.now().strftime("%Y-%m-%d")
    return checks.get(today, False)


def _calc_streak(h):
    checks = _parse_checks(h.get("checks", "{}"))
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


def _get_today_habits(habitos_df):
    if habitos_df.empty:
        return habitos_df
    dow = datetime.now().weekday()
    mask = []
    for _, h in habitos_df.iterrows():
        freq = h.get("freq", "diario")
        if freq == "laborables":
            mask.append(dow < 5)
        elif freq == "fines":
            mask.append(dow >= 5)
        else:
            mask.append(True)
    return habitos_df[mask]


def render():
    st.header("Habitos")

    habitos = get_df("habitos")

    col_spacer, col_add = st.columns([5, 1])
    with col_add:
        if st.button("+ Habito", type="primary", use_container_width=True):
            st.session_state["hab_adding"] = True

    if st.session_state.get("hab_adding"):
        with st.form("hab_form", clear_on_submit=True):
            st.subheader("Nuevo habito")
            c1, c2 = st.columns([3, 1])
            name = c1.text_input("Nombre")
            emoji = c2.text_input("Emoji", value="\u2b50")
            c3, c4 = st.columns(2)
            cat = c3.selectbox("Categoria", list(HABIT_CATS.keys()), format_func=lambda x: f"{HABIT_CATS[x]} {x.capitalize()}")
            freq = c4.selectbox("Frecuencia", list(HABIT_FREQ.keys()), format_func=lambda x: HABIT_FREQ[x])

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip():
                new_row = {
                    "id": uid(), "name": name.strip(), "emoji": emoji or "\u2b50",
                    "cat": cat, "freq": freq, "checks": "{}", "streak": 0, "ts": now_ts(),
                }
                save_df("habitos", pd.concat([pd.DataFrame([new_row]), habitos], ignore_index=True))
                st.session_state["hab_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["hab_adding"] = False
                st.rerun()

    # --- Display habits ---
    today_habs = _get_today_habits(habitos)

    if habitos.empty:
        st.info("No hay habitos configurados.")
        return

    cols = st.columns(2)
    for i, (idx, h) in enumerate(habitos.iterrows()):
        with cols[i % 2]:
            checks = _parse_checks(h.get("checks", "{}"))
            today_str = datetime.now().strftime("%Y-%m-%d")
            done_today = checks.get(today_str, False)
            streak = _calc_streak(h)

            with st.container(border=True):
                # Header
                c_emoji, c_name, c_del = st.columns([1, 6, 1])
                with c_emoji:
                    hab_emoji = h.get('emoji', '\u2b50')
                    st.markdown(f"### {hab_emoji}")
                with c_name:
                    st.markdown(f"**{h['name']}**")
                    st.caption(f"{HABIT_CATS.get(h['cat'], '')} {h['cat'].capitalize()} \u2022 {HABIT_FREQ.get(h['freq'], h['freq'])}")
                with c_del:
                    if st.button("\U0001f5d1", key=f"hdel_{h['id']}"):
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
