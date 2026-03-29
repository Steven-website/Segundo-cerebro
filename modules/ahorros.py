import streamlit as st
import pandas as pd
from core.data import get_df, save_df, uid, now_ts
from core.constants import fmt


def render():
    st.header("Ahorros & Deudas")

    savings = get_df("savings")
    debts = get_df("debts")

    # ═══════════════════════════════
    #  SAVINGS
    # ═══════════════════════════════
    col_title, col_add = st.columns([5, 1])
    with col_title:
        st.subheader("Metas de ahorro")
    with col_add:
        if st.button("+ Meta", key="add_sav", use_container_width=True, type="primary"):
            st.session_state["sav_adding"] = True

    if st.session_state.get("sav_adding"):
        with st.form("sav_form", clear_on_submit=True):
            name = st.text_input("Nombre de la meta")
            c1, c2 = st.columns(2)
            goal = c1.number_input("Meta (\u20a1)", min_value=0.0, step=10000.0)
            current = c2.number_input("Ahorrado hasta ahora", min_value=0.0, step=1000.0, value=0.0)
            date = st.date_input("Fecha objetivo (opcional)", value=None)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip() and goal > 0:
                new_row = {
                    "id": uid(), "name": name.strip(), "goal": goal,
                    "current": current, "date": str(date) if date else "", "ts": now_ts(),
                }
                save_df("savings", pd.concat([pd.DataFrame([new_row]), savings], ignore_index=True))
                st.session_state["sav_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["sav_adding"] = False
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
                    if s.get("date"):
                        st.caption(f"\U0001f4c5 Meta: {s['date']}")
                with c2:
                    amount = st.number_input("Abonar", min_value=0.0, step=1000.0, key=f"sav_amt_{s['id']}", label_visibility="collapsed")
                    if st.button("\U0001f4b0 Abonar", key=f"sav_add_{s['id']}", use_container_width=True):
                        if amount > 0:
                            savings.loc[savings["id"] == s["id"], "current"] += amount
                            save_df("savings", savings)
                            st.rerun()
                    if st.button("\U0001f5d1", key=f"sav_del_{s['id']}", use_container_width=True):
                        savings = savings[savings["id"] != s["id"]]
                        save_df("savings", savings)
                        st.rerun()

    st.divider()

    # ═══════════════════════════════
    #  DEBTS
    # ═══════════════════════════════
    col_title2, col_add2 = st.columns([5, 1])
    with col_title2:
        st.subheader("Deudas")
    with col_add2:
        if st.button("+ Deuda", key="add_debt", use_container_width=True, type="primary"):
            st.session_state["debt_adding"] = True

    if st.session_state.get("debt_adding"):
        with st.form("debt_form", clear_on_submit=True):
            name = st.text_input("Nombre de la deuda")
            c1, c2, c3 = st.columns(3)
            total = c1.number_input("Total (\u20a1)", min_value=0.0, step=10000.0)
            paid = c2.number_input("Pagado", min_value=0.0, step=1000.0, value=0.0)
            rate = c3.number_input("Tasa de interes (%)", min_value=0.0, step=0.5, value=0.0)
            due = st.date_input("Fecha vencimiento (opcional)", value=None)

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and name.strip() and total > 0:
                new_row = {
                    "id": uid(), "name": name.strip(), "total": total,
                    "paid": paid, "rate": rate, "due": str(due) if due else "", "ts": now_ts(),
                }
                save_df("debts", pd.concat([pd.DataFrame([new_row]), debts], ignore_index=True))
                st.session_state["debt_adding"] = False
                st.rerun()
            if cancelled:
                st.session_state["debt_adding"] = False
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
                        details += f" \u2022 Tasa: {d['rate']}%"
                    if d.get("due"):
                        details += f" \u2022 Vence: {d['due']}"
                    st.markdown(details)
                with c2:
                    amount = st.number_input("Pagar", min_value=0.0, step=1000.0, key=f"debt_amt_{d['id']}", label_visibility="collapsed")
                    if st.button("\U0001f4b3 Pagar", key=f"debt_pay_{d['id']}", use_container_width=True):
                        if amount > 0:
                            new_paid = min(d["paid"] + amount, d["total"])
                            debts.loc[debts["id"] == d["id"], "paid"] = new_paid
                            save_df("debts", debts)
                            st.rerun()
                    if st.button("\U0001f5d1", key=f"debt_del_{d['id']}", use_container_width=True):
                        debts = debts[debts["id"] != d["id"]]
                        save_df("debts", debts)
                        st.rerun()
