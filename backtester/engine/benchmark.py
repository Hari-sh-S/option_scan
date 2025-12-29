"""
Benchmark Script - Compare Original vs Optimized Backtest Engine

This script runs the same backtest on both engines and compares:
1. Correctness: P&L, trades, and metrics match
2. Performance: Execution time comparison
"""

import time
import sys
from pathlib import Path

# Add backtester to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.loader import DataLoader
from engine.leg import LegConfig, LegAction
from engine.strategy import Strategy, StrategyConfig, StrategyMode
from engine.backtest import BacktestEngine
from engine.backtest_optimized import OptimizedBacktestEngine


def create_test_strategy() -> Strategy:
    """Create a simple test strategy: Sell ATM CE"""
    config = StrategyConfig(
        name="Benchmark Strategy",
        mode=StrategyMode.INTRADAY,
        entry_time="09:20",
        exit_time="15:15",
        no_entry_after="14:30",
        max_loss=5000,  # Strategy-level SL
        max_profit=3000  # Strategy-level Target
    )
    
    strategy = Strategy(config=config)
    
    # Add single leg: Sell ATM CE with SL and target
    leg_config = LegConfig(
        leg_id=1,
        strike="ATM",
        option_type="CE",
        expiry_type="WEEK",
        action=LegAction.SELL,
        lots=1,
        sl_points=30,
        target_points=20
    )
    strategy.add_leg(leg_config)
    
    return strategy


def compare_results(original_result, optimized_result, tolerance=0.01) -> bool:
    """
    Compare backtest results for correctness
    
    Args:
        original_result: Result from original engine
        optimized_result: Result from optimized engine
        tolerance: Percentage tolerance for floating point comparison
    
    Returns:
        True if results match within tolerance
    """
    all_match = True
    
    print("\n" + "="*60)
    print("CORRECTNESS COMPARISON")
    print("="*60)
    
    # Compare summary metrics
    metrics = [
        ("Total P&L", original_result.total_pnl, optimized_result.total_pnl),
        ("Total Brokerage", original_result.total_brokerage, optimized_result.total_brokerage),
        ("Net P&L", original_result.net_pnl, optimized_result.net_pnl),
        ("Num Trades", original_result.num_trades, optimized_result.num_trades),
        ("Num Days", original_result.num_days, optimized_result.num_days),
    ]
    
    for name, orig, opt in metrics:
        if isinstance(orig, int):
            match = orig == opt
        else:
            # Float comparison with tolerance
            if orig == 0 and opt == 0:
                match = True
            elif orig == 0:
                match = abs(opt) < 0.01
            else:
                match = abs((orig - opt) / orig) <= tolerance
        
        status = "[OK] MATCH" if match else "[FAIL] MISMATCH"
        print(f"{name:20s}: Original={orig:12.2f}, Optimized={opt:12.2f} [{status}]")
        if not match:
            all_match = False
    
    # Compare trade counts by exit reason
    print("\nTrade Exit Reasons:")
    orig_reasons = {}
    opt_reasons = {}
    
    for t in original_result.trades:
        orig_reasons[t.exit_reason] = orig_reasons.get(t.exit_reason, 0) + 1
    for t in optimized_result.trades:
        opt_reasons[t.exit_reason] = opt_reasons.get(t.exit_reason, 0) + 1
    
    all_reasons = set(orig_reasons.keys()) | set(opt_reasons.keys())
    for reason in sorted(all_reasons):
        orig_count = orig_reasons.get(reason, 0)
        opt_count = opt_reasons.get(reason, 0)
        match = orig_count == opt_count
        status = "[OK] MATCH" if match else "[FAIL] MISMATCH"
        print(f"  {reason:15s}: Original={orig_count:3d}, Optimized={opt_count:3d} [{status}]")
        if not match:
            all_match = False
    
    # Sample trade comparison (first 5 trades)
    print("\nSample Trade Comparison (first 5):")
    for i, (orig_t, opt_t) in enumerate(zip(original_result.trades[:5], optimized_result.trades[:5])):
        pnl_match = abs(orig_t.pnl - opt_t.pnl) < 1  # Within 1 rupee
        print(f"  Trade {i+1}: Orig P&L={orig_t.pnl:8.2f} ({orig_t.exit_reason:12s}), "
              f"Opt P&L={opt_t.pnl:8.2f} ({opt_t.exit_reason:12s}) "
              f"[{'OK' if pnl_match else 'FAIL'}]")
    
    return all_match


def run_benchmark():
    """Run the benchmark comparison with multiple iterations"""
    print("="*60)
    print("BACKTEST ENGINE BENCHMARK")
    print("="*60)
    
    # Initialize loader
    loader = DataLoader()
    
    # Check data availability
    try:
        min_date, max_date = loader.get_date_range("WEEK")
        print(f"\nData available from {min_date} to {max_date}")
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    # Use a 30-day period for benchmarking
    trading_days = loader.get_trading_days("WEEK")
    if len(trading_days) < 30:
        print(f"Not enough trading days for benchmark (need 30, have {len(trading_days)})")
        return
    
    # Use first 60 days for a good sample
    start_date = trading_days[0]
    end_date = trading_days[min(59, len(trading_days)-1)]
    
    print(f"Benchmark period: {start_date} to {end_date}")
    print(f"Trading days: {len([d for d in trading_days if start_date <= d <= end_date])}")
    
    # Run multiple iterations
    num_iterations = 3
    original_times = []
    optimized_times = []
    all_match = True
    
    for iteration in range(num_iterations):
        print(f"\n--- Iteration {iteration + 1}/{num_iterations} ---")
        
        # Create engines
        original_engine = BacktestEngine(loader)
        optimized_engine = OptimizedBacktestEngine(loader)
        
        # Run original engine
        print("Running ORIGINAL engine...")
        strategy1 = create_test_strategy()
        
        start_time = time.perf_counter()
        original_result = original_engine.run(
            strategy1, start_date, end_date,
            slippage_pct=0.05,
            brokerage_per_lot=20
        )
        orig_time = time.perf_counter() - start_time
        original_times.append(orig_time)
        print(f"  Original: {orig_time:.3f}s")
        
        # Run optimized engine
        print("Running OPTIMIZED engine...")
        strategy2 = create_test_strategy()
        
        start_time = time.perf_counter()
        optimized_result = optimized_engine.run(
            strategy2, start_date, end_date,
            slippage_pct=0.05,
            brokerage_per_lot=20
        )
        opt_time = time.perf_counter() - start_time
        optimized_times.append(opt_time)
        print(f"  Optimized: {opt_time:.3f}s")
        
        # Compare results on first iteration
        if iteration == 0:
            all_match = compare_results(original_result, optimized_result)
    
    # Calculate averages
    avg_original = sum(original_times) / len(original_times)
    avg_optimized = sum(optimized_times) / len(optimized_times)
    
    # Performance summary
    print("\n" + "="*60)
    print("PERFORMANCE SUMMARY (averaged over {} iterations)".format(num_iterations))
    print("="*60)
    print(f"Original engine:  {avg_original:.3f} seconds (min: {min(original_times):.3f}, max: {max(original_times):.3f})")
    print(f"Optimized engine: {avg_optimized:.3f} seconds (min: {min(optimized_times):.3f}, max: {max(optimized_times):.3f})")
    
    if avg_optimized > 0:
        speedup = avg_original / avg_optimized
        print(f"Speedup factor:   {speedup:.2f}x")
        
        if speedup > 1:
            print(f"Performance gain: {(speedup - 1) * 100:.1f}% faster")
        else:
            print(f"Performance loss: {(1 - speedup) * 100:.1f}% slower")
    
    # Final verdict
    print("\n" + "="*60)
    if all_match and avg_optimized < avg_original:
        print("[PASS] BENCHMARK PASSED")
        print("  - All results match within tolerance")
        print("  - Optimized engine is faster")
    elif all_match:
        print("[WARN] BENCHMARK PARTIAL PASS")
        print("  - All results match within tolerance")
        print("  - But optimized engine is NOT faster (needs optimization)")
    else:
        print("[FAIL] BENCHMARK FAILED")
        print("  - Results do not match - correctness issue!")
    print("="*60)
    
    return all_match


if __name__ == "__main__":
    run_benchmark()
