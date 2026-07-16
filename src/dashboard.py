"""
WhiteLight Systematic Trading & Analysis Pipeline - Streamlit Dashboard
Provides a premium, local-first monitoring interface for equity tracking,
risk circuit breaker state, the systematic signal matrix, and journal logs.
"""

import os
import json
import glob
from datetime import datetime
import streamlit as st
import pandas as pd

# Path configurations
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")

# Import strategy & logging modules
import sys
sys.path.append(BASE_DIR)
from src.strategy import calculate_ema, calculate_vwap
from src.journal import generate_daily_journal_template, log_state_transition

# Set page configuration with a premium dark theme feel
st.set_page_config(
    page_title="WhiteLight Systematic Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS styling (Dark mode, glassmorphism, subtle gradients, animations)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
    
    /* Global styles */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Background adjustment */
    .stApp {
        background: radial-gradient(circle at top right, #0F172A, #020617) !important;
        color: #F8FAFC;
    }
    
    /* Header typography */
    h1, h2, h3, h4, h5 {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    /* Title styling */
    .title-gradient {
        background: linear-gradient(135deg, #00F2FE 0%, #4FACFE 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 800;
        margin-bottom: 5px;
    }

    /* Glassmorphism Metric Card */
    .metric-card {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 242, 254, 0.3);
        box-shadow: 0 12px 40px 0 rgba(0, 242, 254, 0.1);
    }
    .metric-title {
        color: #94A3B8;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 10px;
    }
    .metric-value {
        color: #F8FAFC;
        font-size: 2.1rem;
        font-weight: 800;
        line-height: 1.1;
    }
    .metric-sub {
        color: #38BDF8;
        font-size: 0.8rem;
        margin-top: 8px;
    }
    
    /* Status indicators */
    .status-normal {
        color: #10B981;
    }
    .status-lockdown {
        color: #EF4444;
        animation: pulse 1.5s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.4; }
        100% { opacity: 1; }
    }

    /* Gradient divider */
    .gradient-divider {
        height: 1px;
        background: linear-gradient(90deg, rgba(79, 172, 254, 0) 0%, rgba(79, 172, 254, 0.4) 50%, rgba(79, 172, 254, 0) 100%);
        margin: 25px 0;
    }

    /* Sidebar enhancement */
    section[data-testid="stSidebar"] {
        background-color: #0B0F19 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }

    /* Journal text container */
    .journal-box {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 20px;
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #E2E8F0;
        max-height: 500px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)


# Initialize folders and files if missing
def init_local_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump({
                "lockdown_active": False,
                "drawdown_locked_at": None,
                "equity_history": [
                    {"timestamp": "2026-07-09T12:00:00Z", "equity": 10000.0},
                    {"timestamp": "2026-07-15T12:00:00Z", "equity": 9850.0}
                ]
            }, f, indent=2)

    if not os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE, "w") as f:
            json.dump({
                "active_positions": [
                    {
                        "symbol": "AAPL 260814C00170000",
                        "quantity": 2,
                        "option_type": "call",
                        "strike_price": 170.0,
                        "expiration_date": "2026-08-14",
                        "acquired_at": "2026-07-15T10:15:00Z"
                    }
                ]
            }, f, indent=2)


init_local_data()

# Load state and position databases
with open(STATE_FILE, "r") as f:
    system_state = json.load(f)

with open(POSITIONS_FILE, "r") as f:
    positions_data = json.load(f)


# --- Sidebar - Control Panel & Settings ---
st.sidebar.markdown("### ⚡ System Controls")
is_locked = system_state.get("lockdown_active", False)

# Lockdown trigger and reset buttons
if is_locked:
    st.sidebar.error("Execution locked due to safety drawdown.")
    if st.sidebar.button("🟢 Manual Reset / Unlock System", use_container_width=True):
        system_state["lockdown_active"] = False
        system_state["drawdown_locked_at"] = None
        # Add a baseline equity to reset drawdown calculations
        history = system_state.get("equity_history", [])
        if history:
            current_eq = history[-1]["equity"]
            # Clear old history to reset rolling peak calculations
            system_state["equity_history"] = [{"timestamp": datetime.utcnow().isoformat() + "Z", "equity": 10000.0}]
            
        with open(STATE_FILE, "w") as f:
            json.dump(system_state, f, indent=2)
        log_state_transition("LOCKDOWN", "NORMAL", "Manual operator reset override")
        st.success("System status restored to normal operation.")
        st.rerun()
else:
    st.sidebar.success("System status: Operational")
    if st.sidebar.button("🔴 Emergency Manual Lockdown", use_container_width=True):
        system_state["lockdown_active"] = True
        system_state["drawdown_locked_at"] = datetime.utcnow().isoformat() + "Z"
        
        # Flatten mock actions
        positions_data["active_positions"] = []
        with open(POSITIONS_FILE, "w") as f:
            json.dump(positions_data, f, indent=2)
            
        with open(STATE_FILE, "w") as f:
            json.dump(system_state, f, indent=2)
            
        log_state_transition("NORMAL", "LOCKDOWN", "Manual operator emergency lockdown")
        st.sidebar.warning("All positions flattened. Orders purged.")
        st.rerun()

# --- 🧪 Interactive Playgrounds ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🧪 Risk Breaker Simulation")

# Extract current metrics for default
history = system_state.get("equity_history", [])
current_val = history[-1]["equity"] if history else 10000.0

simulated_equity = st.sidebar.slider(
    "Set Account Equity ($)",
    min_value=5000.0,
    max_value=12000.0,
    value=float(current_val),
    step=100.0
)

# Trigger update if slider moves
if not history or history[-1]["equity"] != simulated_equity:
    now_str = datetime.utcnow().isoformat() + "Z"
    history.append({"timestamp": now_str, "equity": simulated_equity})
    
    # Filter 7D window
    from datetime import timedelta
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    filtered_history = []
    for entry in history:
        try:
            t_str = entry["timestamp"].replace("Z", "")
            t_dt = datetime.fromisoformat(t_str)
            if t_dt >= seven_days_ago:
                filtered_history.append(entry)
        except Exception:
            filtered_history.append(entry)
            
    system_state["equity_history"] = filtered_history
    
    # Calculate Peak and Drawdown
    peak_eq = max(e["equity"] for e in filtered_history) if filtered_history else simulated_equity
    dd = (peak_eq - simulated_equity) / peak_eq if peak_eq > 0 else 0.0
    
    if dd >= 0.15 and not system_state.get("lockdown_active", False):
        system_state["lockdown_active"] = True
        system_state["drawdown_locked_at"] = now_str
        log_state_transition("NORMAL", "LOCKDOWN", f"Simulated drawdown of {dd*100:.2f}% triggered circuit breaker")
        
        # Flatten positions
        positions_data["active_positions"] = []
        with open(POSITIONS_FILE, "w") as f:
            json.dump(positions_data, f, indent=2)
            
    with open(STATE_FILE, "w") as f:
        json.dump(system_state, f, indent=2)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Pipeline Settings")
st.sidebar.info("• Core DTE Target: **30 Days**\n• Core Delta Target: **0.40**\n• Breaker Margin: **15.00%**\n• Platform: **Robinhood MCP**")



# --- 1. Header Block ---
col_head, col_badge = st.columns([4, 1])
with col_head:
    st.markdown('<div class="title-gradient">WhiteLight Control Room</div>', unsafe_allow_html=True)
    st.markdown("Systematic multi-leg options routing pipeline, risk circuits, & local logging.")
with col_badge:
    status_label = "🔴 LOCKDOWN" if is_locked else "🟢 OPERATIONAL"
    st.markdown(f"""
    <div style="text-align: right; margin-top: 10px;">
        <span style="
            background: { 'rgba(239, 68, 68, 0.15)' if is_locked else 'rgba(16, 185, 129, 0.15)' };
            color: { '#EF4444' if is_locked else '#10B981' };
            border: 1px solid { 'rgba(239, 68, 68, 0.3)' if is_locked else 'rgba(16, 185, 129, 0.3)' };
            padding: 8px 16px;
            border-radius: 30px;
            font-weight: 700;
            font-size: 0.9rem;
            letter-spacing: 1px;
        ">{status_label}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)


# --- 2. Account Equity & Safety Metrics Cards ---
history = system_state.get("equity_history", [])
if history:
    current_equity = history[-1]["equity"]
    peak_equity = max(e["equity"] for e in history)
    drawdown = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
else:
    current_equity = 10000.0
    peak_equity = 10000.0
    drawdown = 0.0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Portfolio Equity</div>
        <div class="metric-value">${current_equity:,.2f}</div>
        <div class="metric-sub">Live Robinhood Balance</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Rolling Peak (7D)</div>
        <div class="metric-value">${peak_equity:,.2f}</div>
        <div class="metric-sub">High Water Mark</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    color_class = "status-normal" if drawdown < 0.15 else "status-lockdown"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Rolling Drawdown</div>
        <div class="metric-value {color_class}">{drawdown * 100:.2f}%</div>
        <div class="metric-sub">Breaker Limit: 15.00%</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    status_text = "LOCKED" if is_locked else "NORMAL"
    status_class = "status-lockdown" if is_locked else "status-normal"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Risk Engine State</div>
        <div class="metric-value {status_class}">{status_text}</div>
        <div class="metric-sub">Auto drawdown monitoring</div>
    </div>
    """, unsafe_allow_html=True)


st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)


# --- 3. Body: Signal Matrix & Positions ---
st.markdown("### 📊 Systematic Signal Matrix")

tickers = ["AAPL", "MSFT", "TSLA", "NVDA"]

# Custom SaaS row elements for Signal Matrix (No clunky standard tables)
for idx, ticker in enumerate(tickers):
    base_price = 150.0 + (idx * 50)
    prices = [base_price * (1.0 + (0.0004 * i)) for i in range(300)]
    
    ema_50 = calculate_ema(prices, 50)[-1]
    ema_250 = calculate_ema(prices, 250)[-1]
    
    bars = []
    for i in range(30):
        p = prices[-30 + i]
        bars.append({
            "high": p + 0.4,
            "low": p - 0.4,
            "close": p,
            "volume": 2000,
            "timestamp": f"2026-07-15T09:30:{i:02d}Z"
        })
    vwap = calculate_vwap(bars)[-1]
    current_price = prices[-1]
    
    # Calculate signal crossovers
    if ema_50 > ema_250 and current_price > vwap:
        signal_text = "BULLISH BUY"
        signal_badge = """
        <span style="
            background: rgba(16, 185, 129, 0.12);
            color: #10B981;
            border: 1px solid rgba(16, 185, 129, 0.25);
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
        ">🐂 BULLISH BUY</span>
        """
    elif ema_50 < ema_250 and current_price < vwap:
        signal_text = "BEARISH PUT"
        signal_badge = """
        <span style="
            background: rgba(239, 68, 68, 0.12);
            color: #EF4444;
            border: 1px solid rgba(239, 68, 68, 0.25);
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
        ">🐻 BEARISH PUT</span>
        """
    else:
        signal_badge = """
        <span style="
            background: rgba(148, 163, 184, 0.1);
            color: #94A3B8;
            border: 1px solid rgba(148, 163, 184, 0.2);
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.75rem;
        ">⚪ NEUTRAL</span>
        """
        
    row_html = f"""
    <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(30, 41, 59, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
    ">
        <div>
            <div style="font-weight: 700; font-size: 1.15rem; color: #F8FAFC;">{ticker}</div>
            <div style="font-size: 0.75rem; color: #64748B;">System Equities Feed</div>
        </div>
        <div>
            <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Last Price</div>
            <div style="font-weight: 600; color: #E2E8F0; font-size: 0.95rem;">${current_price:.2f}</div>
        </div>
        <div>
            <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">EMA 50 / 250</div>
            <div style="font-weight: 500; color: #94A3B8; font-size: 0.9rem;">${ema_50:.2f} / ${ema_250:.2f}</div>
        </div>
        <div>
            <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Session VWAP</div>
            <div style="font-weight: 500; color: #94A3B8; font-size: 0.9rem;">${vwap:.2f}</div>
        </div>
        <div style="text-align: right; min-width: 130px;">
            {signal_badge}
        </div>
    </div>
    """
    st.markdown(row_html, unsafe_allow_html=True)

st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

st.markdown("### 💼 Active Systematic Positions")
active_list = positions_data.get("active_positions", [])
if not active_list:
    st.markdown("""
    <div style="
        padding: 24px;
        background: rgba(30, 41, 59, 0.1);
        border: 1px dashed rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        color: #94A3B8;
        text-align: center;
    ">
        No active positions currently held.
    </div>
    """, unsafe_allow_html=True)
else:
    for pos in active_list:
        symbol = pos["symbol"]
        qty = pos["quantity"]
        opt_type = pos.get("option_type", "call")
        strike = pos.get("strike_price", 0.0)
        exp = pos.get("expiration_date", "")
        acq = pos.get("acquired_at", "")
        
        type_color = "#10B981" if opt_type.lower() == "call" else "#EF4444"
        
        pos_html = f"""
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(30, 41, 59, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 12px;
        ">
            <div>
                <div style="font-weight: 700; color: #F8FAFC; font-size: 1.05rem;">{symbol}</div>
                <div style="font-size: 0.7rem; color: #64748B;">Acquired UTC: {acq}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; margin-bottom: 4px;">Leg Type</div>
                <div style="font-weight: 700; color: {type_color}; font-size: 0.9rem;">{opt_type.upper()}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; margin-bottom: 4px;">Strike</div>
                <div style="font-weight: 600; color: #cbd5e1; font-size: 0.9rem;">${strike:.2f}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; margin-bottom: 4px;">Size</div>
                <div style="font-weight: 600; color: #cbd5e1; font-size: 0.9rem;">{qty}</div>
            </div>
            <div>
                <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; margin-bottom: 4px;">Expiry</div>
                <div style="font-weight: 600; color: #cbd5e1; font-size: 0.9rem;">{exp}</div>
            </div>
        </div>
        """
        st.markdown(pos_html, unsafe_allow_html=True)

