import streamlit as st
from datetime import datetime
from core.data import get_df
from core.constants import fmt
from core.utils import parse_checks


def _build_context():
    notas = get_df("notas")
    tareas = get_df("tareas")
    proyectos = get_df("proyectos")
    txs = get_df("txs")
    savings = get_df("savings")
    debts = get_df("debts")
    habitos = get_df("habitos")
    inventario = get_df("inventario")

    ctx = ""
    if not notas.empty:
        ctx += f"NOTAS({len(notas)}):\n"
        for _, n in notas.iterrows():
            ctx += f"[{n['titulo']}|{n['area']}]:{n['body']}\n"
        ctx += "\n"

    if not tareas.empty:
        ctx += "TAREAS:\n"
        for _, t in tareas.iterrows():
            mark = "\u2713" if t["done"] else "\u25cb"
            ctx += f"[{mark}|{t['prioridad']}]{t['titulo']}({t['area']})\n"
        ctx += "\n"

    if not proyectos.empty:
        ctx += "PROYECTOS:\n"
        for _, p in proyectos.iterrows():
            ctx += f"{p['nombre']}({p['area']}):{p['desc']}\n"
        ctx += "\n"

    if not txs.empty:
        now = datetime.now()
        prefix = f"{now.year}-{now.month:02d}"
        month_txs = txs[txs["fecha"].str.startswith(prefix)]
        inc = float(month_txs[month_txs["type"] == "ingreso"]["amt"].sum()) if not month_txs.empty else 0
        exp = float(month_txs[month_txs["type"] == "gasto"]["amt"].sum()) if not month_txs.empty else 0
        ctx += f"FINANZAS MES:ingresos={fmt(inc)},gastos={fmt(exp)},balance={fmt(inc-exp)}\n"
        recent = txs.sort_values("ts", ascending=False).head(10)
        ctx += "TXS:\n"
        for _, t in recent.iterrows():
            ctx += f"{t['type']}{fmt(t['amt'])}{t['cat']}:{t['desc']}\n"
        ctx += "\n"

    if not savings.empty:
        ctx += "AHORROS:\n"
        for _, s in savings.iterrows():
            ctx += f"{s['name']}:{fmt(s['current'])}/{fmt(s['goal'])}\n"
        ctx += "\n"

    if not debts.empty:
        debt_monthly = get_df("debt_monthly")
        ctx += "DEUDAS:\n"
        for _, d in debts.iterrows():
            dm = debt_monthly[debt_monthly["debt_id"] == d["id"]] if not debt_monthly.empty else pd.DataFrame()
            if not dm.empty:
                latest = dm.sort_values("ts", ascending=False).iloc[0]
                saldo = float(latest["saldo"])
                mon = d.get("moneda", "CRC") or "CRC"
                label = f"${saldo:,.2f}" if mon == "USD" else fmt(saldo)
                ctx += f"{d['name']}: saldo {label}\n"
            else:
                ctx += f"{d['name']}: sin registros\n"
        ctx += "\n"

    if not habitos.empty:
        ctx += "HABITOS:\n"
        for _, h in habitos.iterrows():
            checks = parse_checks(h.get("checks", "{}"))
            today = datetime.now().strftime("%Y-%m-%d")
            done_today = checks.get(today, False)
            ctx += f"{h['name']}({h['freq']})streak:{h.get('streak', 0)}hoy:{'si' if done_today else 'no'}\n"
        ctx += "\n"

    if not inventario.empty:
        total_val = (inventario["val"] * inventario["qty"]).sum()
        ctx += f"INVENTARIO({len(inventario)} items, valor total={fmt(total_val)}):\n"
        for _, item in inventario.iterrows():
            ctx += f"{item['name']}({item['cat']}):{fmt(item['val'])}x{item['qty']}\n"
        ctx += "\n"

    return ctx


SUGGESTIONS = [
    "Dame un resumen general de mi segundo cerebro",
    "Que habitos he cumplido esta semana?",
    "Cuanto vale todo mi inventario del hogar?",
    "Cuales son mis deudas pendientes?",
    "Que tareas tengo de alta prioridad?",
    "Dame un resumen de mi situacion financiera",
]


def render():
    st.header("Buscar con IA")
    st.caption("Consulta todo tu conocimiento con el asistente de IA")

    # --- API Key ---
    with st.expander("Configurar API Key", expanded="ai_key" not in st.session_state or not st.session_state.get("ai_key")):
        api_key = st.text_input(
            "API Key de Anthropic",
            type="password",
            value=st.session_state.get("ai_key", ""),
            placeholder="sk-ant-...",
            help="Tu key se guarda solo en esta sesion. Obten una en console.anthropic.com",
        )
        if st.button("Guardar key"):
            if api_key.strip():
                st.session_state["ai_key"] = api_key.strip()
                st.success("API key guardada para esta sesion.")
            else:
                st.warning("Ingresa una API key.")

    st.divider()

    # --- Query ---
    question = st.text_input("Pregunta sobre tus notas, finanzas, habitos, inventario...", key="ai_question")

    col_ask, col_clear = st.columns([1, 5])
    with col_ask:
        ask = st.button("Preguntar", type="primary")

    # --- Suggestions ---
    st.caption("Ideas para preguntar:")
    suggestion_cols = st.columns(3)
    for i, s in enumerate(SUGGESTIONS):
        with suggestion_cols[i % 3]:
            if st.button(s, key=f"sugg_{i}", use_container_width=True):
                st.session_state["ai_question"] = s
                st.rerun()

    # --- Run query ---
    if ask and question.strip():
        api_key = st.session_state.get("ai_key", "")
        if not api_key:
            st.error("Configura tu API key primero.")
            return

        with st.spinner("Analizando tu cerebro..."):
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                ctx = _build_context()
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    system=f'Eres "Cerebro", asistente PKM personal. Responde en espanol, de forma concisa.\nDatos del usuario:\n\n{ctx}',
                    messages=[{"role": "user", "content": question.strip()}],
                )
                result = "".join(block.text for block in response.content if hasattr(block, "text"))
                st.divider()
                st.subheader("Respuesta")
                st.markdown(result)
            except anthropic.AuthenticationError:
                st.error("API key invalida. Verifica tu key en console.anthropic.com")
            except Exception as e:
                st.error(f"Error: {str(e)}")
