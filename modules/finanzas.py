import streamlit as st
import pandas as pd
from datetime import datetime, date
from core.data import get_df, save_df, uid, now_ts
from core.constants import CAT_ICONS, TX_CATS_GASTO, TX_CATS_INGRESO, BUDGET_DEFAULT, fmt
from core.utils import confirm_delete, export_csv

FREQ_OPTIONS = {"mensual": "Mensual", "quincenal": "Quincenal", "semanal": "Semanal"}


def _auto_generate_recurring(txs):
    """Auto-generate transactions from active recurring subscriptions."""
    recurrentes = get_df("tx_recurrentes")
    if recurrentes.empty:
        return txs

    active = recurrentes[recurrentes["activa"] == True] if "activa" in recurrentes.columns else recurrentes
    if active.empty:
        return txs

    today = date.today()
    new_txs = []

    for _, r in active.iterrows():
        freq = r.get("frecuencia", "mensual")
        dia = int(r["dia"])
        fecha_inicio_str = r.get("fecha_inicio", "")
        try:
            fecha_inicio = date.fromisoformat(fecha_inicio_str) if fecha_inicio_str else None
        except (ValueError, TypeError):
            fecha_inicio = None

        # Determine which dates to check based on frequency
        dates_to_check = []
        if freq == "mensual":
            try:
                target = date(today.year, today.month, min(dia, 28))
            except ValueError:
                target = date(today.year, today.month, 28)
            if target <= today and (not fecha_inicio or target >= fecha_inicio):
                dates_to_check.append(target)
        elif freq == "quincenal":
            for d in [dia, min(dia + 15, 28)]:
                try:
                    target = date(today.year, today.month, min(d, 28))
                except ValueError:
                    target = date(today.year, today.month, 28)
                if target <= today and (not fecha_inicio or target >= fecha_inicio):
                    dates_to_check.append(target)
        elif freq == "semanal":
            from datetime import timedelta
            d = date(today.year, today.month, 1)
            while d <= today:
                if d.isoweekday() == min(dia, 7):
                    if not fecha_inicio or d >= fecha_inicio:
                        dates_to_check.append(d)
                d += timedelta(days=1)

        for target_date in dates_to_check:
            target_str = str(target_date)
            # Check if already generated (same desc + same date)
            already_exists = False
            if not txs.empty:
                matches = txs[(txs["desc"] == r["desc"]) & (txs["fecha"] == target_str)]
                already_exists = not matches.empty

            if not already_exists:
                new_txs.append({
                    "id": uid(), "type": r["type"], "desc": r["desc"],
                    "amt": float(r["amt"]), "cat": r["cat"],
                    "fecha": target_str, "ts": now_ts(),
                })

    if new_txs:
        txs = pd.concat([pd.DataFrame(new_txs), txs], ignore_index=True)
        save_df("txs", txs)

    return txs


def _get_month_txs(txs, year=None, month=None):
    if txs.empty:
        return txs
    now = datetime.now()
    y = year or now.year
    m = month or now.month
    prefix = f"{y}-{m:02d}"
    return txs[txs["fecha"].str.startswith(prefix)]


def _filter_by_period(txs_month, period, now):
    """Filter month transactions by period (mensual, quincena1, quincena2)."""
    if period == "mensual" or txs_month.empty:
        return txs_month
    # Extract day from fecha string
    days = txs_month["fecha"].str.split("-").str[2].astype(int)
    if period == "quincena1":
        return txs_month[days <= 15]
    else:  # quincena2
        return txs_month[days > 15]


def render():
    st.header("Finanzas")

    txs = get_df("txs")
    txs = _auto_generate_recurring(txs)
    budget_df = get_df("budget")

    if budget_df.empty:
        budget = BUDGET_DEFAULT.copy()
    else:
        budget = dict(zip(budget_df["cat"], budget_df["amt"]))
        for k, v in BUDGET_DEFAULT.items():
            budget.setdefault(k, v)

    now = datetime.now()

    # --- Period selector ---
    period_options = {"mensual": "Mes completo", "quincena1": "Quincena 1 (1-15)", "quincena2": "Quincena 2 (16-fin)"}
    today_day = now.day
    default_idx = 1 if today_day <= 15 else 2  # auto-select current quincena
    period = st.radio(
        "Periodo", list(period_options.keys()),
        format_func=lambda x: period_options[x],
        horizontal=True, index=default_idx, key="fin_period",
        label_visibility="collapsed",
    )

    month_txs = _get_month_txs(txs)
    period_txs = _filter_by_period(month_txs, period, now)

    ingresos = float(period_txs[period_txs["type"] == "ingreso"]["amt"].sum()) if not period_txs.empty else 0
    gastos = float(period_txs[period_txs["type"] == "gasto"]["amt"].sum()) if not period_txs.empty else 0
    balance = ingresos - gastos

    # --- Comparison vs previous period ---
    prev_m = now.month - 1
    prev_y = now.year
    if prev_m <= 0:
        prev_m += 12
        prev_y -= 1
    prev_txs = _get_month_txs(txs, prev_y, prev_m)
    prev_period_txs = _filter_by_period(prev_txs, period, now)
    prev_gastos = float(prev_period_txs[prev_period_txs["type"] == "gasto"]["amt"].sum()) if not prev_period_txs.empty else 0
    prev_ingresos = float(prev_period_txs[prev_period_txs["type"] == "ingreso"]["amt"].sum()) if not prev_period_txs.empty else 0

    period_label = period_options[period]

    # --- Summary metrics ---
    c1, c2 = st.columns(2)
    inc_delta = None
    if prev_ingresos > 0:
        inc_change = int((ingresos - prev_ingresos) / prev_ingresos * 100)
        inc_delta = f"{inc_change:+d}% vs anterior"
    c1.metric("Ingresos", fmt(ingresos), delta=inc_delta)

    exp_delta = None
    if prev_gastos > 0:
        exp_change = int((gastos - prev_gastos) / prev_gastos * 100)
        exp_delta = f"{exp_change:+d}% vs anterior"
    c2.metric("Gastos", fmt(gastos), delta=exp_delta, delta_color="inverse")

    st.metric("Balance", fmt(balance), delta="Positivo" if balance >= 0 else "Negativo", delta_color="normal" if balance >= 0 else "inverse")

    st.divider()

    # --- Charts ---
    if not txs.empty:
        st.subheader("Tendencias")
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            # Monthly income vs expenses (last 6 months)
            months_data = []
            for i in range(5, -1, -1):
                m = now.month - i
                y = now.year
                if m <= 0:
                    m += 12
                    y -= 1
                m_txs = _get_month_txs(txs, y, m)
                m_inc = float(m_txs[m_txs["type"] == "ingreso"]["amt"].sum()) if not m_txs.empty else 0
                m_exp = float(m_txs[m_txs["type"] == "gasto"]["amt"].sum()) if not m_txs.empty else 0
                label = f"{y}-{m:02d}"
                months_data.append({"Mes": label, "Ingresos": m_inc, "Gastos": m_exp})

            chart_df = pd.DataFrame(months_data)
            if chart_df[["Ingresos", "Gastos"]].sum().sum() > 0:
                st.caption("Ingresos vs Gastos (6 meses)")
                st.bar_chart(chart_df.set_index("Mes"), color=["#4a9e7a", "#c96a6a"])

        with col_chart2:
            # Expenses by category (current month)
            if not month_txs.empty:
                gastos_df = month_txs[month_txs["type"] == "gasto"]
                if not gastos_df.empty:
                    cat_totals = gastos_df.groupby("cat")["amt"].sum().reset_index()
                    cat_totals.columns = ["Categoria", "Monto"]
                    cat_totals["Categoria"] = cat_totals["Categoria"].apply(lambda x: f"{CAT_ICONS.get(x, '')} {x.capitalize()}")
                    st.caption("Gastos por categoria (mes actual)")
                    st.bar_chart(cat_totals.set_index("Categoria"))

        st.divider()

    # --- Add transaction ---
    col_ing, col_gas, col_exp = st.columns([2, 2, 1])
    with col_ing:
        if st.button("+ Ingreso", use_container_width=True):
            st.session_state["tx_adding"] = "ingreso"
            st.session_state["tx_editing_id"] = None
    with col_gas:
        if st.button("+ Gasto", use_container_width=True, type="primary"):
            st.session_state["tx_adding"] = "gasto"
            st.session_state["tx_editing_id"] = None
    with col_exp:
        export_csv(txs, "transacciones.csv", "\U0001f4e5 CSV")

    # --- Add/Edit transaction form ---
    if st.session_state.get("tx_adding") or st.session_state.get("tx_editing_id"):
        edit_id = st.session_state.get("tx_editing_id")
        existing = None
        if edit_id and not txs.empty:
            matches = txs[txs["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        tx_type = existing["type"] if existing is not None else st.session_state.get("tx_adding", "gasto")
        cats = TX_CATS_INGRESO if tx_type == "ingreso" else TX_CATS_GASTO

        with st.form("tx_form", clear_on_submit=True):
            st.subheader(f"{'Editar' if existing is not None else 'Nuevo'} {'ingreso' if tx_type == 'ingreso' else 'gasto'}")
            desc = st.text_input("Descripcion", value=existing["desc"] if existing is not None else "")
            c1, c2 = st.columns(2)
            amt = c1.number_input("Monto", min_value=0.0, step=1000.0, value=float(existing["amt"]) if existing is not None else 0.0)
            cat_idx = cats.index(existing["cat"]) if existing is not None and existing["cat"] in cats else 0
            cat = c2.selectbox("Categoria", cats, index=cat_idx, format_func=lambda x: f"{CAT_ICONS.get(x, '')} {x.capitalize()}")
            fecha = st.date_input("Fecha")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and desc.strip() and amt > 0:
                new_row = {
                    "id": edit_id or uid(), "type": tx_type, "desc": desc.strip(),
                    "amt": amt, "cat": cat, "fecha": str(fecha), "ts": now_ts(),
                }
                if edit_id and not txs.empty:
                    txs = txs[txs["id"] != edit_id]
                new_df = pd.concat([pd.DataFrame([new_row]), txs], ignore_index=True)
                save_df("txs", new_df)
                st.session_state["tx_adding"] = None
                st.session_state["tx_editing_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["tx_adding"] = None
                st.session_state["tx_editing_id"] = None
                st.rerun()

    st.divider()

    # --- Presupuesto vs Realidad ---
    with st.expander("📊 Presupuesto vs Realidad", expanded=False):
        # Calculate monthly totals
        total_pres_mensual = sum(v for k, v in budget.items() if k != "ingreso")
        total_gasto_mensual = float(month_txs[month_txs["type"] == "gasto"]["amt"].sum()) if not month_txs.empty else 0
        # Calculate biweekly totals
        total_pres_quincenal = total_pres_mensual / 2
        q1_txs = _filter_by_period(month_txs, "quincena1", now)
        q2_txs = _filter_by_period(month_txs, "quincena2", now)
        gasto_q1 = float(q1_txs[q1_txs["type"] == "gasto"]["amt"].sum()) if not q1_txs.empty else 0
        gasto_q2 = float(q2_txs[q2_txs["type"] == "gasto"]["amt"].sum()) if not q2_txs.empty else 0
        today_day = now.day
        gasto_quincenal = gasto_q1 if today_day <= 15 else gasto_q2

        st.markdown("**Totales mensuales**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Presupuesto", fmt(total_pres_mensual))
        m2.metric("Gastado", fmt(total_gasto_mensual))
        diff_m = total_pres_mensual - total_gasto_mensual
        m3.metric("Disponible", fmt(diff_m), delta="OK" if diff_m >= 0 else "Excedido", delta_color="normal" if diff_m >= 0 else "inverse")

        st.markdown("**Totales quincenales** (quincena actual)")
        q1, q2, q3 = st.columns(3)
        q1.metric("Presupuesto", fmt(total_pres_quincenal))
        q2.metric("Gastado", fmt(gasto_quincenal))
        diff_q = total_pres_quincenal - gasto_quincenal
        q3.metric("Disponible", fmt(diff_q), delta="OK" if diff_q >= 0 else "Excedido", delta_color="normal" if diff_q >= 0 else "inverse")

        st.divider()

        # Detail per category (uses selected period)
        st.markdown(f"**Detalle por categoria ({period_label})**")
        budget_factor = 0.5 if period != "mensual" else 1.0
        for cat, limit in budget.items():
            if cat == "ingreso":
                continue
            icon = CAT_ICONS.get(cat, "\U0001f4e6")
            adj_limit = limit * budget_factor
            spent = float(period_txs[(period_txs["type"] == "gasto") & (period_txs["cat"] == cat)]["amt"].sum()) if not period_txs.empty else 0
            diff = adj_limit - spent
            if adj_limit == 0 and spent == 0:
                continue
            col_cat, col_pres, col_real, col_diff = st.columns([3, 2, 2, 2])
            with col_cat:
                st.markdown(f"{icon} **{cat.capitalize()}**")
            with col_pres:
                st.caption(f"Pres: {fmt(adj_limit)}")
            with col_real:
                st.caption(f"Real: {fmt(spent)}")
            with col_diff:
                if diff >= 0:
                    st.caption(f"✅ {fmt(diff)}")
                else:
                    st.caption(f"🔴 {fmt(abs(diff))}")

    # --- Budget progress (collapsible) ---
    budget_label = "📊 Presupuesto quincenal" if period != "mensual" else "📊 Presupuesto mensual"
    with st.expander(budget_label):
        budget_factor = 0.5 if period != "mensual" else 1.0
        for cat, limit in budget.items():
            if cat == "ingreso":
                continue
            icon = CAT_ICONS.get(cat, "\U0001f4e6")
            adj_limit = limit * budget_factor
            spent = float(period_txs[(period_txs["type"] == "gasto") & (period_txs["cat"] == cat)]["amt"].sum()) if not period_txs.empty else 0
            if adj_limit == 0 and spent == 0:
                continue
            pct = min(spent / adj_limit, 1.0) if adj_limit > 0 else 0

            st.markdown(f"{icon} **{cat.capitalize()}** • {fmt(spent)} / {fmt(adj_limit)}")
            st.progress(pct)

        st.divider()
        st.markdown("**✏️ Editar presupuesto**")
        with st.form("budget_form"):
            new_budget = {}
            for cat, val in budget.items():
                if cat == "ingreso":
                    continue
                icon = CAT_ICONS.get(cat, "")
                new_budget[cat] = st.number_input(f"{icon} {cat.capitalize()}", value=float(val), step=10000.0, key=f"bud_{cat}")
            if st.form_submit_button("Guardar presupuesto"):
                budget_rows = [{"cat": k, "amt": v} for k, v in new_budget.items()]
                save_df("budget", pd.DataFrame(budget_rows))
                st.rerun()

    # --- Transactions ---
    with st.expander("💳 Transacciones del periodo"):
        st.subheader("Transacciones del periodo")
        if period_txs.empty:
            st.info("Sin transacciones en este periodo.")
        else:
            recent = period_txs.sort_values("ts", ascending=False).head(15)
            for _, tx in recent.iterrows():
                icon = CAT_ICONS.get(tx["cat"], "\U0001f4e6")
                sign = "+" if tx["type"] == "ingreso" else "-"
                color = "green" if tx["type"] == "ingreso" else "red"

                col_info, col_actions = st.columns([5, 1])
                with col_info:
                    st.markdown(f"{icon} {tx['desc']} \u2022 :{color}[{sign}{fmt(tx['amt'])}] \u2022 `{tx['fecha']}`")
                with col_actions:
                    ca, cb = st.columns(2)
                    with ca:
                        if st.button("✏️", key=f"tx_edit_{tx['id']}"):
                            st.session_state["tx_editing_id"] = tx["id"]
                            st.session_state["tx_adding"] = None
                            st.rerun()
                    with cb:
                        if confirm_delete(tx["id"], tx["desc"], "tx"):
                            txs = txs[txs["id"] != tx["id"]]
                            save_df("txs", txs)
                            st.rerun()

    # ═══ SUSCRIPCIONES / RECURRENTES ═══
    st.divider()
    _render_recurrentes()


def _render_recurrentes():
    """Manage recurring transactions (subscriptions)."""
    st.subheader("Suscripciones y recurrentes")

    recurrentes = get_df("tx_recurrentes")

    col_add, _ = st.columns([1, 5])
    with col_add:
        if st.button("+ Suscripcion", use_container_width=True):
            st.session_state["rec_editing"] = True
            st.session_state["rec_edit_id"] = None

    # --- Add/Edit form ---
    if st.session_state.get("rec_editing"):
        edit_id = st.session_state.get("rec_edit_id")
        existing = None
        if edit_id and not recurrentes.empty:
            matches = recurrentes[recurrentes["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("rec_form", clear_on_submit=True):
            st.subheader("Editar recurrente" if existing is not None else "Nueva recurrente")
            desc = st.text_input("Descripcion", value=existing["desc"] if existing is not None else "")
            c1, c2, c3 = st.columns(3)
            tx_type = c1.selectbox("Tipo", ["gasto", "ingreso"],
                                   index=0 if existing is None or existing["type"] == "gasto" else 1,
                                   format_func=lambda x: "Gasto" if x == "gasto" else "Ingreso")
            amt = c2.number_input("Monto", min_value=0.0, step=1000.0,
                                  value=float(existing["amt"]) if existing is not None else 0.0)
            cats = TX_CATS_INGRESO if (existing is not None and existing["type"] == "ingreso") or (existing is None and tx_type == "ingreso") else TX_CATS_GASTO
            cat_idx = cats.index(existing["cat"]) if existing is not None and existing["cat"] in cats else 0
            cat = c3.selectbox("Categoria", cats, index=cat_idx,
                               format_func=lambda x: f"{CAT_ICONS.get(x, '')} {x.capitalize()}")

            c4, c5 = st.columns(2)
            freq_keys = list(FREQ_OPTIONS.keys())
            freq = c4.selectbox("Frecuencia", freq_keys,
                                index=freq_keys.index(existing["frecuencia"]) if existing is not None and existing.get("frecuencia") in freq_keys else 0,
                                format_func=lambda x: FREQ_OPTIONS[x])
            dia = c5.number_input("Dia del cobro", min_value=1, max_value=31, step=1,
                                  value=int(existing["dia"]) if existing is not None else 1)

            existing_fecha = None
            if existing is not None and existing.get("fecha_inicio"):
                try:
                    existing_fecha = date.fromisoformat(existing["fecha_inicio"])
                except (ValueError, TypeError):
                    pass
            fecha_inicio = st.date_input("Fecha de inicio", value=existing_fecha or date.today())

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and desc.strip() and amt > 0:
                new_row = {
                    "id": edit_id or uid(), "type": tx_type, "desc": desc.strip(),
                    "amt": amt, "cat": cat, "frecuencia": freq, "dia": dia,
                    "fecha_inicio": str(fecha_inicio), "activa": True, "ts": now_ts(),
                }
                if edit_id and not recurrentes.empty:
                    recurrentes = recurrentes[recurrentes["id"] != edit_id]
                save_df("tx_recurrentes", pd.concat([pd.DataFrame([new_row]), recurrentes], ignore_index=True))
                st.session_state["rec_editing"] = False
                st.session_state["rec_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["rec_editing"] = False
                st.session_state["rec_edit_id"] = None
                st.rerun()

    # --- List ---
    if recurrentes.empty:
        st.info("No hay suscripciones configuradas.")
        return

    active = recurrentes[recurrentes["activa"] == True] if "activa" in recurrentes.columns else recurrentes
    inactive = recurrentes[recurrentes["activa"] == False] if "activa" in recurrentes.columns else pd.DataFrame()

    total_mensual = 0
    for _, r in active.iterrows():
        amt = float(r["amt"])
        freq = r.get("frecuencia", "mensual")
        if freq == "quincenal":
            amt *= 2
        elif freq == "semanal":
            amt *= 4
        if r["type"] == "gasto":
            total_mensual += amt
        else:
            total_mensual -= amt

    st.caption(f"Gasto mensual estimado en suscripciones: **{fmt(total_mensual)}**")

    for _, r in active.iterrows():
        icon = CAT_ICONS.get(r["cat"], "\U0001f4e6")
        sign = "-" if r["type"] == "gasto" else "+"
        color = "red" if r["type"] == "gasto" else "green"
        freq_label = FREQ_OPTIONS.get(r.get("frecuencia", "mensual"), "Mensual")

        col_info, col_actions = st.columns([5, 1])
        with col_info:
            desde = f" \u2022 Desde {r['fecha_inicio']}" if r.get("fecha_inicio") else ""
            st.markdown(f"{icon} **{r['desc']}** \u2022 :{color}[{sign}{fmt(r['amt'])}] \u2022 {freq_label} \u2022 Dia {int(r['dia'])}{desde}")
        with col_actions:
            ca, cb = st.columns(2)
            with ca:
                if st.button("✏️", key=f"rec_edit_{r['id']}"):
                    st.session_state["rec_editing"] = True
                    st.session_state["rec_edit_id"] = r["id"]
                    st.rerun()
            with cb:
                if confirm_delete(r["id"], r["desc"], "rec"):
                    recurrentes = recurrentes[recurrentes["id"] != r["id"]]
                    save_df("tx_recurrentes", recurrentes)
                    st.rerun()

    if not inactive.empty:
        with st.expander(f"Inactivas ({len(inactive)})"):
            for _, r in inactive.iterrows():
                icon = CAT_ICONS.get(r["cat"], "\U0001f4e6")
                st.markdown(f"~~{icon} {r['desc']} \u2022 {fmt(r['amt'])}~~")
                if st.button("Reactivar", key=f"rec_react_{r['id']}"):
                    recurrentes.loc[recurrentes["id"] == r["id"], "activa"] = True
                    save_df("tx_recurrentes", recurrentes)
                    st.rerun()
