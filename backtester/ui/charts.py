"""
Plotly Charts for Backtester
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List


def create_equity_chart(equity_curve: List[float], 
                       daily_df: pd.DataFrame = None) -> go.Figure:
    """
    Create equity curve chart
    
    Args:
        equity_curve: List of cumulative P&L values
        daily_df: Daily results dataframe with dates
    """
    fig = go.Figure()
    
    if daily_df is not None and not daily_df.empty:
        x_axis = pd.to_datetime(daily_df['date'])
    else:
        x_axis = list(range(len(equity_curve)))
    
    # Equity line
    fig.add_trace(go.Scatter(
        x=x_axis,
        y=equity_curve,
        mode='lines',
        name='Equity',
        line=dict(color='#00C853', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 200, 83, 0.1)'
    ))
    
    # Zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_layout(
        title='Equity Curve',
        xaxis_title='Date' if daily_df is not None else 'Trade #',
        yaxis_title='Cumulative P&L (₹)',
        template='plotly_dark',
        hovermode='x unified',
        height=400
    )
    
    return fig


def create_drawdown_chart(equity_curve: List[float],
                         daily_df: pd.DataFrame = None) -> go.Figure:
    """Create drawdown chart"""
    equity_arr = np.array(equity_curve)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = peak - equity_arr
    drawdown_pct = np.where(peak > 0, drawdown / peak * 100, 0)
    
    if daily_df is not None and not daily_df.empty:
        x_axis = pd.to_datetime(daily_df['date'])
    else:
        x_axis = list(range(len(equity_curve)))
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=x_axis,
        y=-drawdown,  # Negative to show as underwater
        mode='lines',
        name='Drawdown',
        line=dict(color='#FF5252', width=1),
        fill='tozeroy',
        fillcolor='rgba(255, 82, 82, 0.3)'
    ))
    
    fig.update_layout(
        title='Drawdown',
        xaxis_title='Date' if daily_df is not None else 'Trade #',
        yaxis_title='Drawdown (₹)',
        template='plotly_dark',
        hovermode='x unified',
        height=300
    )
    
    return fig


def create_monthly_heatmap(daily_df: pd.DataFrame) -> go.Figure:
    """Create monthly P&L heatmap"""
    if daily_df.empty:
        return go.Figure()
    
    df = daily_df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    
    pivot = df.pivot_table(
        values='net_pnl', 
        index='year', 
        columns='month', 
        aggfunc='sum'
    ).fillna(0)
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[month_names[i-1] for i in pivot.columns],
        y=pivot.index.astype(str),
        colorscale='RdYlGn',
        zmid=0,
        text=np.round(pivot.values, 0),
        texttemplate='₹%{text:.0f}',
        textfont=dict(size=10),
        hovertemplate='%{y} %{x}: ₹%{z:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        title='Monthly P&L Heatmap',
        template='plotly_dark',
        height=300
    )
    
    return fig


def create_trade_distribution(trades_df: pd.DataFrame) -> go.Figure:
    """Create trade P&L distribution histogram"""
    if trades_df.empty:
        return go.Figure()
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=trades_df['net_pnl'],
        nbinsx=50,
        marker_color='#2196F3',
        opacity=0.7
    ))
    
    # Add vertical line at zero
    fig.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
    
    # Add mean line
    mean_pnl = trades_df['net_pnl'].mean()
    fig.add_vline(x=mean_pnl, line_dash="dot", line_color="#00C853",
                  annotation_text=f"Avg: ₹{mean_pnl:.0f}")
    
    fig.update_layout(
        title='Trade P&L Distribution',
        xaxis_title='P&L (₹)',
        yaxis_title='Frequency',
        template='plotly_dark',
        height=300
    )
    
    return fig


def create_monte_carlo_chart(mc_data: dict) -> go.Figure:
    """Create Monte Carlo distribution chart"""
    if not mc_data:
        return go.Figure()
    
    fig = make_subplots(rows=1, cols=2, 
                       subplot_titles=('Final P&L Distribution', 'Max Drawdown Distribution'))
    
    if 'final_pnls' in mc_data:
        fig.add_trace(
            go.Histogram(x=mc_data['final_pnls'], nbinsx=100, 
                        marker_color='#4CAF50', opacity=0.7),
            row=1, col=1
        )
    
    if 'max_drawdowns' in mc_data:
        fig.add_trace(
            go.Histogram(x=mc_data['max_drawdowns'], nbinsx=100,
                        marker_color='#FF5252', opacity=0.7),
            row=1, col=2
        )
    
    fig.update_layout(
        template='plotly_dark',
        height=300,
        showlegend=False
    )
    
    return fig
