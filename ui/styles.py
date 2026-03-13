import streamlit as st

def apply_styles():
    """
    Diseño Institucional Bloomberg-Style.
    Dark theme profesional con tipografía premium.
    """
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

        /* ===== GLOBAL ===== */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #0b0e14 !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* Hide defaults */
        #MainMenu, footer, header, [data-testid="stToolbar"] { visibility: hidden !important; }
        .block-container { padding-top: 1rem !important; max-width: 100% !important; }

        /* ===== TEXT ===== */
        h1, h2, h3, h4, h5, h6, p, span, label, div {
            color: #e6edf3 !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* ===== CONTAINERS / CARDS ===== */
        [data-testid="stExpander"] {
            background: #151b23 !important;
            border: 1px solid #21262d !important;
            border-radius: 10px !important;
        }

        /* ===== BUTTONS — Cyan Neon ===== */
        .stButton > button {
            background: linear-gradient(135deg, #00b4d8 0%, #0077b6 100%) !important;
            color: #fff !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            font-size: 12px !important;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            box-shadow: 0 2px 10px rgba(0, 180, 216, 0.25) !important;
            transition: all 0.25s ease !important;
        }
        .stButton > button:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 16px rgba(0, 180, 216, 0.4) !important;
        }

        /* ===== TABS ===== */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            background: transparent !important;
            border-bottom: 1px solid #21262d;
        }
        .stTabs [data-baseweb="tab"] {
            color: #8b949e !important;
            font-weight: 600 !important;
            font-size: 12px !important;
            padding: 8px 16px !important;
        }
        .stTabs [aria-selected="true"] {
            color: #00d1ff !important;
            border-bottom: 2px solid #00d1ff !important;
        }

        /* ===== INPUTS ===== */
        .stTextInput > div > div > input,
        .stSelectbox > div > div,
        .stTextArea > div > div > textarea,
        .stNumberInput > div > div > input {
            background: #0d1117 !important;
            border: 1px solid #21262d !important;
            border-radius: 6px !important;
            color: #e6edf3 !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 12px !important;
        }

        /* ===== METRICS (for ticker cards) ===== */
        [data-testid="stMetricValue"] {
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 18px !important;
            font-weight: 700 !important;
        }
        [data-testid="stMetricDelta"] {
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 11px !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 11px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
        }

        /* ===== SIGNAL PILLS ===== */
        .pill {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .pill-buy { background: rgba(0,255,136,0.12); color: #00ff88; border: 1px solid rgba(0,255,136,0.25); }
        .pill-sell { background: rgba(255,75,75,0.12); color: #ff4b4b; border: 1px solid rgba(255,75,75,0.25); }
        .pill-neutral { background: rgba(139,148,158,0.1); color: #8b949e; border: 1px solid #21262d; }

        /* ===== DATA TABLES ===== */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        table thead th {
            background: #151b23 !important;
            color: #8b949e !important;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 10px;
            padding: 10px 14px;
            border-bottom: 1px solid #21262d;
        }
        table tbody td {
            padding: 8px 14px;
            border-bottom: 1px solid rgba(33,38,45,0.5);
            color: #e6edf3 !important;
        }
        table tbody tr:hover { background: rgba(0,209,255,0.03) !important; }

        /* ===== DIVIDER ===== */
        hr { border-color: #21262d !important; opacity: 0.6 !important; }

        /* ===== SCROLLBAR ===== */
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #0b0e14; }
        ::-webkit-scrollbar-thumb { background: #21262d; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)
