import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from core.data import get_df, save_df, uid, now_ts

DEPORTES = [
    "🏃 Correr", "🚴 Ciclismo", "🏋️ Gym", "🧘 Yoga", "🏊 Natacion",
    "⚽ Futbol", "🏀 Basketball", "🎾 Tenis", "🥊 Boxeo", "🚶 Caminata",
    "🧗 Escalada", "💪 Calistenia", "🏐 Voleibol", "🤸 Crossfit", "🏌️ Golf",
    "🏓 Ping pong", "🎯 Otro",
]


def render():
    st.header("Ejercicio")

    log = get_df("exercise_log")
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    month_prefix = today.strftime("%Y-%m")

    # --- Quick log ---
    with st.form("quick_exercise", clear_on_submit=True):
        c1, c2 = st.columns(2)
        deporte = c1.selectbox("Deporte", DEPORTES)
        fecha = c2.date_input("Fecha", value=today.date())
        c3, c4 = st.columns(2)
        duracion = c3.number_input("Minutos", min_value=1, value=30)
        notas = c4.text_input("Notas", placeholder="Opcional")
        submitted = st.form_submit_button("+ Registrar", type="primary", use_container_width=True)

        if submitted:
            new = {
                "id": uid(), "fecha": fecha.strftime("%Y-%m-%d"),
                "deporte": deporte, "duracion": duracion,
                "notas": notas.strip(), "ts": now_ts(),
            }
            log = pd.concat([pd.DataFrame([new]), log], ignore_index=True)
            save_df("exercise_log", log)
            st.rerun()

    st.divider()

    # --- Metrics ---
    today_log = log[log["fecha"] == today_str] if not log.empty else pd.DataFrame()
    month_log = log[log["fecha"].str.startswith(month_prefix)] if not log.empty else pd.DataFrame()

    # Streak calculation
    streak = 0
    if not log.empty:
        check_date = today
        # If no session today, start counting from yesterday
        if log[log["fecha"] == today_str].empty:
            check_date -= timedelta(days=1)
        while True:
            ds = check_date.strftime("%Y-%m-%d")
            if not log[log["fecha"] == ds].empty:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hoy", f"{len(today_log)} sesiones")
    c2.metric("Min hoy", f"{int(today_log['duracion'].sum())}" if not today_log.empty else "0")
    c3.metric("Este mes", f"{len(month_log)} sesiones")
    c4.metric("Racha", f"🔥 {streak} dias")

    st.divider()

    # --- Calendar heatmap (last 30 days) ---
    st.subheader("Ultimos 30 dias")
    days_data = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        day_log = log[log["fecha"] == ds] if not log.empty else pd.DataFrame()
        count = len(day_log)
        mins = int(day_log["duracion"].sum()) if not day_log.empty else 0
        days_data.append({"Fecha": ds, "Sesiones": count, "Minutos": mins})

    chart_df = pd.DataFrame(days_data)
    if chart_df["Sesiones"].sum() > 0:
        st.bar_chart(chart_df.set_index("Fecha")["Sesiones"], color="#4a9e7a")

    st.divider()

    # --- Monthly breakdown by sport ---
    st.subheader("Desglose del mes")

    if not month_log.empty:
        sport_stats = month_log.groupby("deporte").agg(
            Sesiones=("id", "count"),
            Minutos=("duracion", "sum"),
        ).reset_index()
        sport_stats.columns = ["Deporte", "Sesiones", "Minutos"]
        sport_stats = sport_stats.sort_values("Sesiones", ascending=False)

        for _, row in sport_stats.iterrows():
            hours = row["Minutos"] / 60
            st.markdown(f"{row['Deporte']}: **{int(row['Sesiones'])}** sesiones — {int(row['Minutos'])} min ({hours:.1f}h)")

        st.divider()
        st.bar_chart(sport_stats.set_index("Deporte")["Minutos"], color="#d4a853")
    else:
        st.info("No hay sesiones registradas este mes.")

    st.divider()

    # --- Monthly trend (last 6 months) ---
    st.subheader("Tendencia mensual")
    if not log.empty:
        months_data = []
        for i in range(5, -1, -1):
            m_date = today - timedelta(days=i * 30)
            mp = m_date.strftime("%Y-%m")
            m_log = log[log["fecha"].str.startswith(mp)]
            m_name = m_date.strftime("%b %Y")
            sesiones = len(m_log)
            minutos = int(m_log["duracion"].sum()) if not m_log.empty else 0
            deportes = m_log["deporte"].nunique() if not m_log.empty else 0
            months_data.append({"Mes": m_name, "Sesiones": sesiones, "Minutos": minutos, "Deportes": deportes})

        months_df = pd.DataFrame(months_data)
        if months_df["Sesiones"].sum() > 0:
            st.bar_chart(months_df.set_index("Mes")[["Sesiones", "Minutos"]], color=["#5a8fc9", "#d4a853"])

            for _, m in months_df.iterrows():
                if m["Sesiones"] > 0:
                    st.caption(f"**{m['Mes']}**: {int(m['Sesiones'])} sesiones, {int(m['Minutos'])} min, {int(m['Deportes'])} deportes distintos")

    st.divider()

    # --- Recent sessions ---
    st.subheader("Sesiones recientes")
    if log.empty:
        st.info("No hay sesiones registradas.")
        return

    recent = log.sort_values("fecha", ascending=False).head(15)
    for _, r in recent.iterrows():
        col_info, col_del = st.columns([6, 1])
        with col_info:
            notas_txt = f" — {r['notas']}" if r.get("notas") else ""
            st.markdown(f"📅 **{r['fecha']}** | {r['deporte']} | {int(r['duracion'])} min{notas_txt}")
        with col_del:
            if st.button("🗑️", key=f"exdel_{r['id']}", use_container_width=True):
                log = log[log["id"] != r["id"]]
                save_df("exercise_log", log)
                st.rerun()
