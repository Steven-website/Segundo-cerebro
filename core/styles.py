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

/* Tag badges */
.tag-urgente { background: rgba(201,106,106,0.2); color: #c96a6a; padding: 2px 8px; border-radius: 10px; font-size: 10px; }
.tag-bug { background: rgba(201,148,58,0.2); color: #c9943a; padding: 2px 8px; border-radius: 10px; font-size: 10px; }
.tag-idea { background: rgba(138,106,201,0.2); color: #8a6ac9; padding: 2px 8px; border-radius: 10px; font-size: 10px; }
.tag-reunion { background: rgba(90,143,201,0.2); color: #5a8fc9; padding: 2px 8px; border-radius: 10px; font-size: 10px; }
.tag-personal { background: rgba(74,158,122,0.2); color: #4a9e7a; padding: 2px 8px; border-radius: 10px; font-size: 10px; }

/* ===== RESPONSIVE / MOBILE ===== */

/* Tablet: allow 2-col layouts */
@media (max-width: 992px) and (min-width: 769px) {
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"] > div {
        min-width: 45% !important;
        flex: 1 1 45% !important;
    }
}

/* Mobile: stack columns, bigger touch targets */
@media (max-width: 768px) {
    /* Stack all columns vertically */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 4px !important;
    }
    [data-testid="stHorizontalBlock"] > div {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }

    /* Metric blocks: keep 2 per row */
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
        flex-wrap: wrap !important;
        gap: 8px !important;
    }
    [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div {
        min-width: 45% !important;
        flex: 1 1 45% !important;
    }

    /* Touch-friendly buttons */
    button {
        min-height: 44px !important;
        font-size: 14px !important;
    }

    /* Checkboxes - bigger touch area */
    .stCheckbox label {
        min-height: 44px;
        display: flex;
        align-items: center;
    }

    /* Selectbox / nav */
    [data-testid="stSelectbox"] {
        font-size: 14px !important;
    }

    /* Tabs - scrollable on mobile */
    [data-testid="stTabs"] [role="tablist"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
    }
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar {
        display: none;
    }
    [data-testid="stTabs"] button[role="tab"] {
        white-space: nowrap !important;
        flex-shrink: 0 !important;
        font-size: 13px !important;
        padding: 8px 12px !important;
    }

    /* Expanders - bigger touch */
    [data-testid="stExpander"] summary {
        min-height: 44px;
        display: flex;
        align-items: center;
    }

    /* Forms - more padding */
    [data-testid="stForm"] {
        padding: 12px !important;
    }

    /* Charts - full width */
    [data-testid="stVegaLiteChart"],
    [data-testid="stArrowVegaLiteChart"] {
        width: 100% !important;
    }

    /* Reduce padding on main content for more space */
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 1rem !important;
    }

    /* Compact header on mobile */
    h1 { font-size: 1.4rem !important; }
    h2 { font-size: 1.2rem !important; }
    h3 { font-size: 1rem !important; }

    /* Habit day cells - slightly smaller on mobile */
    .habit-day {
        width: 20px;
        height: 20px;
        font-size: 8px;
    }

    /* Text inputs bigger touch area */
    input[type="text"], input[type="password"], input[type="email"], input[type="number"] {
        min-height: 44px !important;
        font-size: 16px !important; /* prevents iOS zoom */
    }

    /* Textareas */
    textarea {
        font-size: 16px !important; /* prevents iOS zoom */
    }

    /* Code blocks - wrap on mobile */
    code {
        word-break: break-all !important;
        white-space: pre-wrap !important;
    }
}
</style>
"""


def inject_css():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
