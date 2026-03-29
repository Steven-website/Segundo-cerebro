import streamlit as st
import pandas as pd
from datetime import datetime
from core.data import get_df, save_df, uid, now_ts
from core.constants import CAT_ICONS, TX_CATS_GASTO, TX_CATS_INGRESO, BUDGET_DEFAULT, fmt
from core.utils import confirm_delete, export_csv


def _get_month_txs(txs, year=None, month=None):
    if txs.empty:
        return txs
    now = datetime.now()
    y = year or now.year
    m = month or now.month
    prefix = f"{y}-{m:02d}"
    return txs[txs["fecha"].str.startswith(prefix)]


def render():
    st.header("Finanzas")

    txs = get_df("txs")
    budget_df = get_df("budget")

    if budget_df.empty:
        budget = BUDGET_DEFAULT.copy()
    else:
        budget = dict(zip(budget_df["cat"], budget_df["amt"]))
        for k, v in BUDGET_DEFAULT.items():
            budget.setdefault(k, v)

    month_txs = _get_month_txs(txs)
    ingresos = float(month_txs[month_txs["type"] == "ingreso"]["amt"].sum()) if not month_txs.empty else 0
    gastos = float(month_txs[month_txs["type"] == "gasto"]["amt"].sum()) if not month_txs.empty else 0
    balance = ingresos - gastos

    # --- Summary metrics ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", fmt(ingresos))
    c2.metric("Gastos", fmt(gastos))
    c3.metric("Balance", fmt(balance), delta="Positivo" if balance >= 0 else "Negativo", delta_color="normal" if balance >= 0 else "inverse")

    st.divider()

    # --- Charts ---
    if not txs.empty:
        st.subheader("Tendencias")
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            # Monthly income vs expenses (last 6 months)
            now = datetime.now()
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
    with col_gas:
        if st.button("+ Gasto", use_container_width=True, type="primary"):
            st.session_state["tx_adding"] = "gasto"
    with col_exp:
        export_csv(txs, "transacciones.csv", "\U0001f4e5 CSV")

    if st.session_state.get("tx_adding"):
        tx_type = st.session_state["tx_adding"]
        cats = TX_CATS_INGRESO if tx_type == "ingreso" else TX_CATS_GASTO

        with st.form("tx_form", clear_on_submit=True):
            st.subheader(f"Nuevo {'ingreso' if tx_type == 'ingreso' else 'gasto'}")
            desc = st.text_input("Descripcion")
            c1, c2 = st.columns(2)
            amt = c1.number_input("Monto", min_value=0.0, step=1000.0)
            cat = c2.selectbox("Categoria", cats, format_func=lambda x: f"{CAT_ICONS.get(x, '')} {x.capitalize()}")
            fecha = st.date_input("Fecha")

            col_s, col_c = st.columns(2)
            submitted = col_s.form_submit_button("Guardar", type="primary")
            cancelled = col_c.form_submit_button("Cancelar")

            if submitted and desc.strip() and amt > 0:
                new_row = {
                    "id": uid(), "type": tx_type, "desc": desc.strip(),
                    "amt": amt, "cat": cat, "fecha": str(fecha), "ts": now_ts(),
                }
                new_df = pd.concat([pd.DataFrame([new_row]), txs], ignore_index=True)
                save_df("txs", new_df)
                st.session_state["tx_adding"] = None
                st.rerun()
            if cancelled:
                st.session_state["tx_adding"] = None
                st.rerun()

    st.divider()

    # --- Budget progress + Transactions ---
    col_budget, col_txs = st.columns(2)

    with col_budget:
        st.subheader("Presupuesto mensual")
        for cat, limit in budget.items():
            if cat == "ingreso":
                continue
            icon = CAT_ICONS.get(cat, "\U0001f4e6")
            spent = float(month_txs[(month_txs["type"] == "gasto") & (month_txs["cat"] == cat)]["amt"].sum()) if not month_txs.empty else 0
            pct = min(spent / limit, 1.0) if limit > 0 else 0

            st.markdown(f"{icon} **{cat.capitalize()}** \u2022 {fmt(spent)} / {fmt(limit)}")
            st.progress(pct)

        with st.expander("Editar presupuesto"):
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

    with col_txs:
        st.subheader("Transacciones recientes")
        if txs.empty:
            st.info("Sin transacciones.")
        else:
            recent = txs.sort_values("ts", ascending=False).head(12)
            for _, tx in recent.iterrows():
                icon = CAT_ICONS.get(tx["cat"], "\U0001f4e6")
                sign = "+" if tx["type"] == "ingreso" else "-"
                color = "green" if tx["type"] == "ingreso" else "red"
                st.markdown(f"{icon} {tx['desc']} \u2022 :{color}[{sign}{fmt(tx['amt'])}] \u2022 `{tx['fecha']}`")

                if confirm_delete(tx["id"], tx["desc"], "tx"):
                    txs = txs[txs["id"] != tx["id"]]
                    save_df("txs", txs)
                    st.rerun()
