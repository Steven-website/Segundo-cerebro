import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts
from core.constants import fmt
from core.utils import confirm_delete, export_csv, get_tipo_cambio


def _register_tx(cat, desc, amount):
    """Register a transaction in Finanzas automatically."""
    txs = get_df("txs")
    new_tx = {
        "id": uid(), "type": "gasto", "desc": desc, "amt": amount,
        "cat": cat, "fecha": datetime.now().strftime("%Y-%m-%d"), "ts": now_ts(),
    }
    txs = pd.concat([pd.DataFrame([new_tx]), txs], ignore_index=True)
    save_df("txs", txs)


def render():
    st.header("Ahorros & Deudas")

    savings = get_df("savings")
    debts = get_df("debts")

    # ═══════════════════════════════
    #  SAVINGS
    # ═══════════════════════════════
    col_title, col_exp, col_add = st.columns([4, 1, 1])
    with col_title:
        st.subheader("Metas de ahorro")
    with col_exp:
        export_csv(savings, "ahorros.csv", "CSV")
    with col_add:
        if st.button("+ Meta", key="add_sav", use_container_width=True, type="primary"):
            st.session_state["sav_editing"] = True
            st.session_state["sav_edit_id"] = None

    if st.session_state.get("sav_editing"):
        edit_id = st.session_state.get("sav_edit_id")
        existing = None
        if edit_id and not savings.empty:
            matches = savings[savings["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("sav_form", clear_on_submit=True):
            st.subheader("Editar meta" if existing is not None else "Nueva meta de ahorro")
            name = st.text_input("Nombre", value=existing["name"] if existing is not None else "")
            c1, c2 = st.columns(2)
            goal = c1.number_input("Meta (₡)", min_value=0.0, step=10000.0, value=float(existing["goal"]) if existing is not None else 0.0)
            current = c2.number_input("Ahorrado", min_value=0.0, step=1000.0, value=float(existing["current"]) if existing is not None else 0.0)
            date = st.date_input("Fecha objetivo (opcional)", value=None)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip() and goal > 0:
                new_row = {
                    "id": edit_id or uid(), "name": name.strip(), "goal": goal,
                    "current": current, "date": str(date) if date else "", "ts": now_ts(),
                }
                if edit_id and not savings.empty:
                    savings = savings[savings["id"] != edit_id]
                save_df("savings", pd.concat([pd.DataFrame([new_row]), savings], ignore_index=True))
                st.session_state["sav_editing"] = False
                st.session_state["sav_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["sav_editing"] = False
                st.session_state["sav_edit_id"] = None
                st.rerun()

    if savings.empty:
        st.info("No hay metas de ahorro.")
    else:
        for _, s in savings.iterrows():
            pct = min(s["current"] / s["goal"], 1.0) if s["goal"] > 0 else 0
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{s['name']}**")
                    st.progress(pct, text=f"{fmt(s['current'])} / {fmt(s['goal'])} ({int(pct*100)}%)")
                    info_parts = []
                    if s.get("date"):
                        info_parts.append(f"Meta: {s['date']}")
                    # Projection
                    remaining = s["goal"] - s["current"]
                    if remaining > 0:
                        payments = get_df("debt_payments")  # reuse for savings tracking
                        # Estimate based on average monthly deposit
                        all_payments = payments[payments.get("debt_id", pd.Series(dtype=str)).str.startswith("sav_")] if not payments.empty else pd.DataFrame()
                        # Simple projection: if they save at current pace
                        if s["current"] > 0 and s.get("date"):
                            try:
                                target = datetime.strptime(s["date"], "%Y-%m-%d")
                                days_left = (target - datetime.now()).days
                                if days_left > 0:
                                    daily_needed = remaining / days_left
                                    monthly_needed = daily_needed * 30
                                    info_parts.append(f"Necesitas {fmt(monthly_needed)}/mes")
                            except (ValueError, TypeError):
                                pass
                        elif s["current"] > 0:
                            info_parts.append(f"Faltan {fmt(remaining)}")
                    if info_parts:
                        st.caption(" | ".join(info_parts))
                with c2:
                    amount = st.number_input("Abonar", min_value=0.0, step=1000.0, key=f"sav_amt_{s['id']}", label_visibility="collapsed")
                    if st.button("Abonar", key=f"sav_add_{s['id']}", use_container_width=True):
                        if amount > 0:
                            new_balance = s["current"] + amount
                            savings.loc[savings["id"] == s["id"], "current"] = new_balance
                            save_df("savings", savings)
                            _record_savings_contribution(s["id"], amount, new_balance)
                            _register_tx("ahorro", f"Ahorro: {s['name']}", amount)
                            st.rerun()
                    c_edit, c_chart = st.columns(2)
                    with c_edit:
                        if st.button("✏️", key=f"sav_edit_{s['id']}", use_container_width=True):
                            st.session_state["sav_editing"] = True
                            st.session_state["sav_edit_id"] = s["id"]
                            st.rerun()
                    with c_chart:
                        if st.button("📈", key=f"sav_chart_{s['id']}", use_container_width=True, help="Historial"):
                            st.session_state["sav_history_id"] = s["id"]
                            st.rerun()
                    if confirm_delete(s["id"], s["name"], "sav"):
                        savings = savings[savings["id"] != s["id"]]
                        save_df("savings", savings)
                        st.rerun()

    # --- Savings history panel ---
    sav_hist_id = st.session_state.get("sav_history_id")
    if sav_hist_id and not savings.empty:
        _render_savings_history(sav_hist_id, savings)

    st.divider()

    # ═══════════════════════════════
    #  DEBTS
    # ═══════════════════════════════
    DEBT_ORIGINS = ["Tarjeta de credito", "Prestamo personal", "Prestamo vehicular",
                    "Prestamo hipotecario", "Financiamiento", "Otro"]

    col_title2, col_add2 = st.columns([5, 1])
    with col_title2:
        st.subheader("Deudas")
    with col_add2:
        if st.button("+ Deuda", key="add_debt", use_container_width=True, type="primary"):
            st.session_state["debt_editing"] = True
            st.session_state["debt_edit_id"] = None

    # --- Month/Year filter ---
    now = datetime.now()
    MONTH_NAMES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    cm, cy = st.columns(2)
    with cm:
        debt_month = st.selectbox("Mes", range(1, 13), index=now.month - 1,
                                  format_func=lambda m: MONTH_NAMES[m - 1],
                                  key="debt_month", label_visibility="collapsed")
    with cy:
        debt_years = list(range(now.year + 1, now.year - 4, -1))
        debt_year = st.selectbox("Año", debt_years, index=debt_years.index(now.year),
                                 key="debt_year", label_visibility="collapsed")

    sel_mes = f"{debt_year}-{debt_month:02d}"

    # --- Add/Edit form ---
    if st.session_state.get("debt_editing"):
        edit_id = st.session_state.get("debt_edit_id")
        existing = None
        if edit_id and not debts.empty:
            matches = debts[debts["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        MONEDAS = ["₡ CRC", "$ USD"]
        with st.form("debt_form", clear_on_submit=True):
            st.subheader("Editar deuda" if existing is not None else "Nueva deuda")
            name = st.text_input("Nombre", value=existing["name"] if existing is not None else "")
            co, cm2 = st.columns(2)
            orig_idx = DEBT_ORIGINS.index(existing["origen"]) if existing is not None and existing.get("origen") in DEBT_ORIGINS else 0
            origen = co.selectbox("Origen", DEBT_ORIGINS, index=orig_idx)
            mon_idx = 1 if existing is not None and existing.get("moneda") == "USD" else 0
            moneda_sel = cm2.selectbox("Moneda", MONEDAS, index=mon_idx)
            c1, c2 = st.columns(2)
            monto_mes = c1.number_input("Deuda del mes", min_value=0.0, step=100.0,
                                        value=float(existing["monto_mes"]) if existing is not None else 0.0)
            pagado = c2.number_input("Pago realizado", min_value=0.0, step=100.0,
                                     value=float(existing["pagado"]) if existing is not None else 0.0)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip() and monto_mes > 0:
                moneda = "USD" if "USD" in moneda_sel else "CRC"
                new_row = {
                    "id": edit_id or uid(), "name": name.strip(), "origen": origen,
                    "moneda": moneda, "monto_mes": monto_mes, "pagado": pagado,
                    "mes": sel_mes, "ts": now_ts(),
                }
                # Register payment as transaction in Finanzas (always in CRC)
                if pagado > 0:
                    old_pagado = float(existing["pagado"]) if existing is not None else 0.0
                    diff_pago = pagado - old_pagado
                    if diff_pago > 0:
                        if moneda == "USD":
                            tc = get_tipo_cambio()
                            monto_crc = diff_pago * tc
                            _register_tx("deudas", f"Deuda: {name.strip()} ({origen}) ${diff_pago:,.2f}", monto_crc)
                        else:
                            _register_tx("deudas", f"Deuda: {name.strip()} ({origen})", diff_pago)
                if edit_id and not debts.empty:
                    debts = debts[debts["id"] != edit_id]
                save_df("debts", pd.concat([pd.DataFrame([new_row]), debts], ignore_index=True))
                st.session_state["debt_editing"] = False
                st.session_state["debt_edit_id"] = None
                st.rerun()
            if cancelled:
                st.session_state["debt_editing"] = False
                st.session_state["debt_edit_id"] = None
                st.rerun()

    # --- Filter debts by selected month ---
    month_debts = debts[debts["mes"] == sel_mes] if not debts.empty and "mes" in debts.columns else pd.DataFrame()

    if month_debts.empty:
        st.info(f"No hay deudas en {MONTH_NAMES[debt_month - 1]} {debt_year}.")
    else:
        # Ensure moneda column exists, default to CRC
        if "moneda" not in month_debts.columns:
            month_debts["moneda"] = "CRC"
        month_debts["moneda"] = month_debts["moneda"].fillna("CRC").replace("", "CRC")

        # Summary split by currency
        for cur in ["CRC", "USD"]:
            cur_debts = month_debts[month_debts["moneda"] == cur]
            if cur_debts.empty:
                continue
            sym = "₡" if cur == "CRC" else "$"
            fmt_c = lambda v, s=sym: f"{s}{v:,.0f}" if s == "₡" else f"{s}{v:,.2f}"
            total_d = cur_debts["monto_mes"].sum()
            total_p = cur_debts["pagado"].sum()
            pend = total_d - total_p
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric(f"Deuda {cur}", fmt_c(total_d))
            mc2.metric("Pagado", fmt_c(total_p))
            mc3.metric("Pendiente", fmt_c(pend),
                        delta="Al dia" if pend <= 0 else "Pendiente",
                        delta_color="normal" if pend <= 0 else "inverse")

        # Group by origen
        origenes = month_debts["origen"].unique() if "origen" in month_debts.columns else []
        for orig in sorted(origenes):
            grupo = month_debts[month_debts["origen"] == orig]
            st.markdown(f"**💳 {orig}**")
            for _, d in grupo.iterrows():
                mon = d.get("moneda", "CRC") or "CRC"
                sym = "₡" if mon == "CRC" else "$"
                fmt_d = lambda v, s=sym: f"{s}{v:,.0f}" if s == "₡" else f"{s}{v:,.2f}"
                pend = d["monto_mes"] - d["pagado"]
                status = "✅" if pend <= 0 else f":red[Pendiente {fmt_d(pend)}]"
                col_info, col_act = st.columns([5, 1])
                with col_info:
                    st.markdown(f"{d['name']} — {fmt_d(d['monto_mes'])} — Pagado: {fmt_d(d['pagado'])} — {status}")
                with col_act:
                    ca, cb = st.columns(2)
                    with ca:
                        if st.button("✏️", key=f"debt_edit_{d['id']}"):
                            st.session_state["debt_editing"] = True
                            st.session_state["debt_edit_id"] = d["id"]
                            st.rerun()
                    with cb:
                        if confirm_delete(d["id"], d["name"], "debt"):
                            debts = debts[debts["id"] != d["id"]]
                            save_df("debts", debts)
                            st.rerun()


def _record_savings_contribution(saving_id, amount, new_balance):
    """Record a savings contribution in history."""
    hist = get_df("savings_hist")
    new_entry = {
        "id": uid(),
        "saving_id": saving_id,
        "monto": amount,
        "balance": new_balance,
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "ts": now_ts(),
    }
    hist = pd.concat([pd.DataFrame([new_entry]), hist], ignore_index=True)
    save_df("savings_hist", hist)


def _render_savings_history(saving_id, savings):
    """Show contribution history and progress chart for a savings goal."""
    sav_match = savings[savings["id"] == saving_id]
    if sav_match.empty:
        return

    sav = sav_match.iloc[0]
    hist = get_df("savings_hist")
    sav_hist = hist[hist["saving_id"] == saving_id].sort_values("ts", ascending=True) if not hist.empty else pd.DataFrame()

    st.divider()
    col_t, col_close = st.columns([5, 1])
    with col_t:
        st.subheader(f"Historial: {sav['name']}")
    with col_close:
        if st.button("Cerrar", key="close_sav_hist"):
            st.session_state["sav_history_id"] = None
            st.rerun()

    if sav_hist.empty:
        st.info("No hay aportes registrados. Los proximos aportes apareceran aqui.")
        return

    # Progress chart
    chart_data = sav_hist[["fecha", "balance"]].copy()
    chart_data.columns = ["Fecha", "Balance"]
    chart_data = chart_data.set_index("Fecha")
    st.line_chart(chart_data, color=["#4a9e7a"])

    # Stats
    total_contributions = sav_hist["monto"].sum()
    num_contributions = len(sav_hist)
    avg_contribution = total_contributions / num_contributions if num_contributions > 0 else 0

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Total aportado", fmt(total_contributions))
    sc2.metric("Aportes", num_contributions)
    sc3.metric("Promedio por aporte", fmt(avg_contribution))

    # Contribution list
    for _, h in sav_hist.sort_values("ts", ascending=False).iterrows():
        st.markdown(f"- **{h['fecha']}** — Aporte: {fmt(h['monto'])} — Balance: {fmt(h['balance'])}")
