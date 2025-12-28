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

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #00C853;
    }
    .stMetric {
        background-color: #1E1E1E;
        padding: 10px;
        border-radius: 5px;
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
        st.markdown("## Build Your Strategy")
        
        # Number of legs
        if 'num_legs' not in st.session_state:
            st.session_state.num_legs = 2
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("➕ Add Leg"):
                st.session_state.num_legs += 1
            if st.button("➖ Remove Leg") and st.session_state.num_legs > 1:
                st.session_state.num_legs -= 1
        
        # Render leg builders
        leg_configs = []
        for i in range(st.session_state.num_legs):
            with st.container():
                config = render_leg_builder(i + 1)
                leg_configs.append(config)
                st.divider()
        
        # Run backtest button
        st.markdown("---")
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
                
                # Run backtest with progress
                engine = BacktestEngine(loader)
                
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
                    use_container_width=True
                )
            
            with col2:
                st.plotly_chart(
                    create_drawdown_chart(result.equity_curve, daily_df),
                    use_container_width=True
                )
            
            # Monthly heatmap and distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.plotly_chart(
                    create_monthly_heatmap(daily_df),
                    use_container_width=True
                )
            
            with col2:
                st.plotly_chart(
                    create_trade_distribution(st.session_state.trades_df),
                    use_container_width=True
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
