"""
Backtest Execution Engine - Candle-by-candle simulation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, time
import pandas as pd
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from data.loader import DataLoader
from .leg import Leg, LegState, LegConfig, LegAction
from .strategy import Strategy, StrategyConfig, StrategyMode


@dataclass
class Trade:
    """Record of a single trade"""
    date: str
    leg_id: int
    strike: str
    option_type: str
    action: str
    lots: int
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    exit_reason: str
    pnl_points: float
    pnl: float
    brokerage: float
    net_pnl: float


@dataclass
class DayResult:
    """Result for a single trading day"""
    date: str
    gross_pnl: float
    brokerage: float
    net_pnl: float
    num_trades: int
    trades: List[Trade] = field(default_factory=list)


@dataclass
class BacktestResult:
    """Complete backtest results"""
    # Summary
    total_pnl: float
    total_brokerage: float
    net_pnl: float
    num_trades: int
    num_days: int
    
    # Detailed results
    trades: List[Trade] = field(default_factory=list)
    daily_results: List[DayResult] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    def to_trades_df(self) -> pd.DataFrame:
        """Convert trades to DataFrame"""
        return pd.DataFrame([vars(t) for t in self.trades])
    
    def to_daily_df(self) -> pd.DataFrame:
        """Convert daily results to DataFrame"""
        return pd.DataFrame([{
            "date": d.date,
            "gross_pnl": d.gross_pnl,
            "brokerage": d.brokerage,
            "net_pnl": d.net_pnl,
            "num_trades": d.num_trades
        } for d in self.daily_results])


class BacktestEngine:
    """
    Candle-by-candle backtest execution.
    
    NON-NEGOTIABLE RULES:
    1. Process each candle individually
    2. Use OHLC for SL/Target checking
    3. Apply slippage on entry and exit
    4. Strategy-level risk overrides leg-level
    """
    
    def __init__(self, loader: DataLoader):
        self.loader = loader
        self.trades: List[Trade] = []
        self.daily_results: List[DayResult] = []
        self.equity_curve: List[float] = []
    
    def run(self, strategy: Strategy, 
            start_date: str, end_date: str,
            slippage_pct: float = 0.05,
            brokerage_per_lot: float = 20) -> BacktestResult:
        """
        Run backtest
        
        Args:
            strategy: Strategy to backtest
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            slippage_pct: Slippage percentage
            brokerage_per_lot: Brokerage per lot (one-way)
        
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
        
        print(f"Running backtest from {start_date} to {end_date}")
        print(f"Trading days: {len(trading_days)}")
        
        for day_idx, date in enumerate(trading_days):
            if (day_idx + 1) % 50 == 0:
                print(f"Processing day {day_idx + 1}/{len(trading_days)}: {date}")
            
            day_result = self._run_day(
                strategy, date, slippage_pct, brokerage_per_lot
            )
            
            if day_result:
                self.daily_results.append(day_result)
                self.trades.extend(day_result.trades)
                cumulative_pnl += day_result.net_pnl
                self.equity_curve.append(cumulative_pnl)
            
            # Reset strategy for next day
            strategy.reset_for_new_day()
        
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
    
    def _run_day(self, strategy: Strategy, date: str,
                 slippage_pct: float, brokerage_per_lot: float) -> Optional[DayResult]:
        """Run backtest for a single day"""
        
        # Load data for all legs
        leg_data: Dict[int, pd.DataFrame] = {}
        for leg in strategy.legs:
            try:
                df = self.loader.get_day_data(
                    leg.config.strike,
                    leg.config.option_type,
                    leg.config.expiry_type,
                    date
                )
                if not df.empty:
                    leg_data[leg.config.leg_id] = df
            except Exception as e:
                print(f"Error loading data for leg {leg.config.leg_id} on {date}: {e}")
        
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
        
        # Process each candle
        for timestamp in timestamps:
            current_time = timestamp.time()
            
            # Get current candles for all legs
            candle_data: Dict[int, pd.Series] = {}
            for leg_id, df in leg_data.items():
                candle = df[df['datetime'] == timestamp]
                if not candle.empty:
                    candle_data[leg_id] = candle.iloc[0]
            
            if not candle_data:
                continue
            
            # 1. Check entry
            if strategy.should_enter(current_time) and not strategy.entered_today:
                strategy.enter_all_legs(candle_data, timestamp, slippage_pct)
            
            # 2. Skip if not entered
            if not strategy.entered_today or not strategy.get_active_legs():
                continue
            
            # 3. Check strategy-level exits (highest priority)
            if strategy.check_strategy_sl():
                strategy.exit_all_legs(candle_data, timestamp, "STRATEGY_SL", slippage_pct)
                day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                break
            
            if strategy.check_strategy_target():
                strategy.exit_all_legs(candle_data, timestamp, "STRATEGY_TARGET", slippage_pct)
                day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                break
            
            # 4. Check time-based exit
            if strategy.should_exit_time(current_time):
                strategy.exit_all_legs(candle_data, timestamp, "TIME_EXIT", slippage_pct)
                day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                break
            
            # 5. Update legs and check individual exits
            exits = strategy.update_legs(candle_data, timestamp, slippage_pct)
            
            # If all legs exited, we're done for the day (for intraday)
            if not strategy.get_active_legs() and strategy.config.mode == StrategyMode.INTRADAY:
                day_trades.extend(self._create_trades(strategy.legs, date, brokerage_per_lot))
                break
        
        # Force exit any remaining positions at end of day (for intraday)
        if strategy.get_active_legs() and strategy.config.mode == StrategyMode.INTRADAY:
            last_timestamp = timestamps[-1]
            last_candles = {leg_id: leg_data[leg_id].iloc[-1] 
                          for leg_id in leg_data if not leg_data[leg_id].empty}
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
                
                trade = Trade(
                    date=date,
                    leg_id=leg.config.leg_id,
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
