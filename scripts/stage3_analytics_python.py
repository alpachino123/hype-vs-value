import psycopg2
import pandas as pd
import sys
import time
from tqdm import tqdm
from db_manager import get_db_connection, upsert_market_analysis
import warnings

warnings.filterwarnings('ignore', category=UserWarning)

def get_golden_tickers():
    """Get list of symbols that have both fundamental and price data."""
    conn = get_db_connection()
    try:
        df = pd.read_sql("""
            SELECT DISTINCT p.symbol 
            FROM daily_prices p
            INNER JOIN fundamentals f ON p.symbol = f.symbol
            ORDER BY p.symbol
        """, conn)
        return df['symbol'].tolist()
    finally:
        conn.close()

def get_already_processed():
    """Return tickers already in market_analysis so we skip them (resume support)."""
    conn = get_db_connection()
    try:
        df = pd.read_sql("SELECT DISTINCT symbol FROM market_analysis", conn)
        return set(df['symbol'].tolist())
    finally:
        conn.close()

def process_ticker(symbol):
    """
    Process a single ticker entirely in Python/Pandas.
    Returns number of rows written, or 0 if skipped/failed.
    """
    conn = get_db_connection()
    try:
        # --- 1. Fundamentals ---
        fund_df = pd.read_sql(
            "SELECT report_date, eps FROM fundamentals WHERE symbol = %s AND eps IS NOT NULL ORDER BY report_date ASC",
            conn, params=(symbol,)
        )
        if len(fund_df) < 4:
            return 0

        fund_df['ttm_eps'] = fund_df['eps'].rolling(window=4).sum()
        fund_df = fund_df.dropna(subset=['ttm_eps'])
        fund_df = fund_df[fund_df['ttm_eps'] > 0].copy()
        if fund_df.empty:
            return 0

        # --- 2. Daily Prices ---
        price_df = pd.read_sql(
            "SELECT price_date, close_price FROM daily_prices WHERE symbol = %s AND close_price > 0 ORDER BY price_date ASC",
            conn, params=(symbol,)
        )
        if price_df.empty:
            return 0

        # --- 3. Forward-fill TTM EPS onto each price day (merge_asof = fast) ---
        price_df['price_date'] = pd.to_datetime(price_df['price_date'])
        fund_df['report_date'] = pd.to_datetime(fund_df['report_date'])

        merged = pd.merge_asof(
            price_df,
            fund_df[['report_date', 'ttm_eps']],
            left_on='price_date',
            right_on='report_date',
            direction='backward'
        )
        merged = merged.dropna(subset=['ttm_eps'])
        if merged.empty:
            return 0

        # --- 4. Daily P/E and Rolling 5-Year Average ---
        merged['daily_pe'] = merged['close_price'] / merged['ttm_eps']

        # Cap P/E at 150 ONLY for the rolling average baseline.
        # Near-zero EPS years produce P/E of 1000+ which would poison the
        # 5yr average and make Fair Value collapse to ~$0 for all future years.
        # The real (uncapped) daily_pe is still used for the hype_score comparison.
        PE_CAP = 150
        merged['daily_pe_for_avg'] = merged['daily_pe'].clip(upper=PE_CAP)
        # Also treat negative daily P/E as NaN (negative EPS slips through occasionally)
        merged['daily_pe_for_avg'] = merged['daily_pe_for_avg'].where(merged['daily_pe_for_avg'] > 0)

        # min_periods=750 ~ 3 years; shift(1) prevents using today in its own baseline
        merged['avg_5yr_pe'] = (
            merged['daily_pe_for_avg']
            .rolling(window=1260, min_periods=750)
            .mean()
            .shift(1)
        )
        merged = merged.dropna(subset=['avg_5yr_pe'])
        merged = merged[merged['avg_5yr_pe'] > 0]
        if merged.empty:
            return 0

        # --- 5. Fair Value & Hype Score ---
        merged['fair_value']          = merged['avg_5yr_pe'] * merged['ttm_eps']
        merged['hype_score']          = merged['daily_pe']   / merged['avg_5yr_pe']
        merged['price_to_fair_ratio'] = merged['close_price'] / merged['fair_value']

        # --- 6. Batch upsert ---
        records = [
            (
                symbol,
                row['price_date'].date(),
                float(row['fair_value']),
                float(row['hype_score']),
                float(row['price_to_fair_ratio'])
            )
            for _, row in merged.iterrows()
        ]
        if records:
            upsert_market_analysis(records)
        return len(records)

    except Exception as e:
        print(f"\n  ERROR on {symbol}: {e}", flush=True)
        return 0
    finally:
        conn.close()

def main():
    print("Stage 3 Analytics — Python per-ticker engine", flush=True)
    print("=" * 55, flush=True)

    tickers = get_golden_tickers()
    done    = get_already_processed()

    remaining = [t for t in tickers if t not in done]
    print(f"Total golden tickers:  {len(tickers)}", flush=True)
    print(f"Already processed:     {len(done)}", flush=True)
    print(f"Remaining to process:  {len(remaining)}", flush=True)
    print("=" * 55, flush=True)

    if not remaining:
        print("Nothing left to process. Stage 3 is complete!", flush=True)
        return

    total_rows  = 0
    start_time  = time.time()

    for i, symbol in enumerate(tqdm(remaining, desc="Analytics Progress", unit="ticker"), 1):
        t0      = time.time()
        rows    = process_ticker(symbol)
        elapsed = time.time() - t0
        total_rows += rows

        # Per-ticker log so you can see live progress
        elapsed_total = time.time() - start_time
        avg_sec = elapsed_total / i
        eta_sec = avg_sec * (len(remaining) - i)
        eta_h, eta_m = divmod(int(eta_sec), 3600)[0], divmod(int(eta_sec), 60)[0] % 60
        eta_s = int(eta_sec) % 60

        tqdm.write(
            f"  [{i}/{len(remaining)}] {symbol:<8} "
            f"| rows: {rows:>6,} "
            f"| ticker_time: {elapsed:.2f}s "
            f"| ETA: {eta_h}h {eta_m}m {eta_s}s",
        )
        sys.stdout.flush()

    elapsed_total = time.time() - start_time
    print(f"\n{'=' * 55}", flush=True)
    print(f"Stage 3 COMPLETE!", flush=True)
    print(f"  Total rows inserted:  {total_rows:,}", flush=True)
    print(f"  Total time:           {elapsed_total/60:.1f} minutes", flush=True)

if __name__ == "__main__":
    main()
