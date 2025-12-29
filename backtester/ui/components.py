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
    Render a single leg configuration UI - Compact design
    
    Args:
        leg_id: Unique leg identifier
        key_prefix: Prefix for streamlit keys
    
    Returns:
        LegConfig if valid, None otherwise
    """
    # Compact header with colored badge
    st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
            <span style="background: linear-gradient(135deg, #00C853 0%, #00E676 100%); 
                         color: white; padding: 0.2rem 0.6rem; border-radius: 4px; 
                         font-size: 0.85rem; font-weight: 600; margin-right: 0.5rem;">
                Leg {leg_id}
            </span>
        </div>
    """, unsafe_allow_html=True)
    
    # Main settings in 5 columns for compact layout
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1.2, 1, 0.8])
    
    with col1:
        action = st.selectbox(
            "Action",
            ["SELL", "BUY"],
            key=f"{key_prefix}action_{leg_id}"
        )
    
    with col2:
        option_type = st.selectbox(
            "Type",
            ["CE", "PE"],
            key=f"{key_prefix}opt_type_{leg_id}"
        )
    
    with col3:
        strike = st.selectbox(
            "Strike",
            ["ATM"] + [f"ATM+{i}" for i in range(1, 11)] + [f"ATM-{i}" for i in range(1, 11)],
            key=f"{key_prefix}strike_{leg_id}"
        )
    
    with col4:
        expiry_type = st.selectbox(
            "Expiry",
            ["WEEK", "MONTH"],
            key=f"{key_prefix}expiry_{leg_id}"
        )
    
    with col5:
        lots = st.number_input(
            "Lots",
            min_value=1,
            value=1,
            key=f"{key_prefix}lots_{leg_id}"
        )
    # Exit parameters in collapsible expander for compact view
    with st.expander(f"⚙️ Exit Settings (SL/Target)", expanded=True):
        # Initialize all variables
        sl_points = None
        sl_percent = None
        sl_underlying_points = None
        sl_underlying_percent = None
        target_points = None
        target_percent = None
        target_underlying_points = None
        target_underlying_percent = None
        trailing_sl = False
        trail_type = "points"
        trail_activate_points = None
        trail_activate_percent = None
        trail_lock_points = None
        trail_lock_percent = None
        
        # Row 1: SL and Target settings
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Stop Loss**")
            sl_type = st.selectbox(
                "SL Type",
                ["None", "Points (Pts)", "Percent (%)", "Underlying Pts", "Underlying %"],
                key=f"{key_prefix}sl_type_{leg_id}"
            )
            
            if sl_type == "Points (Pts)":
                sl_points = st.number_input(
                    "SL Points",
                    min_value=0.0,
                    value=30.0,
                    step=5.0,
                    key=f"{key_prefix}sl_points_{leg_id}",
                    help="Stop loss in absolute points on option premium"
                )
            elif sl_type == "Percent (%)":
                sl_percent = st.number_input(
                    "SL %",
                    min_value=0.0,
                    value=30.0,
                    step=5.0,
                    key=f"{key_prefix}sl_pct_{leg_id}",
                    help="Stop loss as % of option premium"
                )
            elif sl_type == "Underlying Pts":
                sl_underlying_points = st.number_input(
                    "Nifty SL Pts",
                    min_value=0.0,
                    value=50.0,
                    step=10.0,
                    key=f"{key_prefix}sl_und_pts_{leg_id}",
                    help="Stop loss based on Nifty 50 movement in points"
                )
            elif sl_type == "Underlying %":
                sl_underlying_percent = st.number_input(
                    "Nifty SL %",
                    min_value=0.0,
                    value=1.0,
                    step=0.5,
                    key=f"{key_prefix}sl_und_pct_{leg_id}",
                    help="Stop loss based on Nifty 50 % movement"
                )
        
        with col2:
            st.markdown("**Target Profit**")
            target_type = st.selectbox(
                "Target Type",
                ["None", "Points (Pts)", "Percent (%)", "Underlying Pts", "Underlying %"],
                key=f"{key_prefix}target_type_{leg_id}"
            )
            
            if target_type == "Points (Pts)":
                target_points = st.number_input(
                    "Target Points",
                    min_value=0.0,
                    value=50.0,
                    step=5.0,
                    key=f"{key_prefix}target_points_{leg_id}",
                    help="Target in absolute points on option premium"
                )
            elif target_type == "Percent (%)":
                target_percent = st.number_input(
                    "Target %",
                    min_value=0.0,
                    value=50.0,
                    step=5.0,
                    key=f"{key_prefix}target_pct_{leg_id}",
                    help="Target as % of option premium"
                )
            elif target_type == "Underlying Pts":
                target_underlying_points = st.number_input(
                    "Nifty Target Pts",
                    min_value=0.0,
                    value=50.0,
                    step=10.0,
                    key=f"{key_prefix}target_und_pts_{leg_id}",
                    help="Target based on Nifty 50 movement in points"
                )
            elif target_type == "Underlying %":
                target_underlying_percent = st.number_input(
                    "Nifty Target %",
                    min_value=0.0,
                    value=1.0,
                    step=0.5,
                    key=f"{key_prefix}target_und_pct_{leg_id}",
                    help="Target based on Nifty 50 % movement"
                )
        
        # Row 2: Trailing SL
        st.markdown("---")
        st.markdown("**Trail SL**")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            trailing_sl = st.checkbox(
                "Enable Trail SL",
                key=f"{key_prefix}trail_{leg_id}",
                help="Move SL in your favor as price moves"
            )
        
        if trailing_sl:
            with col2:
                trail_type = st.selectbox(
                    "Trail Type",
                    ["Points", "Percentage"],
                    key=f"{key_prefix}trail_type_{leg_id}"
                )
            
            with col3:
                if trail_type == "Points":
                    trail_activate_points = st.number_input(
                        "Activate (Pts)",
                        min_value=0.0,
                        value=30.0,
                        step=5.0,
                        key=f"{key_prefix}trail_act_{leg_id}",
                        help="Profit in points to activate trailing"
                    )
                else:
                    trail_activate_percent = st.number_input(
                        "Activate (%)",
                        min_value=0.0,
                        value=20.0,
                        step=5.0,
                        key=f"{key_prefix}trail_act_pct_{leg_id}",
                        help="Profit % to activate trailing"
                    )
            
            # Second row for lock values
            col1, col2, col3 = st.columns([1, 1, 1])
            with col3:
                if trail_type == "Points":
                    trail_lock_points = st.number_input(
                        "Lock (Pts)",
                        min_value=0.0,
                        value=20.0,
                        step=5.0,
                        key=f"{key_prefix}trail_lock_{leg_id}",
                        help="Profit in points to lock"
                    )
                else:
                    trail_lock_percent = st.number_input(
                        "Lock (%)",
                        min_value=0.0,
                        value=15.0,
                        step=5.0,
                        key=f"{key_prefix}trail_lock_pct_{leg_id}",
                        help="Profit % to lock"
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
        sl_underlying_points=sl_underlying_points,
        sl_underlying_percent=sl_underlying_percent,
        target_points=target_points,
        target_percent=target_percent,
        target_underlying_points=target_underlying_points,
        target_underlying_percent=target_underlying_percent,
        trailing_sl=trailing_sl,
        trail_type=trail_type.lower() if trailing_sl else "points",
        trail_activate_points=trail_activate_points,
        trail_activate_percent=trail_activate_percent,
        trail_lock_points=trail_lock_points,
        trail_lock_percent=trail_lock_percent
    )


def render_strategy_settings() -> Dict[str, Any]:
    """Render strategy configuration UI"""
    
    # Strategy mode - full width for better visibility
    mode = st.selectbox(
        "Strategy Mode",
        ["INTRADAY", "BTST", "POSITIONAL"],
        key="strategy_mode"
    )
    
    st.markdown("---")
    
    # Time settings in columns
    col1, col2 = st.columns(2)
    
    with col1:
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
    
    st.markdown("---")
    
    # P&L limits - full width
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
