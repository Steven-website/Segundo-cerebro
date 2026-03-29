import json
import streamlit as st
from datetime import datetime
from core.constants import AREAS


def parse_checks(data):
    if isinstance(data, dict):
        return data
    if isinstance(data, str) and data:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def is_done_today(habit):
    today_str = datetime.now().strftime("%Y-%m-%d")
    checks = parse_checks(habit.get("checks", "{}"))
    return checks.get(today_str, False)


def get_area_id(label):
    area = next((a for a in AREAS if f'{a["emoji"]} {a["name"]}' == label), None)
    return area["id"] if area else None


PRIORITY_EMOJIS = {
    "alta": "\U0001f534",
    "media": "\U0001f7e1",
    "baja": "\U0001f7e2",
}


def confirm_delete(item_id, item_name, key_prefix):
    confirm_key = f"{key_prefix}_confirm_{item_id}"
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False

    if not st.session_state[confirm_key]:
        if st.button("\U0001f5d1", key=f"{key_prefix}_del_{item_id}"):
            st.session_state[confirm_key] = True
            st.rerun()
        return False
    else:
        st.warning(f"Eliminar **{item_name}**?")
        c1, c2 = st.columns(2)
        if c1.button("\u2705 Si, eliminar", key=f"{key_prefix}_yes_{item_id}", type="primary"):
            st.session_state[confirm_key] = False
            return True
        if c2.button("\u274c Cancelar", key=f"{key_prefix}_no_{item_id}"):
            st.session_state[confirm_key] = False
            st.rerun()
        return False


def export_csv(df, filename, label="Exportar CSV"):
    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(label, csv, filename, "text/csv", use_container_width=True)
