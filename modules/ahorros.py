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
    MONEDAS = ["₡ CRC", "$ USD"]

    col_title2, col_add2 = st.columns([5, 1])
    with col_title2:
        st.subheader("Deudas")
    with col_add2:
        if st.button("+ Deuda", key="add_debt", use_container_width=True, type="primary"):
            st.session_state["debt_editing"] = True
            st.session_state["debt_edit_id"] = None

    monthly = get_df("debt_monthly")
    tc = get_tipo_cambio()

    # --- Migrate old format debts (monto_mes/pagado/mes) to new format ---
    if not debts.empty and "monto_mes" in debts.columns:
        migrated_debts = []
        migrated_monthly = []
        for _, old in debts.iterrows():
            debt_id = old["id"]
            migrated_debts.append({
                "id": debt_id, "name": old["name"],
                "origen": old.get("origen", "Otro"),
                "moneda": old.get("moneda", "CRC") or "CRC",
                "total_original": float(old.get("monto_mes", 0)),
                "ts": old["ts"],
            })
            if old.get("mes"):
                migrated_monthly.append({
                    "id": uid(), "debt_id": debt_id, "mes": old["mes"],
                    "saldo": float(old.get("monto_mes", 0)) - float(old.get("pagado", 0)),
                    "pago": float(old.get("pagado", 0)), "ts": old["ts"],
                })
        debts = pd.DataFrame(migrated_debts)
        save_df("debts", debts)
        if migrated_monthly:
            new_monthly = pd.DataFrame(migrated_monthly)
            monthly = pd.concat([new_monthly, monthly], ignore_index=True)
            save_df("debt_monthly", monthly)

    def _fmt_money(val, moneda):
        if moneda == "USD":
            return f"${val:,.2f}"
        return f"₡{val:,.0f}"

    # --- Add/Edit debt form ---
    if st.session_state.get("debt_editing"):
        edit_id = st.session_state.get("debt_edit_id")
        existing = None
        if edit_id and not debts.empty:
            matches = debts[debts["id"] == edit_id]
            if not matches.empty:
                existing = matches.iloc[0]

        with st.form("debt_form", clear_on_submit=True):
            st.subheader("Editar deuda" if existing is not None else "Nueva deuda")
            name = st.text_input("Nombre", value=existing["name"] if existing is not None else "")
            co, cm2 = st.columns(2)
            orig_idx = DEBT_ORIGINS.index(existing["origen"]) if existing is not None and existing.get("origen") in DEBT_ORIGINS else 0
            origen = co.selectbox("Origen", DEBT_ORIGINS, index=orig_idx)
            mon_idx = 1 if existing is not None and existing.get("moneda") == "USD" else 0
            moneda_sel = cm2.selectbox("Moneda", MONEDAS, index=mon_idx)
            total_orig = st.number_input("Deuda total original", min_value=0.0, step=100.0,
                                         value=float(existing["total_original"]) if existing is not None else 0.0)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip() and total_orig > 0:
                moneda = "USD" if "USD" in moneda_sel else "CRC"
                new_row = {
                    "id": edit_id or uid(), "name": name.strip(), "origen": origen,
                    "moneda": moneda, "total_original": total_orig, "ts": now_ts(),
                }
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

    # --- List debts ---
    if debts.empty:
        st.info("No hay deudas registradas. Agrega una con + Deuda.")
    else:
        # Ensure columns
        if "moneda" not in debts.columns:
            debts["moneda"] = "CRC"
        debts["moneda"] = debts["moneda"].fillna("CRC").replace("", "CRC")
        if "total_original" not in debts.columns:
            debts["total_original"] = 0.0

        for _, debt in debts.iterrows():
            mon = debt.get("moneda", "CRC") or "CRC"
            debt_monthly = monthly[monthly["debt_id"] == debt["id"]].sort_values("mes") if not monthly.empty else pd.DataFrame()
            total_pagado = float(debt_monthly["pago"].sum()) if not debt_monthly.empty else 0.0
            ultimo_saldo = float(debt_monthly.iloc[-1]["saldo"]) if not debt_monthly.empty else float(debt["total_original"])
            total_orig = float(debt["total_original"])
            pct = min(total_pagado / total_orig, 1.0) if total_orig > 0 else 0

            with st.container(border=True):
                # Header
                crc_equiv = f" (₡{total_orig * tc:,.0f})" if mon == "USD" else ""
                st.markdown(f"**{debt['name']}** — {debt.get('origen', '')} — {_fmt_money(total_orig, mon)}{crc_equiv}")
                st.progress(pct, text=f"Pagado: {_fmt_money(total_pagado, mon)} / {_fmt_money(total_orig, mon)} ({int(pct*100)}%)")

                saldo_label = f"Saldo actual: {_fmt_money(ultimo_saldo, mon)}"
                if mon == "USD":
                    saldo_label += f" (₡{ultimo_saldo * tc:,.0f})"
                st.caption(saldo_label)

                # --- Monthly record form ---
                with st.expander("📝 Registrar mes"):
                    now = datetime.now()
                    MONTH_NAMES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    cm_d, cy_d = st.columns(2)
                    with cm_d:
                        rec_month = st.selectbox("Mes", range(1, 13), index=now.month - 1,
                                                 format_func=lambda m: MONTH_NAMES[m - 1],
                                                 key=f"dm_{debt['id']}", label_visibility="collapsed")
                    with cy_d:
                        rec_years = list(range(now.year + 1, now.year - 4, -1))
                        rec_year = st.selectbox("Año", rec_years, index=rec_years.index(now.year),
                                                key=f"dy_{debt['id']}", label_visibility="collapsed")
                    rec_mes = f"{rec_year}-{rec_month:02d}"

                    # Check existing record for this month
                    existing_rec = None
                    if not debt_monthly.empty:
                        match = debt_monthly[debt_monthly["mes"] == rec_mes]
                        if not match.empty:
                            existing_rec = match.iloc[0]

                    with st.form(f"dm_form_{debt['id']}", clear_on_submit=False):
                        cs, cp = st.columns(2)
                        saldo = cs.number_input("Saldo del mes", min_value=0.0, step=100.0,
                                                value=float(existing_rec["saldo"]) if existing_rec is not None else float(ultimo_saldo))
                        pago = cp.number_input("Pago realizado", min_value=0.0, step=100.0,
                                               value=float(existing_rec["pago"]) if existing_rec is not None else 0.0)
                        if st.form_submit_button("Guardar registro", type="primary"):
                            new_rec = {
                                "id": existing_rec["id"] if existing_rec is not None else uid(),
                                "debt_id": debt["id"], "mes": rec_mes,
                                "saldo": saldo, "pago": pago, "ts": now_ts(),
                            }
                            updated = monthly.copy()
                            if existing_rec is not None:
                                updated = updated[updated["id"] != existing_rec["id"]]
                            # Register payment diff in Finanzas
                            old_pago = float(existing_rec["pago"]) if existing_rec is not None else 0.0
                            diff_pago = pago - old_pago
                            if diff_pago > 0:
                                if mon == "USD":
                                    _register_tx("deudas", f"Deuda: {debt['name']} ({debt.get('origen', '')}) ${diff_pago:,.2f}", diff_pago * tc)
                                else:
                                    _register_tx("deudas", f"Deuda: {debt['name']} ({debt.get('origen', '')})", diff_pago)
                            save_df("debt_monthly", pd.concat([pd.DataFrame([new_rec]), updated], ignore_index=True))
                            st.rerun()

                # --- History chart ---
                if not debt_monthly.empty and len(debt_monthly) > 0:
                    with st.expander("📈 Historial"):
                        chart_data = debt_monthly[["mes", "saldo", "pago"]].copy()
                        chart_data.columns = ["Mes", "Saldo", "Pago"]
                        chart_data = chart_data.set_index("Mes")

                        st.caption("Saldo de deuda por mes")
                        st.line_chart(chart_data[["Saldo"]], color=["#c96a6a"])
                        st.caption("Pagos por mes")
                        st.bar_chart(chart_data[["Pago"]], color=["#4a9e7a"])

                        # Stats
                        total_pagos = debt_monthly["pago"].sum()
                        meses = len(debt_monthly)
                        promedio = total_pagos / meses if meses > 0 else 0
                        sc1, sc2, sc3 = st.columns(3)
                        sc1.metric("Total pagado", _fmt_money(total_pagos, mon))
                        sc2.metric("Meses registrados", meses)
                        sc3.metric("Promedio/mes", _fmt_money(promedio, mon))

                        if ultimo_saldo > 0 and promedio > 0:
                            meses_restantes = int(ultimo_saldo / promedio) + 1
                            st.caption(f"A este ritmo, te faltan ~{meses_restantes} meses para liquidar")

                        # Table
                        for _, r in debt_monthly.sort_values("mes", ascending=False).iterrows():
                            st.markdown(f"**{r['mes']}** — Saldo: {_fmt_money(r['saldo'], mon)} — Pago: {_fmt_money(r['pago'], mon)}")

                # --- Edit/Delete ---
                ce, cd = st.columns(2)
                with ce:
                    if st.button("✏️ Editar", key=f"debt_edit_{debt['id']}", use_container_width=True):
                        st.session_state["debt_editing"] = True
                        st.session_state["debt_edit_id"] = debt["id"]
                        st.rerun()
                with cd:
                    if confirm_delete(debt["id"], debt["name"], "debt"):
                        debts = debts[debts["id"] != debt["id"]]
                        # Also delete monthly records
                        if not monthly.empty:
                            monthly = monthly[monthly["debt_id"] != debt["id"]]
                            save_df("debt_monthly", monthly)
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
