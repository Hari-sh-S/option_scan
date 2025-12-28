# 📊 NIFTY Options Backtester

A **production-grade options backtesting engine** equivalent to AlgoTest, deployable as a Streamlit web app.

## ✨ Features

- **Multi-leg strategies** - Build complex strategies with multiple option legs
- **Flexible strikes** - ATM ± 10 strikes supported
- **Weekly & Monthly expiry** - Both expiry types available
- **Advanced exits** - SL, Target, Trailing SL (points or %)
- **Strategy-level risk** - Max Loss/Profit limits override leg-level
- **Candle-by-candle simulation** - Accurate OHLC-aware execution
- **Monte Carlo analysis** - 10,000+ simulations for risk metrics
- **Beautiful charts** - Equity curve, drawdown, monthly heatmap
- **Trade log export** - Download complete trade history as CSV

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
pip install streamlit plotly
```

### 2. Download Historical Data
```bash
# Configure your Dhan API credentials in .env
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token

# Run the downloader
python downloader.py
```

### 3. Run the Backtester
```bash
streamlit run backtester/app.py
```

Open **http://localhost:8501** in your browser.

## 📁 Project Structure

```
├── backtester/
│   ├── app.py              # Streamlit UI
│   ├── config.py           # Global settings
│   ├── data/
│   │   ├── loader.py       # Parquet reader with caching
│   │   └── resolver.py     # Strike → file mapping
│   ├── engine/
│   │   ├── leg.py          # Leg state machine
│   │   ├── strategy.py     # Multi-leg coordinator
│   │   └── backtest.py     # Execution engine
│   ├── metrics/
│   │   ├── calculator.py   # AlgoTest-matching metrics
│   │   └── monte_carlo.py  # Risk simulations
│   ├── risk/
│   │   ├── leg_risk.py     # SL/Target/Trailing
│   │   └── strategy_risk.py # Strategy-level controls
│   └── ui/
│       ├── charts.py       # Plotly visualizations
│       └── components.py   # Streamlit widgets
├── downloader.py           # Dhan API data fetcher
├── historical_data/        # Parquet data files
└── requirements.txt
```

## 📊 Metrics Calculated

| Metric | Description |
|--------|-------------|
| Win Rate | Percentage of winning trades |
| Max Drawdown | Largest peak-to-trough decline |
| Profit Factor | Gross profit / Gross loss |
| Expectancy | Expected value per trade |
| Reward/Risk | Avg win / Avg loss |
| Max Streak | Consecutive wins/losses |
| CAGR | Compound annual growth rate |

## 🎲 Monte Carlo Analysis

- 10,000+ trade simulations
- 95th percentile max drawdown
- Probability of ruin calculation
- CAGR distribution (median, 5th percentile)

## 📈 Supported Strategies

- **Short Straddle** - Sell ATM CE + Sell ATM PE
- **Short Strangle** - Sell OTM CE + Sell OTM PE
- **Iron Condor** - 4-leg spread
- **Any custom combination** of up to 10+ legs

## 🔧 Configuration

### Strategy Settings
- Entry/Exit time
- No entry after time
- Strategy mode (Intraday/BTST/Positional)

### Risk Management
- Per-leg SL/Target (points or %)
- Trailing stop loss
- Strategy-level max loss/profit
- Slippage and brokerage costs

## 📜 License

MIT License

## 🤝 Contributing

Pull requests welcome! For major changes, please open an issue first.
