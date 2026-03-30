import streamlit as st
import pandas as pd
from datetime import datetime
from core.data import get_df, save_df, uid, now_ts
from core.constants import fmt
from core.utils import confirm_delete, export_csv


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
                        from datetime import datetime, timedelta
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
                            savings.loc[savings["id"] == s["id"], "current"] += amount
                            save_df("savings", savings)
                            st.rerun()
                    if st.button("✏️", key=f"sav_edit_{s['id']}", use_container_width=True):
                        st.session_state["sav_editing"] = True
                        st.session_state["sav_edit_id"] = s["id"]
                        st.rerun()
                    if confirm_delete(s["id"], s["name"], "sav"):
                        savings = savings[savings["id"] != s["id"]]
                        save_df("savings", savings)
                        st.rerun()

    st.divider()

    # ═══════════════════════════════
    #  DEBTS
    # ═══════════════════════════════
    col_title2, col_exp2, col_add2 = st.columns([4, 1, 1])
    with col_title2:
        st.subheader("Deudas")
    with col_exp2:
        export_csv(debts, "deudas.csv", "CSV")
    with col_add2:
        if st.button("+ Deuda", key="add_debt", use_container_width=True, type="primary"):
            st.session_state["debt_editing"] = True
            st.session_state["debt_edit_id"] = None

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
            c1, c2, c3 = st.columns(3)
            total = c1.number_input("Total (₡)", min_value=0.0, step=10000.0, value=float(existing["total"]) if existing is not None else 0.0)
            paid = c2.number_input("Pagado", min_value=0.0, step=1000.0, value=float(existing["paid"]) if existing is not None else 0.0)
            rate = c3.number_input("Tasa interes (%)", min_value=0.0, step=0.5, value=float(existing["rate"]) if existing is not None else 0.0)
            due = st.date_input("Fecha vencimiento (opcional)", value=None)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip() and total > 0:
                new_row = {
                    "id": edit_id or uid(), "name": name.strip(), "total": total,
                    "paid": paid, "rate": rate, "due": str(due) if due else "", "ts": now_ts(),
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

    if debts.empty:
        st.info("No hay deudas registradas.")
    else:
        for _, d in debts.iterrows():
            remaining = d["total"] - d["paid"]
            pct = min(d["paid"] / d["total"], 1.0) if d["total"] > 0 else 0
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{d['name']}**")
                    st.progress(pct, text=f"Pagado: {fmt(d['paid'])} / {fmt(d['total'])} ({int(pct*100)}%)")
                    details = f"Pendiente: :red[{fmt(remaining)}]"
                    if d.get("rate", 0) > 0:
                        details += f" | Tasa: {d['rate']}%"
                    if d.get("due"):
                        details += f" | Vence: {d['due']}"
                    st.markdown(details)
                with c2:
                    amount = st.number_input("Pagar", min_value=0.0, step=1000.0, key=f"debt_amt_{d['id']}", label_visibility="collapsed")
                    if st.button("Pagar", key=f"debt_pay_{d['id']}", use_container_width=True):
                        if amount > 0:
                            new_paid = min(d["paid"] + amount, d["total"])
                            debts.loc[debts["id"] == d["id"], "paid"] = new_paid
                            save_df("debts", debts)
                            # Record payment in history
                            _record_payment(d["id"], amount, d["name"])
                            st.rerun()
                    if st.button("📋 Historial", key=f"debt_hist_{d['id']}", use_container_width=True):
                        st.session_state["debt_history_id"] = d["id"]
                        st.rerun()
                    if st.button("✏️", key=f"debt_edit_{d['id']}", use_container_width=True):
                        st.session_state["debt_editing"] = True
                        st.session_state["debt_edit_id"] = d["id"]
                        st.rerun()
                    if confirm_delete(d["id"], d["name"], "debt"):
                        debts = debts[debts["id"] != d["id"]]
                        save_df("debts", debts)
                        st.rerun()

    # --- Payment history panel ---
    hist_id = st.session_state.get("debt_history_id")
    if hist_id:
        _render_payment_history(hist_id, debts)


def _record_payment(debt_id, amount, debt_name):
    """Record a payment in the debt_payments history."""
    payments = get_df("debt_payments")
    new_payment = {
        "id": uid(),
        "debt_id": debt_id,
        "monto": amount,
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "nota": f"Abono a {debt_name}",
        "ts": now_ts(),
    }
    payments = pd.concat([pd.DataFrame([new_payment]), payments], ignore_index=True)
    save_df("debt_payments", payments)


def _render_payment_history(debt_id, debts):
    """Show payment history for a specific debt."""
    debt_match = debts[debts["id"] == debt_id]
    if debt_match.empty:
        return

    debt = debt_match.iloc[0]
    payments = get_df("debt_payments")
    debt_payments = payments[payments["debt_id"] == debt_id].sort_values("ts", ascending=False) if not payments.empty else pd.DataFrame()

    st.divider()
    col_t, col_close = st.columns([5, 1])
    with col_t:
        st.subheader(f"Historial de pagos: {debt['name']}")
    with col_close:
        if st.button("Cerrar", key="close_hist"):
            st.session_state["debt_history_id"] = None
            st.rerun()

    if debt_payments.empty:
        st.info("No hay pagos registrados para esta deuda.")
    else:
        total_paid_hist = debt_payments["monto"].sum()
        st.metric("Total abonado (historial)", fmt(total_paid_hist))

        for _, p in debt_payments.iterrows():
            st.markdown(f"- **{p['fecha']}** - {fmt(p['monto'])} - {p.get('nota', '')}")
