"""
Streamlit UI Components
"""

import streamlit as st
from typing import List, Dict, Any, Optional
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from engine.leg import LegConfig, LegAction
from metrics.calculator import BacktestMetrics


def render_metrics_dashboard(metrics: BacktestMetrics):
    """Render metrics dashboard with columns"""
    
    # Top row - Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_color = "normal" if metrics.net_pnl >= 0 else "inverse"
        st.metric("Net P&L", f"₹{metrics.net_pnl:,.0f}", 
                 delta=f"{metrics.net_pnl:+,.0f}", delta_color=delta_color)
    
    with col2:
        st.metric("Win Rate", f"{metrics.win_rate:.1f}%")
    
    with col3:
        st.metric("Max Drawdown", f"₹{metrics.max_drawdown:,.0f}")
    
    with col4:
        st.metric("Trades", metrics.num_trades)
    
    st.divider()
    
    # Detailed metrics in expandable section
    with st.expander("📊 Detailed Metrics", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Profit/Loss Analysis**")
            st.write(f"Total P&L: ₹{metrics.total_pnl:,.2f}")
            st.write(f"Brokerage: ₹{metrics.total_brokerage:,.2f}")
            st.write(f"Avg Profit/Trade: ₹{metrics.avg_profit_per_trade:,.2f}")
            st.write(f"Avg Win: ₹{metrics.avg_profit_winning:,.2f}")
            st.write(f"Avg Loss: ₹{metrics.avg_loss_losing:,.2f}")
        
        with col2:
            st.markdown("**Risk Metrics**")
            st.write(f"Max Single Win: ₹{metrics.max_profit_single_trade:,.2f}")
            st.write(f"Max Single Loss: ₹{metrics.max_loss_single_trade:,.2f}")
            st.write(f"Max DD Duration: {metrics.max_drawdown_duration} days")
            st.write(f"Return/MaxDD: {metrics.return_over_max_dd:.2f}")
            st.write(f"Profit Factor: {metrics.profit_factor:.2f}")
        
        with col3:
            st.markdown("**Streaks & Stats**")
            st.write(f"Winning Streak: {metrics.max_winning_streak}")
            st.write(f"Losing Streak: {metrics.max_losing_streak}")
            st.write(f"Expectancy: ₹{metrics.expectancy:,.2f}")
            st.write(f"Reward/Risk: {metrics.reward_to_risk:.2f}")
            st.write(f"Trading Days: {metrics.num_trading_days}")


def render_leg_builder(leg_id: int, key_prefix: str = "") -> Optional[LegConfig]:
    """
    Render a single leg configuration UI
    
    Args:
        leg_id: Unique leg identifier
        key_prefix: Prefix for streamlit keys
    
    Returns:
        LegConfig if valid, None otherwise
    """
    st.markdown(f"### Leg {leg_id}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        action = st.selectbox(
            "Action",
            ["SELL", "BUY"],
            key=f"{key_prefix}action_{leg_id}"
        )
        
        option_type = st.selectbox(
            "Option Type",
            ["CE", "PE"],
            key=f"{key_prefix}opt_type_{leg_id}"
        )
    
    with col2:
        strike = st.selectbox(
            "Strike",
            ["ATM"] + [f"ATM+{i}" for i in range(1, 11)] + [f"ATM-{i}" for i in range(1, 11)],
            key=f"{key_prefix}strike_{leg_id}"
        )
        
        expiry_type = st.selectbox(
            "Expiry",
            ["WEEK", "MONTH"],
            key=f"{key_prefix}expiry_{leg_id}"
        )
    
    with col3:
        lots = st.number_input(
            "Lots",
            min_value=1,
            value=1,
            key=f"{key_prefix}lots_{leg_id}"
        )
    
    # Exit parameters
    st.markdown("**Exit Parameters**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sl_type = st.radio(
            "SL Type",
            ["Points", "Percent", "None"],
            key=f"{key_prefix}sl_type_{leg_id}",
            horizontal=True
        )
        
        sl_points = None
        sl_percent = None
        
        if sl_type == "Points":
            sl_points = st.number_input(
                "SL Points",
                min_value=0.0,
                value=30.0,
                step=5.0,
                key=f"{key_prefix}sl_points_{leg_id}"
            )
        elif sl_type == "Percent":
            sl_percent = st.number_input(
                "SL %",
                min_value=0.0,
                value=30.0,
                step=5.0,
                key=f"{key_prefix}sl_pct_{leg_id}"
            )
    
    with col2:
        target_type = st.radio(
            "Target Type",
            ["Points", "Percent", "None"],
            key=f"{key_prefix}target_type_{leg_id}",
            horizontal=True
        )
        
        target_points = None
        target_percent = None
        
        if target_type == "Points":
            target_points = st.number_input(
                "Target Points",
                min_value=0.0,
                value=50.0,
                step=5.0,
                key=f"{key_prefix}target_points_{leg_id}"
            )
        elif target_type == "Percent":
            target_percent = st.number_input(
                "Target %",
                min_value=0.0,
                value=50.0,
                step=5.0,
                key=f"{key_prefix}target_pct_{leg_id}"
            )
    
    with col3:
        trailing_sl = st.checkbox(
            "Trailing SL",
            key=f"{key_prefix}trail_{leg_id}"
        )
        
        trail_activate = None
        trail_lock = None
        
        if trailing_sl:
            trail_activate = st.number_input(
                "Activate At (pts)",
                min_value=0.0,
                value=30.0,
                key=f"{key_prefix}trail_act_{leg_id}"
            )
            trail_lock = st.number_input(
                "Lock Profit (pts)",
                min_value=0.0,
                value=20.0,
                key=f"{key_prefix}trail_lock_{leg_id}"
            )
    
    return LegConfig(
        leg_id=leg_id,
        strike=strike,
        option_type=option_type,
        expiry_type=expiry_type,
        action=LegAction.BUY if action == "BUY" else LegAction.SELL,
        lots=lots,
        sl_points=sl_points,
        sl_percent=sl_percent,
        target_points=target_points,
        target_percent=target_percent,
        trailing_sl=trailing_sl,
        trail_activate_points=trail_activate,
        trail_lock_points=trail_lock
    )


def render_strategy_settings() -> Dict[str, Any]:
    """Render strategy configuration UI"""
    
    st.markdown("### ⚙️ Strategy Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        mode = st.selectbox(
            "Strategy Mode",
            ["INTRADAY", "BTST", "POSITIONAL"]
        )
        
        entry_time = st.time_input(
            "Entry Time",
            value=pd.to_datetime("09:20").time()
        )
        
        exit_time = st.time_input(
            "Exit Time",
            value=pd.to_datetime("15:15").time()
        )
    
    with col2:
        no_entry_after = st.time_input(
            "No Entry After",
            value=pd.to_datetime("14:30").time()
        )
        
        max_loss = st.number_input(
            "Max Loss (₹)",
            min_value=0,
            value=0,
            step=1000,
            help="0 = No limit"
        )
        
        max_profit = st.number_input(
            "Max Profit (₹)",
            min_value=0,
            value=0,
            step=1000,
            help="0 = No limit"
        )
    
    return {
        "mode": mode,
        "entry_time": entry_time.strftime("%H:%M"),
        "exit_time": exit_time.strftime("%H:%M"),
        "no_entry_after": no_entry_after.strftime("%H:%M"),
        "max_loss": max_loss if max_loss > 0 else None,
        "max_profit": max_profit if max_profit > 0 else None
    }


def render_date_range_selector(min_date: str, max_date: str) -> tuple:
    """Render date range selector"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=pd.to_datetime(min_date),
            min_value=pd.to_datetime(min_date),
            max_value=pd.to_datetime(max_date)
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=pd.to_datetime(max_date),
            min_value=pd.to_datetime(min_date),
            max_value=pd.to_datetime(max_date)
        )
    
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def render_cost_settings() -> Dict[str, float]:
    """Render slippage and brokerage settings"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        slippage = st.number_input(
            "Slippage %",
            min_value=0.0,
            max_value=1.0,
            value=0.05,
            step=0.01
        )
    
    with col2:
        brokerage = st.number_input(
            "Brokerage/Lot (₹)",
            min_value=0.0,
            value=20.0,
            step=5.0
        )
    
    return {
        "slippage_pct": slippage,
        "brokerage_per_lot": brokerage
    }
