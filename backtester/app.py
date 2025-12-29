"""
NIFTY Options Backtester - Streamlit Web App
AlgoTest-equivalent backtesting engine
"""

import streamlit as st
import pandas as pd
from pathlib import Path
import sys

# Add backtester to path
sys.path.insert(0, str(Path(__file__).parent))

from data.loader import DataLoader
from data.resolver import InstrumentResolver
from engine.leg import Leg, LegConfig, LegAction
from engine.strategy import Strategy, StrategyConfig, StrategyMode
from engine.backtest import BacktestEngine
from engine.backtest_optimized import OptimizedBacktestEngine
from metrics.calculator import MetricsCalculator
from metrics.monte_carlo import MonteCarloSimulator
from ui.components import (
    render_metrics_dashboard, render_leg_builder,
    render_strategy_settings, render_date_range_selector,
    render_cost_settings
)
from ui.charts import (
    create_equity_chart, create_drawdown_chart,
    create_monthly_heatmap, create_trade_distribution
)
from config import DATA_DIR

# Page config
st.set_page_config(
    page_title="NIFTY Options Backtester",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for modern, high-contrast styling
st.markdown("""
<style>
    /* Keep sidebar always expanded */
    [data-testid="stSidebar"][aria-expanded="false"] {
        display: block !important;
        min-width: 300px !important;
    }
    
    /* Reduce overall padding and spacing */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.5rem !important;
    }
    
    /* Compact header */
    h1 {
        font-size: 1.8rem !important;
        margin-bottom: 0.2rem !important;
        color: #ffffff !important;
    }
    
    h2, h3 {
        font-size: 1.1rem !important;
        margin-top: 0.5rem !important;
        margin-bottom: 0.3rem !important;
        color: #e0e0e0 !important;
    }
    
    /* HIGH CONTRAST Labels - Bright white */
    .stSelectbox label, .stNumberInput label, .stDateInput label, 
    .stTimeInput label, .stCheckbox label, .stRadio label {
        font-size: 0.9rem !important;
        margin-bottom: 0.2rem !important;
        font-weight: 600 !important;
        color: #ffffff !important;
    }
    
    /* Reduce widget spacing */
    .stSelectbox, .stNumberInput, .stTextInput, 
    .stDateInput, .stTimeInput {
        margin-bottom: 0.5rem !important;
    }
    
    /* HIGH CONTRAST Input fields - Light background with dark text */
    .stSelectbox > div > div,
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        background-color: #2d2d3d !important;
        color: #ffffff !important;
        border: 1px solid #4a4a6a !important;
        border-radius: 6px !important;
    }
    
    /* Dropdown options - Dark with white text */
    [data-baseweb="select"] {
        background-color: #2d2d3d !important;
    }
    
    [data-baseweb="menu"] {
        background-color: #2d2d3d !important;
        border: 1px solid #4a4a6a !important;
    }
    
    [data-baseweb="menu"] li {
        color: #ffffff !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background-color: #4a4a6a !important;
    }
    
    /* HIGH CONTRAST Metrics styling */
    .stMetric {
        background-color: #1e1e2e !important;
        padding: 1rem !important;
        border-radius: 8px;
        border-left: 4px solid #4CAF50 !important;
    }
    
    .stMetric label {
        font-size: 0.85rem !important;
        color: #b0b0b0 !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        color: #ffffff !important;
    }
    
    /* Compact dividers */
    hr {
        margin: 0.8rem 0 !important;
        border-color: #4a4a6a !important;
        opacity: 0.5;
    }
    
    /* HIGH CONTRAST Button styling */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.2rem !important;
        transition: all 0.2s ease;
        border: 1px solid #4a4a6a !important;
        background-color: #2d2d3d !important;
        color: #ffffff !important;
    }
    
    .stButton > button:hover {
        background-color: #3d3d5d !important;
        border-color: #6a6a8a !important;
    }
    
    /* Primary button - Bright green */
    .stButton > button[kind="primary"] {
        background-color: #4CAF50 !important;
        border-color: #4CAF50 !important;
        color: #ffffff !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #66BB6A !important;
        border-color: #66BB6A !important;
    }
    
    /* HIGH CONTRAST Expander styling */
    .streamlit-expanderHeader {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        background-color: #252538 !important;
        border: 1px solid #3a3a5a !important;
        border-radius: 6px !important;
        padding: 0.6rem 1rem !important;
        color: #ffffff !important;
    }
    
    .streamlit-expanderContent {
        background-color: #1e1e2e !important;
        border: 1px solid #3a3a5a !important;
        border-top: none !important;
        border-radius: 0 0 6px 6px !important;
        padding: 1rem !important;
    }
    
    /* HIGH CONTRAST Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #161625 !important;
        min-width: 280px !important;
    }
    
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-size: 1.1rem !important;
        color: #4CAF50 !important;
        font-weight: 700 !important;
    }
    
    [data-testid="stSidebar"] label {
        color: #e0e0e0 !important;
        font-weight: 500 !important;
    }
    
    /* Tab styling - HIGH CONTRAST */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background-color: #1e1e2e !important;
        border-radius: 8px;
        padding: 0.3rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.6rem 1.2rem !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        color: #b0b0b0 !important;
        background-color: transparent !important;
        border-radius: 6px !important;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff !important;
        background-color: #4CAF50 !important;
    }
    
    /* Remove extra margins from columns */
    [data-testid="column"] {
        padding: 0 0.4rem !important;
    }
    
    /* Checkbox styling */
    .stCheckbox label span {
        color: #ffffff !important;
    }
    
    /* Success/Error messages */
    .stSuccess {
        background-color: #1b4332 !important;
        color: #a7f3d0 !important;
        padding: 0.8rem 1rem !important;
        border-radius: 8px !important;
        border-left: 4px solid #4CAF50 !important;
    }
    
    .stError {
        background-color: #4a1515 !important;
        color: #fca5a5 !important;
        padding: 0.8rem 1rem !important;
        border-radius: 8px !important;
        border-left: 4px solid #ef4444 !important;
    }
    
    /* Download button */
    .stDownloadButton button {
        width: 100% !important;
        background-color: #2d2d3d !important;
        color: #ffffff !important;
    }
    
    /* Date input - HIGH CONTRAST */
    .stDateInput input {
        background-color: #2d2d3d !important;
        color: #ffffff !important;
        border: 1px solid #4a4a6a !important;
    }
    
    /* Time input - HIGH CONTRAST */
    .stTimeInput input {
        background-color: #2d2d3d !important;
        color: #ffffff !important;
        border: 1px solid #4a4a6a !important;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown("# 📊 NIFTY Options Backtester")
    st.markdown("*AlgoTest-equivalent backtesting engine*")
    
    # Initialize data loader
    try:
        loader = DataLoader()
        min_date, max_date = loader.get_date_range("WEEK")
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Make sure historical data is in the correct location")
        return
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # Strategy settings
        strategy_settings = render_strategy_settings()
        
        st.divider()
        
        # Date range
        st.markdown("### 📅 Date Range")
        start_date, end_date = render_date_range_selector(min_date, max_date)
        
        st.divider()
        
        # Cost settings
        st.markdown("### 💰 Costs")
        cost_settings = render_cost_settings()
        
        st.divider()
        
        # Monte Carlo settings
        st.markdown("### 🎲 Monte Carlo")
        run_monte_carlo = st.checkbox("Run Monte Carlo", value=True)
        mc_simulations = st.number_input(
            "Simulations", 
            min_value=1000, 
            max_value=50000,
            value=10000,
            step=1000,
            disabled=not run_monte_carlo
        )
    
    # Main content area
    tab1, tab2, tab3 = st.tabs(["🦵 Leg Builder", "📈 Results", "📋 Trade Log"])
    
    with tab1:
        # Compact header with inline buttons
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            st.markdown("### Build Your Strategy")
        with col2:
            if st.button("➕ Add", key="add_leg"):
                if 'num_legs' not in st.session_state:
                    st.session_state.num_legs = 2
                st.session_state.num_legs += 1
        with col3:
            if st.button("➖ Remove", key="remove_leg"):
                if 'num_legs' not in st.session_state:
                    st.session_state.num_legs = 2
                if st.session_state.num_legs > 1:
                    st.session_state.num_legs -= 1
        
        # Number of legs
        if 'num_legs' not in st.session_state:
            st.session_state.num_legs = 2
        
        # Render leg builders in compact cards
        leg_configs = []
        for i in range(st.session_state.num_legs):
            config = render_leg_builder(i + 1)
            leg_configs.append(config)
        
        # Run backtest button
        st.markdown("")  # Small spacer
        if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
            try:
                # Create strategy
                strategy_config = StrategyConfig(
                    name="Custom Strategy",
                    mode=StrategyMode[strategy_settings["mode"]],
                    entry_time=strategy_settings["entry_time"],
                    exit_time=strategy_settings["exit_time"],
                    no_entry_after=strategy_settings["no_entry_after"],
                    max_loss=strategy_settings["max_loss"],
                    max_profit=strategy_settings["max_profit"]
                )
                
                strategy = Strategy(config=strategy_config)
                
                # Add legs
                for config in leg_configs:
                    strategy.add_leg(config)
                
                # Run backtest with optimized engine
                engine = OptimizedBacktestEngine(loader)
                
                # Progress tracking
                import time as time_module
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time_module.time()
                
                def update_progress(day_idx, total_days, date):
                    progress = (day_idx + 1) / total_days
                    progress_bar.progress(progress)
                    
                    elapsed = time_module.time() - start_time
                    if day_idx > 0:
                        avg_time_per_day = elapsed / (day_idx + 1)
                        remaining_days = total_days - day_idx - 1
                        remaining_time = avg_time_per_day * remaining_days
                        
                        elapsed_str = f"{int(elapsed//60)}m {int(elapsed%60)}s"
                        remaining_str = f"{int(remaining_time//60)}m {int(remaining_time%60)}s"
                        
                        status_text.markdown(
                            f"**Processing:** {date} ({day_idx + 1}/{total_days}) | "
                            f"**Elapsed:** {elapsed_str} | **Remaining:** {remaining_str}"
                        )
                    else:
                        status_text.markdown(f"**Processing:** {date} ({day_idx + 1}/{total_days})")
                
                result = engine.run(
                    strategy,
                    start_date,
                    end_date,
                    slippage_pct=cost_settings["slippage_pct"],
                    brokerage_per_lot=cost_settings["brokerage_per_lot"],
                    progress_callback=update_progress
                )
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                # Calculate metrics
                calculator = MetricsCalculator()
                metrics = calculator.calculate(result)
                
                # Store in session state
                st.session_state.result = result
                st.session_state.metrics = metrics
                st.session_state.daily_df = result.to_daily_df()
                st.session_state.trades_df = result.to_trades_df()
                
                # Run Monte Carlo if enabled
                if run_monte_carlo:
                    mc_status = st.empty()
                    mc_status.markdown("**Running Monte Carlo simulations...**")
                    mc_sim = MonteCarloSimulator(num_simulations=mc_simulations)
                    st.session_state.mc_result = mc_sim.simulate(result)
                    mc_status.empty()
                
                total_time = time_module.time() - start_time
                st.success(f"✅ Backtest complete! {result.num_trades} trades over {result.num_days} days in {total_time:.1f}s")
                
            except Exception as e:
                st.error(f"Backtest failed: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    with tab2:
        if 'result' not in st.session_state:
            st.info("Run a backtest to see results")
        else:
            result = st.session_state.result
            metrics = st.session_state.metrics
            daily_df = st.session_state.daily_df
            
            # Metrics dashboard
            render_metrics_dashboard(metrics)
            
            st.divider()
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.plotly_chart(
                    create_equity_chart(result.equity_curve, daily_df),
                    use_container_width=True,
                    key="equity_chart"
                )
            
            with col2:
                st.plotly_chart(
                    create_drawdown_chart(result.equity_curve, daily_df),
                    use_container_width=True,
                    key="drawdown_chart"
                )
            
            # Monthly heatmap and distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.plotly_chart(
                    create_monthly_heatmap(daily_df),
                    use_container_width=True,
                    key="monthly_heatmap"
                )
            
            with col2:
                st.plotly_chart(
                    create_trade_distribution(st.session_state.trades_df),
                    use_container_width=True,
                    key="trade_distribution"
                )
            
            # Monte Carlo results
            if 'mc_result' in st.session_state and st.session_state.mc_result:
                st.divider()
                st.markdown("### 🎲 Monte Carlo Analysis")
                
                mc = st.session_state.mc_result
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Max DD (95%)", f"₹{mc.max_drawdown_95:,.0f}")
                with col2:
                    st.metric("Worst Streak (95%)", mc.worst_losing_streak_95)
                with col3:
                    st.metric("CAGR (Median)", f"{mc.cagr_median:.1f}%")
                with col4:
                    st.metric("Prob. of Ruin", f"{mc.probability_of_ruin:.1f}%")
                
                with st.expander("Full Monte Carlo Stats"):
                    for key, value in mc.to_dict().items():
                        st.write(f"**{key}**: {value}")
            
            # Yearly/Monthly P&L tables
            st.divider()
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Yearly P&L")
                calculator = MetricsCalculator()
                yearly = calculator.get_yearly_pnl(result)
                if not yearly.empty:
                    st.dataframe(yearly, use_container_width=True)
            
            with col2:
                st.markdown("### Monthly P&L")
                monthly = calculator.get_monthly_pnl(result)
                if not monthly.empty:
                    st.dataframe(monthly.tail(12), use_container_width=True)
    
    with tab3:
        if 'trades_df' not in st.session_state:
            st.info("Run a backtest to see trades")
        else:
            trades_df = st.session_state.trades_df
            
            st.markdown(f"### Trade Log ({len(trades_df)} trades)")
            
            # Download button
            csv = trades_df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                "trades.csv",
                "text/csv",
                use_container_width=True
            )
            
            # Display trades
            st.dataframe(
                trades_df,
                use_container_width=True,
                height=500
            )


if __name__ == "__main__":
    main()
