import streamlit as st

def apply_styles():
    """
    Trading Pro System v4.2 — Premium Institutional Terminal.
    Glassmorphism + micro-animations + dark mode + accessible design.
    """
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

        /* ===== ROOT DESIGN TOKENS ===== */
        :root {
            --bg-deepest: #04070e;
            --bg-primary: #060a13;
            --bg-secondary: #0c1121;
            --bg-card: rgba(17, 24, 39, 0.65);
            --bg-card-solid: #111827;
            --bg-card-hover: #161f33;
            --bg-glass: rgba(15, 23, 42, 0.55);
            --bg-input: #0f172a;
            --border-subtle: rgba(30, 41, 59, 0.6);
            --border-active: #334155;
            --border-glow-blue: rgba(59, 130, 246, 0.35);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --text-dim: #475569;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --accent-green: #10b981;
            --accent-emerald: #34d399;
            --accent-red: #ef4444;
            --accent-rose: #f43f5e;
            --accent-amber: #f59e0b;
            --accent-purple: #8b5cf6;
            --accent-indigo: #6366f1;
            --gradient-bull: linear-gradient(135deg, #059669, #10b981);
            --gradient-bear: linear-gradient(135deg, #dc2626, #ef4444);
            --gradient-primary: linear-gradient(135deg, #1e40af, #3b82f6);
            --gradient-premium: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-xl: 20px;
            --shadow-card: 0 4px 16px rgba(0,0,0,0.25), 0 1px 3px rgba(0,0,0,0.15);
            --shadow-glow-blue: 0 0 20px rgba(59, 130, 246, 0.08);
            --shadow-glow-green: 0 0 20px rgba(16, 185, 129, 0.08);
            --shadow-elevated: 0 8px 32px rgba(0,0,0,0.35);
            --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-smooth: 300ms cubic-bezier(0.4, 0, 0.2, 1);
            --transition-spring: 400ms cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        /* ===== GLOBAL RESET & BACKGROUND MESH ===== */
        [data-testid="stAppViewContainer"], .main {
            background: 
                radial-gradient(circle at 10% 20%, rgba(30, 58, 138, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(88, 28, 135, 0.15) 0%, transparent 45%),
                linear-gradient(175deg, var(--bg-deepest) 0%, #050811 100%) !important;
            background-attachment: fixed !important;
        }
        footer, #MainMenu { visibility: hidden !important; height: 0 !important; }
        [data-testid="stHeader"] { background: transparent !important; }
        
        /* Tipografía (Excluyendo iconos de Material para evitar bugs visuales) */
        p, h1, h2, h3, h4, h5, h6, span, div, label, li { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; 
        }
        .material-symbols-rounded, .material-icons, i, [class^="stIcon"] {
            font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
        }
        code, .stCode, pre { font-family: 'JetBrains Mono', monospace !important; }

        /* ===== SCROLLBAR ===== */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-deepest); }
        ::-webkit-scrollbar-thumb { background: var(--border-subtle); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--border-active); }

        /* ===== SIDEBAR — CONTROL CENTER ===== */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #080d1a 0%, #060a15 100%) !important;
            border-right: 1px solid var(--border-subtle) !important;
            width: 22rem !important;
        }
        [data-testid="stSidebarContent"] { padding: 1.5rem 1.2rem !important; }
        [data-testid="stSidebar"] .stMarkdown h1 {
            font-size: 1.2rem !important;
            background: linear-gradient(135deg, #60a5fa, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800 !important;
        }

        /* ===== METRIC CARDS ===== */
        [data-testid="stMetric"] {
            background: var(--bg-card) !important;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-subtle) !important;
            border-radius: var(--radius-md) !important;
            padding: 1rem 1.2rem !important;
            box-shadow: var(--shadow-card);
            transition: all var(--transition-smooth);
        }
        [data-testid="stMetric"]:hover {
            border-color: rgba(59, 130, 246, 0.3) !important;
            box-shadow: var(--shadow-glow-blue);
            transform: translateY(-2px);
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.68rem !important;
            color: var(--text-muted) !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600 !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
            font-weight: 700 !important;
            color: var(--text-primary) !important;
        }

        /* ===== HEADER BAR ===== */
        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.2rem 1.5rem;
            background: var(--bg-glass);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            margin-bottom: 1.5rem;
            box-shadow: var(--shadow-card);
        }
        .header-title {
            font-size: 1.5rem;
            font-weight: 900;
            color: #fff;
            letter-spacing: -0.03em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .header-subtitle {
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 2px;
        }
        .header-badge {
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05));
            border: 1px solid rgba(16, 185, 129, 0.25);
            color: var(--accent-emerald);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace !important;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .header-version {
            font-size: 0.6rem;
            color: var(--text-dim);
            font-weight: 400;
            background: rgba(255,255,255,0.04);
            padding: 2px 8px;
            border-radius: 4px;
            margin-left: 8px;
        }

        /* ===== SECTION TITLES (Separación Visual) ===== */
        .section-title {
            font-family: 'Inter', sans-serif !important;
            font-size: 0.72rem;
            font-weight: 700;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 1.8px;
            margin: 2.8rem 0 1.2rem 0; /* Mayor separación vertical entre bloques */
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .section-title::after {
            content: "";
            flex: 1;
            height: 1px;
            background: linear-gradient(90deg, var(--border-subtle), transparent 80%);
        }

        /* ===== GLASS CARD COMPONENT ===== */
        .glass-card {
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 1.6rem 1.6rem; /* Más espacio interior para respirar */
            box-shadow: var(--shadow-card);
            transition: all var(--transition-smooth);
        }
        .glass-card:hover {
            border-color: rgba(99, 102, 241, 0.2);
        }
        .glass-card-title {
            font-size: 0.68rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 0.8rem;
        }

        /* ===== SCORE GAUGE ===== */
        .score-gauge {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 0;
        }
        .score-value {
            font-size: 2.2rem;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace !important;
            line-height: 1;
        }
        .score-value.bull { color: var(--accent-green); }
        .score-value.bear { color: var(--accent-red); }
        .score-value.neutral { color: var(--text-secondary); }
        .score-bar {
            flex: 1;
            height: 8px;
            background: rgba(255,255,255,0.06);
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }
        .score-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.6s ease-out;
        }
        .score-bar-fill.bull { background: var(--gradient-bull); }
        .score-bar-fill.bear { background: var(--gradient-bear); }
        .score-bar-fill.neutral { background: linear-gradient(135deg, #475569, #64748b); }
        .score-label {
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        /* ===== SIGNAL BADGE ===== */
        .signal-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .signal-badge.long {
            background: rgba(16, 185, 129, 0.12);
            color: var(--accent-emerald);
            border: 1px solid rgba(16, 185, 129, 0.25);
        }
        .signal-badge.short {
            background: rgba(239, 68, 68, 0.12);
            color: #fca5a5;
            border: 1px solid rgba(239, 68, 68, 0.25);
        }
        .signal-badge.wait {
            background: rgba(148, 163, 184, 0.08);
            color: var(--text-secondary);
            border: 1px solid var(--border-subtle);
        }

        /* ===== ML INDICATOR ===== */
        .ml-indicator {
            padding: 10px 14px;
            border-radius: var(--radius-sm);
            background: rgba(139, 92, 246, 0.06);
            border: 1px solid rgba(139, 92, 246, 0.15);
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 8px;
        }
        .ml-indicator .ml-icon {
            font-size: 1.3rem;
        }
        .ml-indicator .ml-label {
            font-size: 0.62rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .ml-indicator .ml-value {
            font-size: 1.1rem;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace !important;
        }
        .ml-value.high { color: var(--accent-green); }
        .ml-value.low { color: var(--accent-red); }
        .ml-value.mid { color: var(--accent-purple); }

        /* ===== DIGITAL REASONING CONSOLE ===== */
        .reasoning-console {
            background: linear-gradient(180deg, #060a14, #080d18);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 14px 18px;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 0.68rem;
            color: var(--text-secondary);
            max-height: 200px;
            overflow-y: auto;
            margin-bottom: 1rem;
            line-height: 1.7;
            box-shadow: inset 0 2px 10px rgba(0,0,0,0.4);
        }
        .reasoning-line {
            margin-bottom: 5px;
            border-left: 2px solid transparent;
            padding-left: 10px;
            transition: all var(--transition-fast);
        }
        .reasoning-line:hover { background: rgba(255,255,255,0.02); }
        .reasoning-line-bull { border-left-color: var(--accent-green); color: var(--text-primary); }
        .reasoning-line-bear { border-left-color: var(--accent-red); color: var(--text-primary); }
        .reasoning-line-ml { border-left-color: var(--accent-purple); color: #c4b5fd; }
        .reasoning-line-info { border-left-color: var(--accent-cyan); color: #67e8f9; }
        .reasoning-timestamp {
            color: var(--text-dim);
            font-size: 0.58rem;
            margin-right: 10px;
            opacity: 0.7;
        }

        /* ===== TICKER HEATMAP BUTTONS ===== */
        .stButton > button {
            transition: all var(--transition-smooth) !important;
            border-radius: var(--radius-sm) !important;
        }
        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
        }
        .stButton > button:active {
            transform: translateY(0) !important;
        }

        /* ===== STATUS BAR ===== */
        .status-bar {
            display: flex;
            align-items: center;
            gap: 1.5rem;
            flex-wrap: wrap;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 0.62rem;
            color: var(--text-muted);
        }
        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .status-dot-green { background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); }
        .status-dot-amber { background: var(--accent-amber); box-shadow: 0 0 6px rgba(245, 158, 11, 0.4); }
        .status-dot-red { background: var(--accent-red); box-shadow: 0 0 6px rgba(239, 68, 68, 0.4); }

        /* Pulsación */
        .pulse-active { animation: pulse-glow 2s infinite; }
        @keyframes pulse-glow {
            0% { opacity: 1; box-shadow: 0 0 6px currentColor; }
            50% { opacity: 0.5; box-shadow: 0 0 12px currentColor; }
            100% { opacity: 1; box-shadow: 0 0 6px currentColor; }
        }

        /* ===== TOOLTIP / HELP TEXT ===== */
        .help-text {
            font-size: 0.6rem;
            color: var(--text-dim);
            background: rgba(255,255,255,0.03);
            border-radius: 4px;
            padding: 4px 8px;
            margin-top: 4px;
            line-height: 1.4;
        }

        /* ===== SCENARIO CARD ===== */
        .scenario-card {
            padding: 12px 16px;
            border-radius: var(--radius-sm);
            background: rgba(99, 102, 241, 0.06);
            border: 1px solid rgba(99, 102, 241, 0.15);
            margin-top: 8px;
        }
        .scenario-label {
            font-size: 0.62rem;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }
        .scenario-text {
            font-size: 0.85rem;
            color: var(--text-primary);
            font-weight: 600;
        }

        /* ===== TABS ===== */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 4px !important;
            background: rgba(255,255,255,0.02);
            border-radius: var(--radius-sm);
            padding: 3px;
            border-bottom: none !important;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            color: var(--text-muted) !important;
            border-radius: 6px !important;
            padding: 8px 16px !important;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            color: var(--text-primary) !important;
            background: rgba(59, 130, 246, 0.1) !important;
            border-bottom: none !important;
        }

        /* ===== DATAFRAME STYLING ===== */
        [data-testid="stDataFrame"] {
            border-radius: var(--radius-md) !important;
            overflow: hidden;
        }

        /* ===== EXPANDER ===== */
        [data-testid="stExpander"] {
            background: var(--bg-card) !important;
            border: 1px solid var(--border-subtle) !important;
            border-radius: var(--radius-md) !important;
        }
        [data-testid="stExpanderToggleIcon"] { color: var(--text-muted) !important; }

        /* ===== PROGRESS BAR ===== */
        [data-testid="stProgress"] > div > div {
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan)) !important;
        }

        /* ===== TABLES (Hover & Style) ===== */
        [data-testid="stDataFrame"] {
            border: 1px solid var(--border-subtle) !important;
            border-radius: var(--radius-md) !important;
            overflow: hidden;
            background: var(--bg-card) !important;
            box-shadow: var(--shadow-card);
        }
        [data-testid="stDataFrame"] table {
            background: transparent !important;
        }
        [data-testid="stDataFrame"] th {
            background: rgba(15, 23, 42, 0.8) !important;
            color: var(--text-muted) !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            font-size: 0.7rem !important;
            letter-spacing: 1.5px;
            border-bottom: 1px solid var(--border-subtle) !important;
        }
        [data-testid="stDataFrame"] td {
            color: var(--text-primary) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 0.85rem !important;
            border-bottom: 1px solid rgba(255,255,255,0.03) !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }
        /* Fila hover interactiva */
        [data-testid="stDataFrame"] tr:hover td {
            background-color: var(--bg-card-hover) !important;
            color: var(--accent-cyan) !important;
            cursor: pointer;
        }

        /* ===== DIVIDER ===== */
        hr {
            border: none !important;
            border-top: 1px solid var(--border-subtle) !important;
            margin: 1.5rem 0 !important;
        }

        /* ===== RESPONSIVE MICRO-ADJUSTMENTS ===== */
        @media (max-width: 768px) {
            .header-bar { flex-direction: column; gap: 10px; text-align: center; }
            .header-title { font-size: 1.2rem; }
        }

        /* ===== PHASE BADGES (F1, F2, F3) ===== */
        .reasoning-line-bull b,
        .reasoning-line-bear b,
        .reasoning-line-ml b,
        .reasoning-line-info b { font-weight: 700; }

        /* Kill Switch alert pulse */
        @keyframes ks-alert {
            0%   { background: rgba(239,68,68,0.08); }
            50%  { background: rgba(239,68,68,0.20); }
            100% { background: rgba(239,68,68,0.08); }
        }
        [data-testid="stMetricValue"]:has-text("🚨") {
            animation: ks-alert 1.5s infinite;
        }

        /* ===== VOLUME IMBALANCE LEGEND ===== */
        .vol-legend {
            display: flex;
            gap: 14px;
            font-size: 0.58rem;
            color: var(--text-dim);
            margin-top: 4px;
            padding: 4px 8px;
            background: rgba(255,255,255,0.02);
            border-radius: 4px;
        }
        .vol-legend span { display: flex; align-items: center; gap: 4px; }
        .vol-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

