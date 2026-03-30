import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts
from core.constants import HABIT_CATS, HABIT_FREQ
from core.utils import parse_checks, is_done_today, get_day_completion, confirm_delete, export_csv
import calendar


STREAK_MILESTONES = [
    (100, "💎", "Diamante — 100 dias!"),
    (60, "👑", "Oro — 60 dias!"),
    (30, "🥈", "Plata — 30 dias!"),
    (7, "🥉", "Bronce — 7 dias!"),
]


def _is_day_complete(h, date_str):
    """Check if a day is fully complete (supports sub-checks)."""
    checks = parse_checks(h.get("checks", "{}"))
    reps = [r.strip() for r in h.get("repeticiones", "").split(",") if r.strip()]
    val = checks.get(date_str, False)
    if reps:
        if isinstance(val, dict):
            return all(val.get(r, False) for r in reps)
        return val is True
    return bool(val)


def _day_pct(h, date_str):
    """Get completion percentage for a day."""
    done, total = get_day_completion(h, date_str)
    return done / total if total > 0 else 0


def _calc_streak(h):
    streak = 0
    day = datetime.now()
    while True:
        ds = day.strftime("%Y-%m-%d")
        if _is_day_complete(h, ds):
            streak += 1
            day -= timedelta(days=1)
        else:
            if day.date() == datetime.now().date():
                day -= timedelta(days=1)
                continue
            break
    return streak


def _get_streak_badge(streak):
    """Return the highest milestone badge for a streak."""
    for threshold, badge, label in STREAK_MILESTONES:
        if streak >= threshold:
            return badge, label
    return "", ""


def _calc_max_streak(h):
    """Calculate max streak considering sub-checks."""
    checks = parse_checks(h.get("checks", "{}")) if isinstance(h, (dict, pd.Series)) else {}
    if not checks:
        return 0
    # Get all fully completed dates
    completed_dates = []
    for ds in sorted(checks.keys()):
        if _is_day_complete(h, ds):
            completed_dates.append(ds)
    if not completed_dates:
        return 0
    max_streak = 1
    current = 1
    for i in range(1, len(completed_dates)):
        try:
            d1 = datetime.strptime(completed_dates[i - 1], "%Y-%m-%d")
            d2 = datetime.strptime(completed_dates[i], "%Y-%m-%d")
            if (d2 - d1).days == 1:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 1
        except ValueError:
            current = 1
    return max_streak


def _get_month_stats(h, year, month):
    """Get month stats considering sub-checks."""
    prefix = f"{year}-{month:02d}"
    days_in_month = calendar.monthrange(year, month)[1]
    today = datetime.now()
    if year == today.year and month == today.month:
        total_days = today.day
    else:
        total_days = days_in_month
    done_days = 0
    for day_num in range(1, total_days + 1):
        ds = f"{year}-{month:02d}-{day_num:02d}"
        if _is_day_complete(h, ds):
            done_days += 1
    pct = int(done_days / total_days * 100) if total_days > 0 else 0
    return done_days, total_days, pct


def render():
    st.header("Habitos")

    habitos = get_df("habitos")

    # Tabs: habits + stats
    tab_habits, tab_stats = st.tabs(["Mis habitos", "Estadisticas"])

    with tab_habits:
        _render_habits_list(habitos)

    with tab_stats:
        _render_stats(habitos)


def _render_habits_list(habitos):
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

            repeticiones = st.text_input(
                "Repeticiones por dia (opcional, separadas por coma)",
                value=existing.get("repeticiones", "") if existing is not None else "",
                placeholder="Ej: mañana,tarde,noche",
                help="Si el habito se repite varias veces al dia, escribe las repeticiones separadas por coma. Solo cuenta como completado si cumples todas.",
            )

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip():
                new_row = {
                    "id": edit_id or uid(), "name": name.strip(), "emoji": emoji or "\u2b50",
                    "cat": cat, "freq": freq,
                    "checks": existing["checks"] if existing is not None else "{}",
                    "streak": existing["streak"] if existing is not None else 0,
                    "repeticiones": repeticiones.strip(),
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

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Separate pending vs completed today
    pending_habs = []
    done_habs = []
    for idx, h in habitos.iterrows():
        if _is_day_complete(h, today_str):
            done_habs.append(h)
        else:
            pending_habs.append(h)

    # --- Pending habits ---
    if not pending_habs:
        st.success("Todos los habitos de hoy completados!")

    for h in pending_habs:
        _render_habit_card(h, habitos, today_str)

    # --- Completed habits (collapsed) ---
    if done_habs:
        with st.expander(f"✅ Completados hoy ({len(done_habs)})"):
            for h in done_habs:
                _render_habit_card(h, habitos, today_str)


def _render_habit_card(h, habitos, today_str):
    """Render a single habit card."""
    checks = parse_checks(h.get("checks", "{}"))
    streak = _calc_streak(h)
    hab_emoji = h.get('emoji', '\u2b50')
    reps = [r.strip() for r in h.get("repeticiones", "").split(",") if r.strip()]
    badge, badge_label = _get_streak_badge(streak)

    with st.container(border=True):
            if reps:
                # --- Sub-checks compact layout ---
                today_val = checks.get(today_str, {})
                if not isinstance(today_val, dict):
                    today_val = {r: bool(today_val) for r in reps}
                done_count, total_count = get_day_completion(h, today_str)
                pct_today = int(done_count / total_count * 100) if total_count > 0 else 0
                all_done = done_count == total_count

                col_info, col_streak = st.columns([5, 1])
                with col_info:
                    status = "~~" if all_done else ""
                    st.markdown(f"{hab_emoji} {status}**{h['name']}**{status}  —  {done_count}/{total_count} ({pct_today}%) {badge}")
                with col_streak:
                    st.markdown(f"\U0001f525 {streak}")

                rep_cols = st.columns(len(reps))
                for ri, rep in enumerate(reps):
                    with rep_cols[ri]:
                        rep_done = today_val.get(rep, False)
                        new_val = st.checkbox(rep.capitalize(), value=rep_done, key=f"hrep_{h['id']}_{ri}")
                        if new_val != rep_done:
                            today_val[rep] = new_val
                            checks[today_str] = today_val
                            habitos.loc[habitos["id"] == h["id"], "checks"] = json.dumps(checks)
                            h_updated = dict(h)
                            h_updated["checks"] = json.dumps(checks)
                            habitos.loc[habitos["id"] == h["id"], "streak"] = _calc_streak(h_updated)
                            save_df("habitos", habitos)
                            st.rerun()
            else:
                # --- Simple compact layout ---
                done_today = _is_day_complete(h, today_str)
                col_check, col_info, col_streak = st.columns([0.5, 5, 1])
                with col_check:
                    new_done = st.checkbox("", value=done_today, key=f"htoggle_{h['id']}", label_visibility="collapsed")
                    if new_done != done_today:
                        checks[today_str] = new_done
                        habitos.loc[habitos["id"] == h["id"], "checks"] = json.dumps(checks)
                        h_updated = dict(h)
                        h_updated["checks"] = json.dumps(checks)
                        habitos.loc[habitos["id"] == h["id"], "streak"] = _calc_streak(h_updated)
                        save_df("habitos", habitos)
                        st.rerun()
                with col_info:
                    status = "~~" if done_today else ""
                    st.markdown(f"{hab_emoji} {status}**{h['name']}**{status} {badge}")
                with col_streak:
                    st.markdown(f"\U0001f525 {streak}")

            # Expandable details (calendar, edit, delete)
            with st.expander("Ver mas"):
                st.caption(f"{HABIT_CATS.get(h['cat'], '')} {h['cat'].capitalize()} \u2022 {HABIT_FREQ.get(h['freq'], h['freq'])}")
                if badge_label:
                    st.caption(f"{badge} {badge_label}")

                # Mini calendar (last 7 days)
                day_cols = st.columns(7)
                for d in range(6, -1, -1):
                    day = datetime.now() - timedelta(days=d)
                    ds = day.strftime("%Y-%m-%d")
                    day_name = day.strftime("%a")[0]
                    full = _is_day_complete(h, ds)
                    partial = _day_pct(h, ds)
                    is_today = ds == today_str
                    with day_cols[6 - d]:
                        if full:
                            st.markdown(f"**:green[{day_name}]**")
                        elif partial > 0:
                            st.markdown(f"**:orange[{day_name}]**")
                        elif is_today:
                            st.markdown(f"**:orange[{day_name}]**")
                        else:
                            st.markdown(f"*{day_name}*")

                c_edit, c_del = st.columns(2)
                with c_edit:
                    if st.button("\u270f\ufe0f Editar", key=f"hedit_{h['id']}", use_container_width=True):
                        st.session_state["hab_editing"] = True
                        st.session_state["hab_edit_id"] = h["id"]
                        st.rerun()
                with c_del:
                    if confirm_delete(h["id"], h["name"], "hab"):
                        habitos = habitos[habitos["id"] != h["id"]]
                        save_df("habitos", habitos)
                        st.rerun()


def _render_stats(habitos):
    """Monthly progress view with stats per habit."""
    if habitos.empty:
        st.info("Agrega habitos para ver estadisticas.")
        return

    # Month selector
    now = datetime.now()
    col_m, col_y = st.columns(2)
    MONTH_NAMES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    month = col_m.selectbox("Mes", range(1, 13), index=now.month - 1,
                            format_func=lambda m: MONTH_NAMES[m - 1], key="hab_stat_month")
    year = col_y.number_input("Ano", min_value=2020, max_value=2030, value=now.year, key="hab_stat_year")

    st.divider()

    # Overall stats for the month
    all_done = 0
    all_total = 0
    for _, h in habitos.iterrows():
        done_days, total_days, _ = _get_month_stats(h, year, month)
        all_done += done_days
        all_total += total_days

    overall_pct = int(all_done / all_total * 100) if all_total > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Tasa de cumplimiento", f"{overall_pct}%")
    c2.metric("Dias cumplidos (total)", all_done)
    c3.metric("Habitos activos", len(habitos))

    st.divider()

    # Per-habit monthly view
    for _, h in habitos.iterrows():
        checks = parse_checks(h.get("checks", "{}"))
        done_days, total_days, pct = _get_month_stats(h, year, month)
        max_streak = _calc_max_streak(h)
        current_streak = _calc_streak(h)

        hab_emoji = h.get("emoji", "\u2b50")
        with st.container(border=True):
            st.markdown(f"### {hab_emoji} {h['name']}")

            # Metrics row
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Cumplimiento", f"{pct}%")
            mc2.metric("Dias", f"{done_days}/{total_days}")
            badge, badge_label = _get_streak_badge(current_streak)
            streak_display = f"\U0001f525 {current_streak}"
            if badge:
                streak_display += f" {badge}"
            mc3.metric("Racha actual", streak_display)
            mc4.metric("Racha maxima", f"\U0001f3c6 {max_streak}")
            if badge_label:
                st.success(f"{badge} {badge_label} Sigue asi!")

            # Monthly calendar grid
            st.caption(f"{MONTH_NAMES[month - 1]} {year}")
            days_in_month = calendar.monthrange(year, month)[1]
            first_weekday = calendar.monthrange(year, month)[0]
            # Weekday of first day (0=Mon)
            first_weekday = datetime(year, month, 1).weekday()

            # Day headers
            day_headers = st.columns(7)
            for i, name in enumerate(["L", "M", "X", "J", "V", "S", "D"]):
                day_headers[i].markdown(f"**{name}**")

            day_num = 1
            today_str = datetime.now().strftime("%Y-%m-%d")
            for week in range(6):
                if day_num > days_in_month:
                    break
                cols = st.columns(7)
                for weekday in range(7):
                    with cols[weekday]:
                        if week == 0 and weekday < first_weekday:
                            st.markdown("")
                        elif day_num <= days_in_month:
                            ds = f"{year}-{month:02d}-{day_num:02d}"
                            full = _is_day_complete(h, ds)
                            partial = _day_pct(h, ds)
                            is_today = ds == today_str
                            if full:
                                st.markdown(f":green[**{day_num}** ✓]")
                            elif partial > 0:
                                pct_label = int(partial * 100)
                                st.markdown(f":orange[**{day_num}** {pct_label}%]")
                            elif is_today:
                                st.markdown(f":orange[**{day_num}**]")
                            else:
                                st.markdown(f"{day_num}")
                            day_num += 1

            # Progress bar
            st.progress(pct / 100, text=f"{pct}% del mes")

    # Best day of week analysis
    st.divider()
    st.subheader("Mejor dia de la semana")
    day_names = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    day_counts = {d: 0 for d in day_names}
    day_totals = {d: 0 for d in day_names}

    for _, h in habitos.iterrows():
        checks = parse_checks(h.get("checks", "{}"))
        for ds in checks.keys():
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d")
                day_name = day_names[dt.weekday()]
                day_totals[day_name] += 1
                if _is_day_complete(h, ds):
                    day_counts[day_name] += 1
            except ValueError:
                pass

    day_data = []
    for d in day_names:
        rate = int(day_counts[d] / day_totals[d] * 100) if day_totals[d] > 0 else 0
        day_data.append({"Dia": d[:3], "Cumplimiento %": rate})

    if any(x["Cumplimiento %"] > 0 for x in day_data):
        chart_df = pd.DataFrame(day_data)
        st.bar_chart(chart_df.set_index("Dia"), color=["#d4a853"])
