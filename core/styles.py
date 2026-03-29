import streamlit as st

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500&display=swap');

/* Hide default streamlit elements */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* Custom fonts */
.stApp {
    font-family: 'JetBrains Mono', monospace;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #111113;
    border-right: 1px solid #2c2c32;
}
[data-testid="stSidebar"] .stRadio > label {
    font-size: 12px;
}

/* Card styling */
.card-container {
    background: #111113;
    border: 1px solid #2c2c32;
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}

/* Metric cards */
.metric-card {
    background: #111113;
    border: 1px solid #2c2c32;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.metric-value {
    font-size: 28px;
    font-weight: 600;
    color: #d4a853;
}
.metric-label {
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #50505e;
    margin-top: 4px;
}

/* Priority dots */
.priority-alta { color: #c96a6a; }
.priority-media { color: #c9943a; }
.priority-baja { color: #4a9e7a; }

/* Progress bar custom */
.progress-container {
    background: #18181b;
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
    margin: 6px 0;
}
.progress-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
}

/* Note cards */
.note-card {
    background: #111113;
    border: 1px solid #2c2c32;
    border-radius: 10px;
    padding: 14px;
    border-left: 3px solid;
    min-height: 100px;
}

/* Task items */
.task-item {
    background: #111113;
    border: 1px solid #2c2c32;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* Habit mini calendar */
.habit-day {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    margin: 1px;
}
.habit-done { background: rgba(74, 158, 122, 0.3); border: 1px solid #4a9e7a; }
.habit-miss { background: #18181b; border: 1px solid #2c2c32; }
.habit-today { border: 1px solid #d4a853 !important; }

/* Budget progress */
.budget-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 11px;
}

/* Inventory cards */
.inv-card {
    background: #111113;
    border: 1px solid #2c2c32;
    border-radius: 10px;
    padding: 14px;
}

/* TX items */
.tx-ingreso { color: #4a9e7a; }
.tx-gasto { color: #c96a6a; }

/* Scrollable containers */
.scroll-container {
    max-height: 400px;
    overflow-y: auto;
}

/* Buttons */
.gold-btn {
    background: rgba(212, 168, 83, 0.15);
    border: 1px solid rgba(212, 168, 83, 0.35);
    color: #d4a853;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12px;
    cursor: pointer;
}

/* Small text */
.text-muted { color: #50505e; font-size: 11px; }
.text-gold { color: #d4a853; }
.text-emerald { color: #4a9e7a; }
.text-rose { color: #c96a6a; }

/* Divider */
.subtle-divider {
    border: none;
    border-top: 1px solid #2c2c32;
    margin: 12px 0;
}

/* Badge */
.area-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    letter-spacing: 0.06em;
}
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
