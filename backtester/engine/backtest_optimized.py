"""
Optimized Backtest Engine - Performance-optimized simulation

Key optimizations:
1. Pre-indexed DataFrames for O(1) timestamp lookups
2. Avoid repeated DataFrame filtering 
3. Reduced data copying
4. NumPy arrays for OHLC access

Maintains exact same logic as original engine for correctness.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from data.loader import DataLoader
from .leg import Leg, LegState, LegConfig, LegAction
from .strategy import Strategy, StrategyConfig, StrategyMode
from .backtest import Trade, DayResult, BacktestResult


class OptimizedBacktestEngine:
    """
    Performance-optimized backtest execution.
    
    Key optimizations:
    1. Pre-indexed DataFrames for O(1) timestamp lookups
    2. Avoid repeated DataFrame filtering
    3. Batch data loading per day
    
    Maintains exact same logic as original engine.
    """
    
    def __init__(self, loader: DataLoader):
        self.loader = loader
        self.trades: List[Trade] = []
        self.daily_results: List[DayResult] = []
        self.equity_curve: List[float] = []
    
    def run(self, strategy: Strategy, 
            start_date: str, end_date: str,
            slippage_pct: float = 0.05,
            brokerage_per_lot: float = 20,
            progress_callback=None) -> BacktestResult:
        """
        Run optimized backtest
        
        Args:
            strategy: Strategy to backtest
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            slippage_pct: Slippage percentage
            brokerage_per_lot: Brokerage per lot (one-way)
            progress_callback: Optional callback(day_idx, total_days, date)
        
        Returns:
            BacktestResult with all results
        """
        self.trades = []
        self.daily_results = []
        self.equity_curve = []
        cumulative_pnl = 0.0
        
        # Get trading days
        expiry_type = strategy.legs[0].config.expiry_type if strategy.legs else "WEEK"
        trading_days = self.loader.get_trading_days(expiry_type, start_date, end_date)
        
        total_days = len(trading_days)
        
        for day_idx, date in enumerate(trading_days):
            # Call progress callback if provided
            if progress_callback:
                progress_callback(day_idx, total_days, date)
            
            day_result = self._run_day_optimized(
                strategy, date, slippage_pct, brokerage_per_lot
            )
            
            if day_result:
                self.daily_results.append(day_result)
                self.trades.extend(day_result.trades)
                cumulative_pnl += day_result.net_pnl
                self.equity_curve.append(cumulative_pnl)
            
            # Reset strategy for next day based on mode
            if strategy.config.mode == StrategyMode.INTRADAY:
                # Intraday: Full reset - new legs each day
                strategy.reset_for_new_day()
            else:
                # BTST/Positional: Keep active legs, only reset daily flags
                strategy.reset_daily_flags()
        
        # Calculate totals
        total_pnl = sum(d.gross_pnl for d in self.daily_results)
        total_brokerage = sum(d.brokerage for d in self.daily_results)
        
        return BacktestResult(
            total_pnl=total_pnl,
            total_brokerage=total_brokerage,
            net_pnl=total_pnl - total_brokerage,
            num_trades=len(self.trades),
            num_days=len(self.daily_results),
            trades=self.trades,
            daily_results=self.daily_results,
            equity_curve=self.equity_curve
        )
    
    def _run_day_optimized(self, strategy: Strategy, date: str,
                           slippage_pct: float, brokerage_per_lot: float) -> Optional[DayResult]:
        """Run optimized backtest for a single day"""
        
        # Load data for all legs with datetime indexing for O(1) lookups
        leg_data: Dict[int, pd.DataFrame] = {}
        leg_datetime_idx: Dict[int, Dict] = {}  # Maps datetime -> row data as dict
        
        for leg in strategy.legs:
            try:
                df = self.loader.get_day_data(
                    leg.config.strike,
                    leg.config.option_type,
                    leg.config.expiry_type,
                    date
                )
                if not df.empty:
                    # Convert UTC to IST for simulation
                    # India does not use DST, so fixed +5:30 offset is correct year-round
                    df['datetime'] = df['datetime'] + pd.Timedelta(hours=5, minutes=30)
                    
                    leg_data[leg.config.leg_id] = df
                    # Build datetime -> row dict using vectorized operations (faster than iterrows)
                    # Use zip with datetime column and records for O(1) lookup
                    datetimes = df['datetime'].tolist()
                    records = df.to_dict('records')
                    leg_datetime_idx[leg.config.leg_id] = dict(zip(datetimes, records))
            except Exception as e:
                pass
        
        if not leg_data:
            return None
        
        # Get common timestamps across all legs
        all_times = set()
        for df in leg_data.values():
            all_times.update(df['datetime'].tolist())
        timestamps = sorted(all_times)
        
        if not timestamps:
            return None
        
        day_trades: List[Trade] = []
        
        # Process each candle - same logic as original but with optimized lookups
        for timestamp in timestamps:
            current_time = timestamp.time()
            
            # Get current candles for all legs using pre-built dict (O(1) lookup)
            candle_data: Dict[int, pd.Series] = {}
            for leg_id, dt_idx in leg_datetime_idx.items():
                if timestamp in dt_idx:
                    candle_data[leg_id] = dt_idx[timestamp]
            
            if not candle_data:
                continue
            
            # 1. Check entry for today's NEW position
            if strategy.should_enter(current_time) and not strategy.entered_today:
                strategy.enter_all_legs(candle_data, timestamp, slippage_pct)
            
            # 2. For BTST: Check exit for YESTERDAY's position (pending_exit_legs)
            if strategy.config.mode == StrategyMode.BTST and strategy.has_pending_exit():
                if strategy.should_exit_time(current_time):
                    strategy.exit_pending_legs(candle_data, timestamp, "TIME_EXIT", slippage_pct)
                    day_trades.extend(self._create_trades(strategy.get_pending_exit_legs(), date, brokerage_per_lot))
                    strategy.clear_pending_exit()
            
            # 3. Skip if no active positions AND no pending exits
            has_active_positions = strategy.get_active_legs()
            has_pending = strategy.has_pending_exit()
            
            if strategy.config.mode == StrategyMode.INTRADAY:
                # Intraday: Need entry today AND active legs
                if not strategy.entered_today or not has_active_positions:
                    continue
            elif strategy.config.mode == StrategyMode.BTST:
                # BTST: Need active legs OR pending exit legs
                if not has_active_positions and not has_pending and not strategy.entered_today:
                    continue
            else:
                # Positional: Just need active legs
                if not has_active_positions and not strategy.entered_today:
                    continue
            
            # 4. Check strategy-level exits (for today's active legs only)
            if has_active_positions:
                if strategy.check_strategy_sl():
                    strategy.exit_all_legs(candle_data, timestamp, "STRATEGY_SL", slippage_pct)
                    day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                    if strategy.config.mode == StrategyMode.INTRADAY:
                        break
                    continue
                
                if strategy.check_strategy_target():
                    strategy.exit_all_legs(candle_data, timestamp, "STRATEGY_TARGET", slippage_pct)
                    day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                    if strategy.config.mode == StrategyMode.INTRADAY:
                        break
                    continue
                
                # 5. Check time-based exit (for Intraday only - BTST exits pending legs above)
                if strategy.config.mode == StrategyMode.INTRADAY and strategy.should_exit_time(current_time):
                    strategy.exit_all_legs(candle_data, timestamp, "TIME_EXIT", slippage_pct)
                    day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                    break
                
                # 6. Update legs and check individual exits
                exits = strategy.update_legs(candle_data, timestamp, slippage_pct)
                
                # If all legs exited, we're done for the day (for intraday)
                if not strategy.get_active_legs() and strategy.config.mode == StrategyMode.INTRADAY:
                    day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                    break
        
        # Force exit any remaining positions at end of day (for intraday)
        if strategy.get_active_legs() and strategy.config.mode == StrategyMode.INTRADAY:
            last_timestamp = timestamps[-1]
            last_candles = {}
            for leg_id, dt_idx in leg_datetime_idx.items():
                if last_timestamp in dt_idx:
                    last_candles[leg_id] = dt_idx[last_timestamp]
            if last_candles:
                strategy.exit_all_legs(last_candles, last_timestamp, "EOD_EXIT", slippage_pct)
                day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
        
        if not day_trades:
            return None
        
        gross_pnl = sum(t.pnl for t in day_trades)
        total_brokerage = sum(t.brokerage for t in day_trades)
        
        return DayResult(
            date=date,
            gross_pnl=gross_pnl,
            brokerage=total_brokerage,
            net_pnl=gross_pnl - total_brokerage,
            num_trades=len(day_trades),
            trades=day_trades
        )
    
    def _create_trades(self, legs: List[Leg], date: str, 
                       brokerage_per_lot: float) -> List[Trade]:
        """Create trade records from exited legs"""
        trades = []
        
        for leg in legs:
            if leg.state == LegState.EXITED and leg.exit_time:
                # Brokerage for entry + exit
                brokerage = brokerage_per_lot * leg.config.lots * 2
                
                # Generate instrument name with actual strike price (e.g., "NIFTY 13000 CE")
                # Falls back to ATM notation if actual strike not captured
                if leg.actual_strike_price:
                    instrument = f"NIFTY {leg.actual_strike_price} {leg.config.option_type}"
                else:
                    instrument = f"NIFTY {leg.config.strike} {leg.config.option_type}"
                
                trade = Trade(
                    date=date,
                    leg_id=leg.config.leg_id,
                    instrument=instrument,
                    strike=leg.config.strike,
                    option_type=leg.config.option_type,
                    action=leg.config.action.value,
                    lots=leg.config.lots,
                    entry_time=str(leg.entry_time),
                    entry_price=leg.entry_price,
                    exit_time=str(leg.exit_time),
                    exit_price=leg.exit_price,
                    exit_reason=leg.exit_reason,
                    pnl_points=leg.get_realized_pnl_points(),
                    pnl=leg.get_realized_pnl(),
                    brokerage=brokerage,
                    net_pnl=leg.get_realized_pnl() - brokerage
                )
                trades.append(trade)
        
        return trades
