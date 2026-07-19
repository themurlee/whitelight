"""
WhiteLight Systematic Trading & Analysis Pipeline - Journal & Psychology Page
Provides a premium visual interface for daily performance tracking, discipline meters,
psychology check-ins (pre/post session), weekly reviews, a 10K blueprint tracker,
and a monthly trade logger.
"""

import os
import json
import glob
from datetime import datetime
import streamlit as st
import pandas as pd
import altair as alt

# Path configurations
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
POSITIONS_FILE = os.path.join(DATA_DIR, "positions.json")
TRADE_LOG_FILE = os.path.join(DATA_DIR, "trade_history.json")
PSYCHOLOGY_FILE = os.path.join(DATA_DIR, "psychology_log.json")
JOURNAL_DIR = os.path.join(DATA_DIR, "journal")

# Set page configuration with a premium dark theme feel
st.set_page_config(
    page_title="Journal & Psychology Portal",
    page_icon="📓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS styling (matches dashboard.py for unified aesthetics)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');
    
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
        background: linear-gradient(135deg, #FF007F 0%, #7F00FF 100%);
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
        padding: 22px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 0, 127, 0.3);
        box-shadow: 0 12px 40px 0 rgba(255, 0, 127, 0.1);
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
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
    }
    .metric-sub {
        color: #38BDF8;
        font-size: 0.8rem;
        margin-top: 8px;
    }

    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #FF007F, #7F00FF) !important;
    }

    /* Gradient divider */
    .gradient-divider {
        height: 1px;
        background: linear-gradient(90deg, rgba(255, 0, 127, 0) 0%, rgba(255, 0, 127, 0.4) 50%, rgba(255, 0, 127, 0) 100%);
        margin: 25px 0;
    }
    
    /* Discipline score styles */
    .discipline-high {
        color: #10B981;
        font-weight: 800;
    }
    .discipline-mid {
        color: #F59E0B;
        font-weight: 800;
    }
    .discipline-low {
        color: #EF4444;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)


# Ensure local database structures
def init_journal_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    
    # Initialize trade history file if missing
    if not os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE, "w") as f:
            json.dump([
                {
                    "timestamp": "2026-04-01T14:30:00Z",
                    "action": "SELL",
                    "symbol": "AAPL",
                    "quantity": 2,
                    "price": 4.50,
                    "details": {
                        "strategy": "EMA Crossover",
                        "pnl": 450.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 2.25,
                        "notes": "Clean bounce off 50 EMA on 5m chart. Took profits at +2.25R target."
                    }
                },
                {
                    "timestamp": "2026-04-02T09:15:00Z",
                    "action": "SELL",
                    "symbol": "TSLA",
                    "quantity": 1,
                    "price": 8.00,
                    "details": {
                        "strategy": "VWAP Rebound",
                        "pnl": -150.0,
                        "session": "London",
                        "direction": "Put",
                        "r_multiple": -1.0,
                        "notes": "VWAP did not hold resistance, squeeze stopped me out."
                    }
                },
                {
                    "timestamp": "2026-04-03T15:00:00Z",
                    "action": "SELL",
                    "symbol": "NVDA",
                    "quantity": 2,
                    "price": 3.20,
                    "details": {
                        "strategy": "Break & Retest",
                        "pnl": 320.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 1.6,
                        "notes": "Breakout above yesterday's high. Re-entry on pullback test."
                    }
                },
                {
                    "timestamp": "2026-04-04T02:45:00Z",
                    "action": "SELL",
                    "symbol": "AAPL",
                    "quantity": 1,
                    "price": 5.50,
                    "details": {
                        "strategy": "Liquidity Sweep",
                        "pnl": -110.0,
                        "session": "Asia",
                        "direction": "Put",
                        "r_multiple": -1.0,
                        "notes": "Chased put after drop, reversed on low liquidity."
                    }
                },
                {
                    "timestamp": "2026-04-05T16:00:00Z",
                    "action": "SELL",
                    "symbol": "TSLA",
                    "quantity": 2,
                    "price": 6.00,
                    "details": {
                        "strategy": "EMA Crossover",
                        "pnl": 600.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 3.0,
                        "notes": "Strong trend continuation above 250 EMA. Locked 3R."
                    }
                },
                {
                    "timestamp": "2026-04-06T10:30:00Z",
                    "action": "SELL",
                    "symbol": "MSFT",
                    "quantity": 1,
                    "price": 4.00,
                    "details": {
                        "strategy": "Break & Retest",
                        "pnl": 280.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 1.4,
                        "notes": "Retested 50 EMA on 5m chart. Clean move to target."
                    }
                },
                {
                    "timestamp": "2026-04-07T08:30:00Z",
                    "action": "SELL",
                    "symbol": "NVDA",
                    "quantity": 2,
                    "price": 2.00,
                    "details": {
                        "strategy": "VWAP Rebound",
                        "pnl": -80.0,
                        "session": "London",
                        "direction": "Put",
                        "r_multiple": -1.0,
                        "notes": "Stopped out early on squeeze above VWAP line."
                    }
                },
                {
                    "timestamp": "2026-04-08T15:30:00Z",
                    "action": "SELL",
                    "symbol": "AAPL",
                    "quantity": 2,
                    "price": 5.00,
                    "details": {
                        "strategy": "Liquidity Sweep",
                        "pnl": 420.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 2.1,
                        "notes": "Swept session low and reversed. Locked 2.1R."
                    }
                },
                {
                    "timestamp": "2026-04-09T03:00:00Z",
                    "action": "SELL",
                    "symbol": "TSLA",
                    "quantity": 1,
                    "price": 7.00,
                    "details": {
                        "strategy": "Break & Retest",
                        "pnl": 190.0,
                        "session": "Asia",
                        "direction": "Put",
                        "r_multiple": 1.9,
                        "notes": "Bearish continuation under VWAP. Closed at support."
                    }
                },
                {
                    "timestamp": "2026-04-10T09:45:00Z",
                    "action": "SELL",
                    "symbol": "MSFT",
                    "quantity": 1,
                    "price": 6.00,
                    "details": {
                        "strategy": "EMA Crossover",
                        "pnl": -120.0,
                        "session": "London",
                        "direction": "Put",
                        "r_multiple": -1.0,
                        "notes": "Fakeout crossover, reversed aggressively. Stopped out."
                    }
                },
                {
                    "timestamp": "2026-04-11T14:15:00Z",
                    "action": "SELL",
                    "symbol": "NVDA",
                    "quantity": 2,
                    "price": 4.00,
                    "details": {
                        "strategy": "EMA Crossover",
                        "pnl": 500.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 2.5,
                        "notes": "Perfect alignment with market trend above 50 EMA."
                    }
                },
                {
                    "timestamp": "2026-04-12T15:20:00Z",
                    "action": "SELL",
                    "symbol": "AAPL",
                    "quantity": 2,
                    "price": 3.00,
                    "details": {
                        "strategy": "VWAP Rebound",
                        "pnl": 150.0,
                        "session": "New York",
                        "direction": "Put",
                        "r_multiple": 1.5,
                        "notes": "Rejected VWAP resistance. Scalped to daily low."
                    }
                },
                {
                    "timestamp": "2026-04-13T10:00:00Z",
                    "action": "SELL",
                    "symbol": "TSLA",
                    "quantity": 1,
                    "price": 9.00,
                    "details": {
                        "strategy": "Liquidity Sweep",
                        "pnl": -200.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": -1.0,
                        "notes": "Premature entry on fake low sweep. Stopped out."
                    }
                },
                {
                    "timestamp": "2026-04-14T14:45:00Z",
                    "action": "SELL",
                    "symbol": "MSFT",
                    "quantity": 2,
                    "price": 3.50,
                    "details": {
                        "strategy": "VWAP Rebound",
                        "pnl": 310.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 1.55,
                        "notes": "VWAP support bounce. Clean target achievement."
                    }
                },
                {
                    "timestamp": "2026-04-14T03:15:00Z",
                    "action": "SELL",
                    "symbol": "NVDA",
                    "quantity": 1,
                    "price": 5.00,
                    "details": {
                        "strategy": "Liquidity Sweep",
                        "pnl": 240.0,
                        "session": "Asia",
                        "direction": "Put",
                        "r_multiple": 2.4,
                        "notes": "Swept daily high and reversed. Closed at VWAP."
                    }
                },
                {
                    "timestamp": "2026-04-15T09:00:00Z",
                    "action": "SELL",
                    "symbol": "AAPL",
                    "quantity": 2,
                    "price": 2.50,
                    "details": {
                        "strategy": "Break & Retest",
                        "pnl": 180.0,
                        "session": "London",
                        "direction": "Call",
                        "r_multiple": 1.8,
                        "notes": "Breakout above resistance. Clean retest entry."
                    }
                },
                {
                    "timestamp": "2026-04-15T15:10:00Z",
                    "action": "SELL",
                    "symbol": "TSLA",
                    "quantity": 2,
                    "price": 4.00,
                    "details": {
                        "strategy": "EMA Crossover",
                        "pnl": -150.0,
                        "session": "New York",
                        "direction": "Put",
                        "r_multiple": -1.0,
                        "notes": "Crossover failed on low volume. Chop stopped me out."
                    }
                },
                {
                    "timestamp": "2026-04-15T08:45:00Z",
                    "action": "SELL",
                    "symbol": "MSFT",
                    "quantity": 1,
                    "price": 5.00,
                    "details": {
                        "strategy": "Liquidity Sweep",
                        "pnl": 290.0,
                        "session": "London",
                        "direction": "Put",
                        "r_multiple": 2.9,
                        "notes": "Swept London session high. Quick drop to support."
                    }
                },
                {
                    "timestamp": "2026-04-16T14:20:00Z",
                    "action": "SELL",
                    "symbol": "NVDA",
                    "quantity": 2,
                    "price": 4.00,
                    "details": {
                        "strategy": "VWAP Rebound",
                        "pnl": 350.0,
                        "session": "New York",
                        "direction": "Call",
                        "r_multiple": 1.75,
                        "notes": "Bounced off VWAP line. Clean breakout extension."
                    }
                },
                {
                    "timestamp": "2026-04-16T15:55:00Z",
                    "action": "SELL",
                    "symbol": "AAPL",
                    "quantity": 2,
                    "price": 2.50,
                    "details": {
                        "strategy": "Break & Retest",
                        "pnl": -100.0,
                        "session": "New York",
                        "direction": "Put",
                        "r_multiple": -1.0,
                        "notes": "Stopped out on consolidation break."
                    }
                }
            ], f, indent=2)

    # Initialize psychology logs if missing
    if not os.path.exists(PSYCHOLOGY_FILE):
        with open(PSYCHOLOGY_FILE, "w") as f:
            json.dump([
                {
                    "date": "2026-07-14",
                    "pre_mood": "Calm",
                    "pre_sleep": 8,
                    "pre_focus": 7,
                    "pre_rules_ready": True,
                    "post_revenge": False,
                    "post_fomo": False,
                    "post_focus": 8,
                    "post_notes": "Followed all entry rules perfectly, locked profit on first target."
                }
            ], f, indent=2)

    # Make sure state.json has history entries for the blueprint
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump({
                "lockdown_active": False,
                "drawdown_locked_at": None,
                "equity_history": [
                    {"timestamp": "2026-07-01T09:30:00Z", "equity": 9500.0},
                    {"timestamp": "2026-07-05T09:30:00Z", "equity": 9840.0},
                    {"timestamp": "2026-07-12T09:30:00Z", "equity": 9750.0},
                    {"timestamp": "2026-07-15T09:30:00Z", "equity": 10000.0}
                ]
            }, f, indent=2)


init_journal_data()

# Load Databases
with open(STATE_FILE, "r") as f:
    system_state = json.load(f)

with open(TRADE_LOG_FILE, "r") as f:
    trade_history = json.load(f)

with open(PSYCHOLOGY_FILE, "r") as f:
    psychology_history = json.load(f)


# --- 1. Header & Navigation ---
st.markdown('<div class="title-gradient">Journal & Psychology Desk</div>', unsafe_allow_html=True)
st.markdown("Systematic Trading Performance Logger, Mental Check-in, & Equity Growth Target Desk")

st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)


# --- 2. Calculate Metrics (Daily P&L, Win Rate, Discipline Score) ---
closed_trades = [t for t in trade_history if t.get("action") == "SELL"]
win_count = sum(1 for t in closed_trades if t.get("details", {}).get("pnl", 0.0) > 0)
total_pnl = sum(t.get("details", {}).get("pnl", 0.0) for t in closed_trades)
win_rate = (win_count / len(closed_trades) * 100.0) if closed_trades else 0.0

latest_psych = psychology_history[-1] if psychology_history else {}
rules_followed = latest_psych.get("pre_rules_ready", False)
no_revenge = not latest_psych.get("post_revenge", False)
no_fomo = not latest_psych.get("post_fomo", False)

discipline_metrics = [rules_followed, no_revenge, no_fomo]
discipline_score = (sum(1 for m in discipline_metrics if m) / 3.0) * 100.0


# --- 3. Top Row Metrics Display ---
col_p1, col_p2, col_p3, col_p4 = st.columns(4)

with col_p1:
    pnl_color = "#10B981" if total_pnl >= 0 else "#EF4444"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Cumulative P&L</div>
        <div class="metric-value" style="color: {pnl_color};">${total_pnl:+,.2f}</div>
        <div class="metric-sub">Across closed transactions</div>
    </div>
    """, unsafe_allow_html=True)

with col_p2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Systematic Win Rate</div>
        <div class="metric-value">{win_rate:.1f}%</div>
        <div class="metric-sub">Total Closed: {len(closed_trades)}</div>
    </div>
    """, unsafe_allow_html=True)

with col_p3:
    score_class = "discipline-high" if discipline_score == 100 else ("discipline-mid" if discipline_score > 50 else "discipline-low")
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Discipline Meter</div>
        <div class="metric-value {score_class}">{discipline_score:.0f}%</div>
        <div class="metric-sub">Followed Rules: {sum(1 for m in discipline_metrics if m)} / 3</div>
    </div>
    """, unsafe_allow_html=True)

with col_p4:
    history_eq = system_state.get("equity_history", [])
    current_equity = history_eq[-1]["equity"] if history_eq else 10000.0
    blueprint_percentage = min((current_equity / 10000.0) * 100.0, 100.0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">10K Target Blueprint</div>
        <div class="metric-value">{blueprint_percentage:.1f}%</div>
        <div class="metric-sub">Current Balance: ${current_equity:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)


st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)


# --- 4. Sub-sections ---
tab_psych, tab_blueprint, tab_log, tab_review = st.tabs([
    "🧠 Psychology Check-in", 
    "📈 10K Target Blueprint", 
    "📝 Monthly Trade Logger",
    "🗓️ Weekly Review Desk"
])

# Tab 1: Psychology Check-in
with tab_psych:
    col_pre, col_post = st.columns(2)
    
    with col_pre:
        st.markdown("### 🌅 Pre-Session Alignment")
        with st.form("pre_session_form"):
            pre_mood = st.selectbox("Mental State / Mood", ["Calm", "Focussed", "Anxious", "Excited", "Fatigued"])
            pre_sleep = st.slider("Sleep Quality (1 - 10)", 1, 10, 8)
            pre_focus = st.slider("Starting Focus Level (1 - 10)", 1, 10, 7)
            pre_rules_ready = st.checkbox("I commit to following entry rules, position sizes, and stop-losses.", value=True)
            
            submit_pre = st.form_submit_button("Record Pre-Session State", use_container_width=True)
            
            if submit_pre:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                
                existing_entry = next((item for item in psychology_history if item["date"] == today), None)
                if existing_entry:
                    existing_entry["pre_mood"] = pre_mood
                    existing_entry["pre_sleep"] = pre_sleep
                    existing_entry["pre_focus"] = pre_focus
                    existing_entry["pre_rules_ready"] = pre_rules_ready
                else:
                    psychology_history.append({
                        "date": today,
                        "pre_mood": pre_mood,
                        "pre_sleep": pre_sleep,
                        "pre_focus": pre_focus,
                        "pre_rules_ready": pre_rules_ready,
                        "post_revenge": False,
                        "post_fomo": False,
                        "post_focus": 5,
                        "post_notes": ""
                    })
                
                with open(PSYCHOLOGY_FILE, "w") as f:
                    json.dump(psychology_history, f, indent=2)
                st.success("Pre-session metrics successfully logged!")
                st.rerun()

    with col_post:
        st.markdown("### 🌆 Post-Session Assessment")
        with st.form("post_session_form"):
            post_revenge = st.checkbox("Revenge Trading: Did you break sizes or re-enter trades on anger?", value=False)
            post_fomo = st.checkbox("FOMO Entry: Did you chase options/stocks outside system crossovers?", value=False)
            post_focus = st.slider("Felt Focus During Session (1 - 10)", 1, 10, 8)
            post_notes = st.text_area("Narrative Lesson / Session Takeaways", placeholder="E.g. Spreads decayed quickly. Stopped out on TSLA put due to sudden VWAP bounce. Followed rules.")
            
            submit_post = st.form_submit_button("Record Post-Session Assessment", use_container_width=True)
            
            if submit_post:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                
                existing_entry = next((item for item in psychology_history if item["date"] == today), None)
                if not existing_entry:
                    existing_entry = {
                        "date": today,
                        "pre_mood": "Calm",
                        "pre_sleep": 8,
                        "pre_focus": 7,
                        "pre_rules_ready": True
                    }
                    psychology_history.append(existing_entry)
                    
                existing_entry["post_revenge"] = post_revenge
                existing_entry["post_fomo"] = post_fomo
                existing_entry["post_focus"] = post_focus
                existing_entry["post_notes"] = post_notes
                
                with open(PSYCHOLOGY_FILE, "w") as f:
                    json.dump(psychology_history, f, indent=2)
                st.success("Post-session metrics successfully logged!")
                st.rerun()

    st.markdown("---")
    st.markdown("#### 📜 Psychology History Log")
    df_psych = pd.DataFrame(psychology_history)
    st.dataframe(df_psych, use_container_width=True)


# Tab 2: 10K Blueprint & Growth Tracker
with tab_blueprint:
    st.markdown("### 🏆 $10,000 Target Growth Progress")
    
    st.write(f"Account Balance: **${current_equity:,.2f} / $10,000.00**")
    st.progress(blueprint_percentage / 100.0)
    
    col_bl1, col_bl2 = st.columns([2, 1])
    
    with col_bl1:
        st.markdown("#### 📈 Account Equity Curve (7-day)")
        df_eq = pd.DataFrame(history_eq)
        if not df_eq.empty:
            df_eq["timestamp"] = pd.to_datetime(df_eq["timestamp"])
            chart = alt.Chart(df_eq).mark_line(
                color='#FF007F', 
                size=3, 
                interpolate='monotone'
            ).encode(
                x=alt.X('timestamp:T', title='Time / Expiry'),
                y=alt.Y('equity:Q', title='Portfolio Valuation ($)', scale=alt.Scale(domain=[5000, 12000])),
                tooltip=['timestamp:T', 'equity:Q']
            ).properties(
                height=350,
                background='transparent'
            ).configure_axis(
                gridColor='rgba(255,255,255,0.05)',
                labelColor='#94A3B8',
                titleColor='#94A3B8'
            ).configure_view(
                strokeOpacity=0
            )
            st.altair_chart(chart, use_container_width=True)
            
    with col_bl2:
        st.markdown("#### 🏥 Account Health Auditing")
        
        # Calculate stats
        history_history = system_state.get("equity_history", [])
        if history_history:
            peak_val = max(e["equity"] for e in history_history)
            curr_val = history_history[-1]["equity"]
            cur_drawdown = (peak_val - curr_val) / peak_val if peak_val > 0 else 0.0
        else:
            cur_drawdown = 0.0
        
        status_health = "Excellent" if cur_drawdown < 0.05 else ("Warning" if cur_drawdown < 0.12 else "Danger")
        health_color = "status-normal" if status_health == "Excellent" else ("discipline-mid" if status_health == "Warning" else "status-lockdown")
        
        st.markdown(f"""
        <div style="background: rgba(30, 41, 59, 0.2); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px;">
            <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 8px;">Health Rating</div>
            <div class="{health_color}" style="font-size: 1.6rem; font-weight:800; margin-bottom: 15px;">{status_health}</div>
            
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.9rem;">
                <span style="color: #94A3B8;">Max Allowable Drawdown:</span>
                <span style="color: #F8FAFC; font-weight: 600;">15.00%</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.9rem;">
                <span style="color: #94A3B8;">Current Drawdown:</span>
                <span style="color: #F8FAFC; font-weight: 600;">{cur_drawdown*100:.2f}%</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.9rem;">
                <span style="color: #94A3B8;">Distance to Liquidate:</span>
                <span style="color: #EF4444; font-weight: 600;">{max(0.15 - cur_drawdown, 0.0)*100:.2f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        
        st.markdown("#### Adjust Account Balance")
        adjust_amt = st.number_input("P&L Adjustment Amount ($)", value=0.0, step=100.0)
        if st.button("Apply Adjustment", use_container_width=True):
            new_eq = current_equity + adjust_amt
            now_str = datetime.utcnow().isoformat() + "Z"
            history_eq.append({"timestamp": now_str, "equity": new_eq})
            system_state["equity_history"] = history_eq
            
            with open(STATE_FILE, "w") as f:
                json.dump(system_state, f, indent=2)
            st.success(f"Adjusted balance by {adjust_amt:+.2f}. New Balance: ${new_eq:,.2f}")
            st.rerun()


# Tab 3: Monthly Trade Logger
with tab_log:
    st.markdown("### 📝 Trade Log Organized by Month")
    
    with st.expander("➕ Log New Completed Option / Equity Trade"):
        with st.form("manual_trade_logger"):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                t_date = st.date_input("Trade Date", value=datetime.utcnow().date())
                t_action = st.selectbox("Action", ["BUY", "SELL"])
                t_symbol = st.text_input("OPRA Option Symbol", placeholder="E.g. AAPL260814C00185000")
                t_quantity = st.number_input("Quantity / Contracts", min_value=1, value=1)
            with col_t2:
                t_price = st.number_input("Price Paid/Received ($ per share/contract)", min_value=0.0, value=2.50)
                t_strategy = st.text_input("Strategy Used", value="EMA_VWAP_crossover")
                t_pnl = st.number_input("Trade Net P&L ($)", value=0.0, help="For SELL actions, calculate: (Sell Price - Buy Price) * 100 * Contracts")
            
            submit_trade = st.form_submit_button("Record Trade Action", use_container_width=True)
            
            if submit_trade:
                t_timestamp = f"{t_date.strftime('%Y-%m-%d')}T12:00:00Z"
                
                trade_history.append({
                    "timestamp": t_timestamp,
                    "action": t_action.upper(),
                    "symbol": t_symbol.upper(),
                    "quantity": int(t_quantity),
                    "price": float(t_price),
                    "details": {
                        "strategy": t_strategy,
                        "pnl": float(t_pnl) if t_action.upper() == "SELL" else 0.0
                    }
                })
                
                with open(TRADE_LOG_FILE, "w") as f:
                    json.dump(trade_history, f, indent=2)
                st.success("Trade action recorded successfully!")
                st.rerun()
                
    df_trades = pd.DataFrame(trade_history)
    if not df_trades.empty:
        df_trades["timestamp"] = pd.to_datetime(df_trades["timestamp"])
        df_trades["Month"] = df_trades["timestamp"].dt.strftime("%Y-%m (%B)")
        
        df_trades["Strategy"] = df_trades["details"].apply(lambda d: d.get("strategy", ""))
        df_trades["PnL ($)"] = df_trades["details"].apply(lambda d: d.get("pnl", 0.0))
        
        months = df_trades["Month"].unique()
        months = sorted(months, reverse=True)
        
        selected_month = st.selectbox("Select Month to Inspect Log", months)
        
        df_filtered = df_trades[df_trades["Month"] == selected_month]
        
        df_disp = df_filtered[["timestamp", "action", "symbol", "quantity", "price", "Strategy", "PnL ($)"]]
        df_disp = df_disp.rename(columns={
            "timestamp": "Date Time",
            "action": "Action",
            "symbol": "Symbol",
            "quantity": "Qty",
            "price": "Price",
        })
        
        st.dataframe(df_disp, use_container_width=True)
        
        month_sells = df_filtered[df_filtered["action"] == "SELL"]
        month_pnl = month_sells["PnL ($)"].sum()
        month_wins = sum(1 for p in month_sells["PnL ($)"].sum() if p > 0) if isinstance(month_sells["PnL ($)"].sum(), list) else sum(1 for p in month_sells["PnL ($)"] if p > 0)
        month_total = len(month_sells)
        month_wr = (month_wins / month_total * 100) if month_total > 0 else 0.0
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Month P&L", f"${month_pnl:+,.2f}", delta=f"{month_pnl:+.2f}")
        col_m2.metric("Month Win Rate", f"{month_wr:.1f}%")
        col_m3.metric("Month Closed Trades", f"{month_total}")
    else:
        st.info("No trades currently logged.")


# Tab 4: Weekly Review Templates
with tab_review:
    st.markdown("### 🗓️ Weekly Systematic Review & Reflection")
    
    now_dt = datetime.utcnow()
    y_wk = now_dt.strftime("%Y_W%W")
    
    st.write(f"Generating Weekly review template for: **{y_wk}**")
    
    with st.form("weekly_review_form"):
        wk_pnl = st.number_input("Weekly Net P&L ($)", value=0.0)
        wk_mistakes = st.text_area("Trading Mistakes Made", placeholder="E.g. Overtraded during mid-day chop; did not wait for VWAP crossover confirmation on NVDA.")
        wk_learnings = st.text_area("Key Takeaways & Lessons", placeholder="E.g. Keep options size small during macro news drops. Trust the 50/250 EMA trends.")
        wk_rating = st.slider("Weekly Discipline Score (1 - 10)", 1, 10, 8)
        
        submit_weekly = st.form_submit_button("Publish Weekly Review File", use_container_width=True)
        
        if submit_weekly:
            filepath = os.path.join(JOURNAL_DIR, f"weekly_review_{y_wk}.md")
            
            review_md = f"""# WhiteLight Weekly Review - {y_wk}

## 1. Weekly Performance Summary
- **Weekly Net P&L**: ${wk_pnl:+,.2f}
- **Discipline Rating**: {wk_rating} / 10

## 2. Quantitative Performance Check
- **Systematic Trend Alignment**: Audited 50/250 EMA setups.
- **Circuit Breaker Status**: Intact and operational.

## 3. Trading Execution & Mistakes
{wk_mistakes if wk_mistakes else "No execution mistakes logged."}

## 4. Key Lessons & Takeaways
{wk_learnings if wk_learnings else "No takeaways logged."}

## 5. Goals for Next Week
- [ ] Maintain discipline meter above 80%.
- [ ] Wait for full structural VWAP confirmation on crossovers.
- [ ] Keep position sizes aligned with risk metrics.
"""
            with open(filepath, "w") as f:
                f.write(review_md)
                
            st.success(f"Weekly review successfully written to: {os.path.basename(filepath)}")
            st.rerun()

    weekly_files = glob.glob(os.path.join(JOURNAL_DIR, "weekly_review_*.md"))
    weekly_files.sort(reverse=True)
    
    if weekly_files:
        st.markdown("---")
        st.markdown("#### 📖 Review Past Weekly Reports")
        rev_basenames = [os.path.basename(f) for f in weekly_files]
        selected_rev = st.selectbox("Select Review File", rev_basenames)
        
        if selected_rev:
            selected_rev_path = os.path.join(JOURNAL_DIR, selected_rev)
            with open(selected_rev_path, "r") as f:
                rev_content = f.read()
                
            st.markdown(f"<div class='journal-box'>", unsafe_allow_html=True)
            st.markdown(rev_content)
            st.markdown(f"</div>", unsafe_allow_html=True)
