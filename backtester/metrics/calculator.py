"""
Metrics Calculator - AlgoTest-equivalent metrics
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from engine.backtest import BacktestResult, Trade


@dataclass
class BacktestMetrics:
    """Complete backtest metrics - matches AlgoTest UI"""
    # Basic Stats
    total_pnl: float
    net_pnl: float
    total_brokerage: float
    num_trades: int
    num_winning_trades: int
    num_losing_trades: int
    
    # Win/Loss Analysis
    win_rate: float
    avg_profit_per_trade: float
    avg_profit_winning: float
    avg_loss_losing: float
    max_profit_single_trade: float
    max_loss_single_trade: float
    
    # Risk Metrics
    max_drawdown: float
    max_drawdown_pct: float
    max_drawdown_duration: int  # In trading days
    return_over_max_dd: float
    
    # Ratios
    reward_to_risk: float
    expectancy: float
    profit_factor: float
    
    # Streaks
    max_winning_streak: int
    max_losing_streak: int
    max_trades_during_drawdown: int
    
    # Time-based
    num_trading_days: int
    avg_trades_per_day: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "Total P&L": f"₹{self.total_pnl:,.2f}",
            "Net P&L (after costs)": f"₹{self.net_pnl:,.2f}",
            "Total Brokerage": f"₹{self.total_brokerage:,.2f}",
            "Number of Trades": self.num_trades,
            "Winning Trades": self.num_winning_trades,
            "Losing Trades": self.num_losing_trades,
            "Win Rate": f"{self.win_rate:.1f}%",
            "Avg Profit/Trade": f"₹{self.avg_profit_per_trade:,.2f}",
            "Avg Profit (Winners)": f"₹{self.avg_profit_winning:,.2f}",
            "Avg Loss (Losers)": f"₹{self.avg_loss_losing:,.2f}",
            "Max Profit (Single)": f"₹{self.max_profit_single_trade:,.2f}",
            "Max Loss (Single)": f"₹{self.max_loss_single_trade:,.2f}",
            "Max Drawdown": f"₹{self.max_drawdown:,.2f}",
            "Max Drawdown %": f"{self.max_drawdown_pct:.1f}%",
            "Max DD Duration": f"{self.max_drawdown_duration} days",
            "Return / Max DD": f"{self.return_over_max_dd:.2f}",
            "Reward to Risk": f"{self.reward_to_risk:.2f}",
            "Expectancy": f"₹{self.expectancy:,.2f}",
            "Profit Factor": f"{self.profit_factor:.2f}",
            "Max Winning Streak": self.max_winning_streak,
            "Max Losing Streak": self.max_losing_streak,
            "Trading Days": self.num_trading_days,
            "Avg Trades/Day": f"{self.avg_trades_per_day:.1f}"
        }


class MetricsCalculator:
    """Calculate all backtest metrics"""
    
    def calculate(self, result: BacktestResult) -> BacktestMetrics:
        """Calculate complete metrics from backtest result"""
        trades_df = result.to_trades_df()
        daily_df = result.to_daily_df()
        equity = result.equity_curve
        
        if trades_df.empty:
            return self._empty_metrics()
        
        # Basic stats
        total_pnl = result.total_pnl
        net_pnl = result.net_pnl
        total_brokerage = result.total_brokerage
        num_trades = len(trades_df)
        
        # Win/Loss
        winners = trades_df[trades_df['net_pnl'] > 0]
        losers = trades_df[trades_df['net_pnl'] < 0]
        
        num_winning = len(winners)
        num_losing = len(losers)
        win_rate = (num_winning / num_trades * 100) if num_trades > 0 else 0
        
        avg_profit_per_trade = net_pnl / num_trades if num_trades > 0 else 0
        avg_profit_winning = winners['net_pnl'].mean() if not winners.empty else 0
        avg_loss_losing = abs(losers['net_pnl'].mean()) if not losers.empty else 0
        
        max_profit_single = trades_df['net_pnl'].max() if not trades_df.empty else 0
        max_loss_single = abs(trades_df['net_pnl'].min()) if not trades_df.empty else 0
        
        # Drawdown analysis
        dd_analysis = self._calculate_drawdown(equity)
        max_drawdown = dd_analysis['max_drawdown']
        max_dd_pct = dd_analysis['max_drawdown_pct']
        max_dd_duration = dd_analysis['max_duration']
        max_trades_during_dd = dd_analysis['max_trades_during_dd']
        
        # Return / Max DD
        return_over_max_dd = abs(net_pnl / max_drawdown) if max_drawdown != 0 else 0
        
        # Ratios
        reward_to_risk = avg_profit_winning / avg_loss_losing if avg_loss_losing > 0 else 0
        expectancy = (win_rate/100 * avg_profit_winning) - ((100-win_rate)/100 * avg_loss_losing)
        
        total_wins = winners['net_pnl'].sum() if not winners.empty else 0
        total_losses = abs(losers['net_pnl'].sum()) if not losers.empty else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Streaks
        winning_streak, losing_streak = self._calculate_streaks(trades_df)
        
        # Time-based
        num_trading_days = len(daily_df)
        avg_trades_per_day = num_trades / num_trading_days if num_trading_days > 0 else 0
        
        return BacktestMetrics(
            total_pnl=total_pnl,
            net_pnl=net_pnl,
            total_brokerage=total_brokerage,
            num_trades=num_trades,
            num_winning_trades=num_winning,
            num_losing_trades=num_losing,
            win_rate=win_rate,
            avg_profit_per_trade=avg_profit_per_trade,
            avg_profit_winning=avg_profit_winning,
            avg_loss_losing=avg_loss_losing,
            max_profit_single_trade=max_profit_single,
            max_loss_single_trade=max_loss_single,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_duration=max_dd_duration,
            return_over_max_dd=return_over_max_dd,
            reward_to_risk=reward_to_risk,
            expectancy=expectancy,
            profit_factor=profit_factor,
            max_winning_streak=winning_streak,
            max_losing_streak=losing_streak,
            max_trades_during_drawdown=max_trades_during_dd,
            num_trading_days=num_trading_days,
            avg_trades_per_day=avg_trades_per_day
        )
    
    def _calculate_drawdown(self, equity: List[float]) -> Dict[str, Any]:
        """Calculate drawdown metrics"""
        if not equity:
            return {
                'max_drawdown': 0,
                'max_drawdown_pct': 0,
                'max_duration': 0,
                'max_trades_during_dd': 0
            }
        
        equity_arr = np.array(equity)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = peak - equity_arr
        
        max_dd = drawdown.max()
        max_dd_pct = (max_dd / peak.max() * 100) if peak.max() > 0 else 0
        
        # Calculate duration
        in_drawdown = drawdown > 0
        max_duration = 0
        current_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0
        
        # Trades during drawdown
        max_trades_during_dd = 0
        trades_in_current_dd = 0
        
        for i, is_dd in enumerate(in_drawdown):
            if is_dd:
                trades_in_current_dd += 1
                max_trades_during_dd = max(max_trades_during_dd, trades_in_current_dd)
            else:
                trades_in_current_dd = 0
        
        return {
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct,
            'max_duration': max_duration,
            'max_trades_during_dd': max_trades_during_dd
        }
    
    def _calculate_streaks(self, trades_df: pd.DataFrame) -> tuple:
        """Calculate max winning and losing streaks"""
        if trades_df.empty:
            return 0, 0
        
        wins = (trades_df['net_pnl'] > 0).astype(int)
        
        max_winning = 0
        max_losing = 0
        current_winning = 0
        current_losing = 0
        
        for is_win in wins:
            if is_win:
                current_winning += 1
                current_losing = 0
                max_winning = max(max_winning, current_winning)
            else:
                current_losing += 1
                current_winning = 0
                max_losing = max(max_losing, current_losing)
        
        return max_winning, max_losing
    
    def _empty_metrics(self) -> BacktestMetrics:
        """Return empty metrics"""
        return BacktestMetrics(
            total_pnl=0, net_pnl=0, total_brokerage=0,
            num_trades=0, num_winning_trades=0, num_losing_trades=0,
            win_rate=0, avg_profit_per_trade=0,
            avg_profit_winning=0, avg_loss_losing=0,
            max_profit_single_trade=0, max_loss_single_trade=0,
            max_drawdown=0, max_drawdown_pct=0, max_drawdown_duration=0,
            return_over_max_dd=0, reward_to_risk=0, expectancy=0, profit_factor=0,
            max_winning_streak=0, max_losing_streak=0, max_trades_during_drawdown=0,
            num_trading_days=0, avg_trades_per_day=0
        )
    
    def get_monthly_pnl(self, result: BacktestResult) -> pd.DataFrame:
        """Get monthly P&L breakdown"""
        daily_df = result.to_daily_df()
        if daily_df.empty:
            return pd.DataFrame()
        
        daily_df['date'] = pd.to_datetime(daily_df['date'])
        daily_df['month'] = daily_df['date'].dt.to_period('M')
        
        monthly = daily_df.groupby('month').agg({
            'net_pnl': 'sum',
            'num_trades': 'sum'
        }).reset_index()
        
        monthly.columns = ['Month', 'P&L', 'Trades']
        return monthly
    
    def get_yearly_pnl(self, result: BacktestResult) -> pd.DataFrame:
        """Get yearly P&L breakdown"""
        daily_df = result.to_daily_df()
        if daily_df.empty:
            return pd.DataFrame()
        
        daily_df['date'] = pd.to_datetime(daily_df['date'])
        daily_df['year'] = daily_df['date'].dt.year
        
        yearly = daily_df.groupby('year').agg({
            'net_pnl': 'sum',
            'num_trades': 'sum'
        }).reset_index()
        
        yearly.columns = ['Year', 'P&L', 'Trades']
        return yearly
