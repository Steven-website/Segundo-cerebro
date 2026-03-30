import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df
from core.constants import fmt, AREA_LABELS, CAT_ICONS
from core.utils import parse_checks, PRIORITY_EMOJIS


def render():
    st.header("Reportes y Balance")

    tab_mensual, tab_anual, tab_balance = st.tabs(["Reporte mensual", "Reporte anual", "Balance general"])

    with tab_mensual:
        _render_monthly()

    with tab_anual:
        _render_annual()

    with tab_balance:
        _render_balance()


def _get_month_finance(txs, year, month):
    prefix = f"{year}-{month:02d}"
    if txs.empty:
        return 0, 0
    month_txs = txs[txs["fecha"].str.startswith(prefix)]
    inc = float(month_txs[month_txs["type"] == "ingreso"]["amt"].sum())
    exp = float(month_txs[month_txs["type"] == "gasto"]["amt"].sum())
    return inc, exp


def _render_monthly():
    now = datetime.now()
    col_m, col_y = st.columns(2)
    month = col_m.selectbox("Mes", range(1, 13), index=now.month - 1, format_func=lambda m: [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ][m - 1], key="rep_month")
    year = col_y.number_input("Ano", min_value=2020, max_value=2030, value=now.year, key="rep_year")

    prefix = f"{year}-{month:02d}"

    # Previous month for comparison
    prev_m = month - 1
    prev_y = year
    if prev_m <= 0:
        prev_m += 12
        prev_y -= 1

    # --- Finance ---
    st.subheader("Finanzas del mes")
    txs = get_df("txs")

    ingresos, gastos = _get_month_finance(txs, year, month)
    prev_inc, prev_exp = _get_month_finance(txs, prev_y, prev_m)
    balance = ingresos - gastos

    c1, c2, c3 = st.columns(3)

    inc_delta = None
    if prev_inc > 0:
        inc_delta = f"{int((ingresos - prev_inc) / prev_inc * 100):+d}% vs anterior"
    c1.metric("Ingresos", fmt(ingresos), delta=inc_delta)

    exp_delta = None
    if prev_exp > 0:
        exp_delta = f"{int((gastos - prev_exp) / prev_exp * 100):+d}% vs anterior"
    c2.metric("Gastos", fmt(gastos), delta=exp_delta, delta_color="inverse")

    bal_color = "normal" if balance >= 0 else "inverse"
    prev_bal = prev_inc - prev_exp
    bal_delta = None
    if prev_bal != 0:
        bal_delta = f"{fmt(balance - prev_bal)} vs anterior"
    c3.metric("Balance", fmt(balance), delta=bal_delta, delta_color=bal_color)

    # By category
    if not txs.empty:
        month_txs = txs[txs["fecha"].str.startswith(prefix)]
        if not month_txs.empty:
            gastos_df = month_txs[month_txs["type"] == "gasto"]
            if not gastos_df.empty:
                cat_grouped = gastos_df.groupby("cat")["amt"].sum().reset_index()
                cat_grouped.columns = ["Categoria", "Monto"]
                cat_grouped["Categoria"] = cat_grouped["Categoria"].str.capitalize()
                st.bar_chart(cat_grouped.set_index("Categoria"), color=["#c96a6a"])

                # Category comparison vs previous month
                prev_prefix = f"{prev_y}-{prev_m:02d}"
                prev_month_txs = txs[txs["fecha"].str.startswith(prev_prefix)]
                prev_gastos_df = prev_month_txs[prev_month_txs["type"] == "gasto"] if not prev_month_txs.empty else pd.DataFrame()

                if not prev_gastos_df.empty:
                    with st.expander("Comparacion por categoria vs mes anterior"):
                        for _, row in cat_grouped.iterrows():
                            cat_name = row["Categoria"].lower()
                            current_amt = row["Monto"]
                            prev_amt = float(prev_gastos_df[prev_gastos_df["cat"] == cat_name]["amt"].sum())
                            if prev_amt > 0:
                                change = int((current_amt - prev_amt) / prev_amt * 100)
                                icon = CAT_ICONS.get(cat_name, "")
                                arrow = "🔺" if change > 0 else "🔽" if change < 0 else "➡️"
                                st.markdown(f"{icon} **{row['Categoria']}**: {fmt(current_amt)} {arrow} {change:+d}% (antes: {fmt(prev_amt)})")

    st.divider()

    # --- Tasks ---
    st.subheader("Productividad")
    tareas = get_df("tareas")
    if not tareas.empty:
        month_tasks = tareas[tareas["fecha"].str.startswith(prefix)]
        total = len(month_tasks)
        done = int(month_tasks["done"].sum()) if total > 0 else 0

        # Previous month comparison
        prev_prefix = f"{prev_y}-{prev_m:02d}"
        prev_tasks = tareas[tareas["fecha"].str.startswith(prev_prefix)]
        prev_total = len(prev_tasks)
        prev_done = int(prev_tasks["done"].sum()) if prev_total > 0 else 0

        c1, c2, c3 = st.columns(3)
        task_delta = f"{total - prev_total:+d} vs anterior" if prev_total > 0 else None
        c1.metric("Tareas del mes", total, delta=task_delta)
        done_delta = f"{done - prev_done:+d} vs anterior" if prev_done > 0 else None
        c2.metric("Completadas", done, delta=done_delta)
        rate = int(done / total * 100) if total > 0 else 0
        prev_rate = int(prev_done / prev_total * 100) if prev_total > 0 else 0
        rate_delta = f"{rate - prev_rate:+d}pp vs anterior" if prev_total > 0 else None
        c3.metric("Tasa de completitud", f"{rate}%", delta=rate_delta)

    # --- Habits ---
    habitos = get_df("habitos")
    if not habitos.empty:
        st.subheader("Habitos del mes")
        habit_stats = []
        for _, h in habitos.iterrows():
            checks = parse_checks(h.get("checks", "{}"))
            count = sum(1 for k, v in checks.items() if k.startswith(prefix) and v)
            habit_stats.append({"Habito": h["name"], "Dias cumplidos": count})
        hab_df = pd.DataFrame(habit_stats)
        if not hab_df.empty:
            st.bar_chart(hab_df.set_index("Habito"), color=["#d4a853"])

    # --- Pomodoro ---
    pomo = get_df("pomo_sessions")
    if not pomo.empty:
        month_pomo = pomo[pomo["fecha"].str.startswith(prefix)]
        if not month_pomo.empty:
            st.subheader("Pomodoro del mes")
            total_sessions = len(month_pomo)
            total_min = int(month_pomo["minutos"].sum())

            # Top tasks by time
            if "tarea" in month_pomo.columns:
                task_time = month_pomo[month_pomo["tarea"] != ""].groupby("tarea")["minutos"].sum().sort_values(ascending=False)
                c1, c2, c3 = st.columns(3)
                c1.metric("Sesiones", total_sessions)
                c2.metric("Minutos enfocados", total_min)
                c3.metric("Horas totales", f"{total_min / 60:.1f}h")

                if not task_time.empty:
                    st.caption("Tiempo por tarea:")
                    for task, mins in task_time.head(5).items():
                        st.markdown(f"- **{task}**: {int(mins)} min ({mins/60:.1f}h)")
            else:
                c1, c2 = st.columns(2)
                c1.metric("Sesiones", total_sessions)
                c2.metric("Minutos enfocados", total_min)

    # --- PDF Export ---
    _pdf_export_button(f"reporte_{prefix}")


def _render_annual():
    now = datetime.now()
    year = st.number_input("Ano", min_value=2020, max_value=2030, value=now.year, key="rep_year_a")
    prefix = str(year)

    txs = get_df("txs")
    tareas = get_df("tareas")

    st.subheader(f"Resumen financiero {year}")

    if not txs.empty:
        year_txs = txs[txs["fecha"].str.startswith(prefix)]
        months_data = []
        for m in range(1, 13):
            mp = f"{year}-{m:02d}"
            m_txs = year_txs[year_txs["fecha"].str.startswith(mp)]
            inc = float(m_txs[m_txs["type"] == "ingreso"]["amt"].sum())
            exp = float(m_txs[m_txs["type"] == "gasto"]["amt"].sum())
            month_name = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"][m - 1]
            months_data.append({"Mes": month_name, "Ingresos": inc, "Gastos": exp})

        chart_df = pd.DataFrame(months_data)
        if chart_df[["Ingresos", "Gastos"]].sum().sum() > 0:
            st.bar_chart(chart_df.set_index("Mes"), color=["#4a9e7a", "#c96a6a"])

        total_inc = float(year_txs[year_txs["type"] == "ingreso"]["amt"].sum())
        total_exp = float(year_txs[year_txs["type"] == "gasto"]["amt"].sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Total ingresos", fmt(total_inc))
        c2.metric("Total gastos", fmt(total_exp))
        c3.metric("Balance anual", fmt(total_inc - total_exp))
    else:
        st.info("No hay transacciones.")

    st.divider()

    st.subheader(f"Productividad {year}")
    if not tareas.empty:
        year_tasks = tareas[tareas["fecha"].str.startswith(prefix)]
        months_prod = []
        for m in range(1, 13):
            mp = f"{year}-{m:02d}"
            m_tasks = year_tasks[year_tasks["fecha"].str.startswith(mp)]
            total = len(m_tasks)
            done = int(m_tasks["done"].sum()) if total > 0 else 0
            month_name = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"][m - 1]
            months_prod.append({"Mes": month_name, "Completadas": done, "Pendientes": total - done})

        prod_df = pd.DataFrame(months_prod)
        st.bar_chart(prod_df.set_index("Mes"), color=["#4a9e7a", "#c96a6a"])

    _pdf_export_button(f"reporte_{year}")


def _render_balance():
    st.subheader("Balance general")

    savings = get_df("savings")
    debts = get_df("debts")
    txs = get_df("txs")
    inventario = get_df("inventario")

    # Totals
    total_savings = float(savings["current"].sum()) if not savings.empty else 0
    total_savings_goal = float(savings["goal"].sum()) if not savings.empty else 0
    total_debt = float((debts["total"] - debts["paid"]).sum()) if not debts.empty else 0
    total_debt_full = float(debts["total"].sum()) if not debts.empty else 0
    total_inventory = float((inventario["val"] * inventario["qty"]).sum()) if not inventario.empty else 0

    now = datetime.now()
    prefix = f"{now.year}-{now.month:02d}"
    if not txs.empty:
        month_txs = txs[txs["fecha"].str.startswith(prefix)]
        month_inc = float(month_txs[month_txs["type"] == "ingreso"]["amt"].sum())
        month_exp = float(month_txs[month_txs["type"] == "gasto"]["amt"].sum())
    else:
        month_inc, month_exp = 0, 0

    # Net worth
    patrimonio = total_savings + total_inventory - total_debt
    st.metric("Patrimonio neto", fmt(patrimonio), help="Ahorros + Inventario - Deudas pendientes")

    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Ahorros")
        st.metric("Ahorrado", fmt(total_savings))
        st.metric("Meta total", fmt(total_savings_goal))
        if total_savings_goal > 0:
            st.progress(min(total_savings / total_savings_goal, 1.0))

        if not savings.empty:
            for _, s in savings.iterrows():
                pct = min(s["current"] / s["goal"] * 100, 100) if s["goal"] > 0 else 0
                st.caption(f"{s['name']}: {fmt(s['current'])} / {fmt(s['goal'])} ({int(pct)}%)")

    with c2:
        st.markdown("### Deudas")
        st.metric("Deuda pendiente", fmt(total_debt))
        st.metric("Deuda total", fmt(total_debt_full))
        if total_debt_full > 0:
            paid_pct = 1 - (total_debt / total_debt_full)
            st.progress(min(paid_pct, 1.0), text=f"{int(paid_pct * 100)}% pagado")

        if not debts.empty:
            for _, d in debts.iterrows():
                remaining = d["total"] - d["paid"]
                st.caption(f"{d['name']}: pendiente {fmt(remaining)}")

    with c3:
        st.markdown("### Este mes")
        st.metric("Ingresos", fmt(month_inc))
        st.metric("Gastos", fmt(month_exp))
        balance = month_inc - month_exp
        color = "green" if balance >= 0 else "red"
        st.markdown(f"**Balance:** :{color}[{fmt(balance)}]")

    st.divider()

    # Balance chart
    st.subheader("Composicion del patrimonio")
    balance_data = pd.DataFrame([
        {"Concepto": "Ahorros", "Valor": total_savings},
        {"Concepto": "Inventario", "Valor": total_inventory},
        {"Concepto": "Deudas", "Valor": -total_debt},
    ])
    if balance_data["Valor"].abs().sum() > 0:
        st.bar_chart(balance_data.set_index("Concepto"), color=["#5a8fc9"])

    _pdf_export_button("balance_general")


def _pdf_export_button(filename):
    """Generate a simple text-based report as downloadable file."""
    st.divider()
    if st.button("Descargar reporte (TXT)", key=f"pdf_{filename}", use_container_width=True):
        report = _generate_text_report()
        st.download_button(
            "Descargar",
            report.encode("utf-8"),
            f"{filename}.txt",
            "text/plain",
            key=f"dl_{filename}",
        )


def _generate_text_report():
    """Generate a text summary of all data."""
    lines = []
    lines.append("=" * 50)
    lines.append("SEGUNDO CEREBRO - REPORTE")
    lines.append(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    lines.append("=" * 50)

    txs = get_df("txs")
    if not txs.empty:
        now = datetime.now()
        prefix = f"{now.year}-{now.month:02d}"
        month_txs = txs[txs["fecha"].str.startswith(prefix)]
        inc = float(month_txs[month_txs["type"] == "ingreso"]["amt"].sum())
        exp = float(month_txs[month_txs["type"] == "gasto"]["amt"].sum())
        lines.append(f"\nFINANZAS DEL MES:")
        lines.append(f"  Ingresos: {fmt(inc)}")
        lines.append(f"  Gastos: {fmt(exp)}")
        lines.append(f"  Balance: {fmt(inc - exp)}")

    savings = get_df("savings")
    if not savings.empty:
        lines.append(f"\nAHORROS:")
        for _, s in savings.iterrows():
            lines.append(f"  {s['name']}: {fmt(s['current'])} / {fmt(s['goal'])}")

    debts = get_df("debts")
    if not debts.empty:
        lines.append(f"\nDEUDAS:")
        for _, d in debts.iterrows():
            lines.append(f"  {d['name']}: pendiente {fmt(d['total'] - d['paid'])}")

    tareas = get_df("tareas")
    if not tareas.empty:
        pending = tareas[~tareas["done"]]
        lines.append(f"\nTAREAS PENDIENTES ({len(pending)}):")
        for _, t in pending.head(20).iterrows():
            lines.append(f"  [{t['prioridad']}] {t['titulo']}")

    return "\n".join(lines)
