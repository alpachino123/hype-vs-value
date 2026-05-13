import pandas as pd
import yfinance as yf
from edgar import Company, set_identity
import config
import os
from datetime import datetime, timedelta
import numpy as np
import time  # CRITICAL: needed for retry sleep logic

# Set EDGAR Identity
try:
    set_identity(config.EDGAR_IDENTITY)
except Exception as e:
    print(f"Warning: Failed to set EDGAR identity: {e}")

def fetch_all_unique_tickers(csv_path):
    """
    Parses the historical S&P 500 CSV to extract ALL unique tickers that satisfy
    the user's 'Survivorship Bias' requirement.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    print(f"Reading historical S&P 500 data from: {csv_path}")
    df = pd.read_csv(csv_path)
    
    unique_tickers = set()
    
    # Iterate over the 'tickers' column which contains comma-separated lists
    for ticker_list in df['tickers'].dropna():
        # Split by comma, strip whitespace
        tickers = [t.strip() for t in ticker_list.split(',')]
        unique_tickers.update(tickers)
        
    print(f"Found {len(unique_tickers)} unique historical tickers.")
    return sorted(list(unique_tickers))

import requests

# --- Tiingo round-robin state ---
_tiingo_call_count = 0          # increments each successful/attempted call
_tiingo_exhausted_keys = set()  # indices of keys that hit their daily limit
_tiingo_keys_exhausted = False  # True when ALL keys are exhausted

# Rate limit config:
# 50-100 req/hour per key; with N keys in round-robin each key gets
# a gap of (N × INTER_REQUEST_DELAY) seconds between uses.
# 5 keys × 15s = 75s per key → ~48 req/hour per key (safe)
TIINGO_INTER_REQUEST_DELAY = 15  # seconds between each API call

def _pick_tiingo_key():
    """
    Returns (index, key) for the next available key using round-robin.
    Skips keys already marked as daily-exhausted.
    Returns (None, None) if all keys are exhausted.
    """
    n = len(config.TIINGO_API_KEYS)
    for offset in range(n):
        idx = (_tiingo_call_count + offset) % n
        if idx not in _tiingo_exhausted_keys:
            return idx, config.TIINGO_API_KEYS[idx]
    return None, None  # all exhausted

def fetch_price_history(symbol):
    """
    Fetches UNADJUSTED price history from Tiingo REST API.
    - Round-robin key cycling across all configured keys
    - 15-second inter-request delay to stay under hourly limits
    - On daily-limit (429): marks key exhausted, retries with next key
    - Returns a DataFrame or None on failure
    """
    global _tiingo_call_count, _tiingo_keys_exhausted

    if _tiingo_keys_exhausted:
        return None

    idx, key = _pick_tiingo_key()
    if key is None:
        _tiingo_keys_exhausted = True
        return None

    url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices"
    params = {
        "startDate": "1990-01-01",
        "token": key,
        "columns": "date,open,high,low,close,volume",
    }
    headers = {"Content-Type": "application/json"}

    while True:
        try:
            # Enforce rate limit delay before every call
            time.sleep(TIINGO_INTER_REQUEST_DELAY)

            resp = requests.get(url, params=params, headers=headers, timeout=30)
            _tiingo_call_count += 1

            # --- Daily limit hit on this key ---
            if resp.status_code == 429 or (
                resp.status_code == 400 and "limit" in resp.text.lower()
            ):
                print(f"  Tiingo daily limit hit on key #{idx + 1}. Marking exhausted.")
                _tiingo_exhausted_keys.add(idx)

                # Try the next available key
                idx, key = _pick_tiingo_key()
                if key is None:
                    print("  All Tiingo API keys exhausted.")
                    _tiingo_keys_exhausted = True
                    return None
                print(f"  Switched to key #{idx + 1}")
                params["token"] = key
                continue  # retry with new key

            # Ticker not found / delisted
            if resp.status_code == 404:
                return None

            if resp.status_code != 200:
                print(f"  Tiingo error for {symbol}: HTTP {resp.status_code} - {resp.text[:200]}")
                return None

            data = resp.json()
            if not data:
                return None

            df = pd.DataFrame(data)
            df.rename(columns={
                "date":  "price_date",
                "open":  "open_price",
                "high":  "high_price",
                "low":   "low_price",
                "close": "close_price",
            }, inplace=True)
            df["price_date"] = pd.to_datetime(df["price_date"]).dt.date
            df["adj_close_price"] = df["close_price"]
            df["symbol"] = symbol

            keep = ["price_date", "open_price", "high_price", "low_price",
                    "close_price", "adj_close_price", "volume", "symbol"]
            return df[keep]

        except requests.exceptions.ConnectionError as e:
            print(f"  Network error for {symbol}: {e}")
            return None
        except Exception as e:
            print(f"  Unexpected error fetching prices for {symbol}: {e}")
            return None


def _fetch_edgar_eps_for_cik(cik_or_symbol):
    """
    Helper to fetch raw facts for a single CIK/Symbol.
    """
    try:
        company = Company(cik_or_symbol)
        facts = company.get_facts()
        if not facts:
            return pd.DataFrame()
            
        df = facts.to_dataframe()
        
        # Filter for EPS using robust column check from POC
        cols = df.columns
        # Identify the column containing the XBRL tag (fact, tag, or concept)
        fact_col = 'fact' if 'fact' in cols else 'tag' if 'tag' in cols else 'concept'
        
        # 'val' is usually the value column, sometimes 'value'
        # val_col = 'val' if 'val' in cols else 'value' (used later in processing)
        
        # Full tag name is standard
        eps_tag = 'us-gaap:EarningsPerShareDiluted'
        
        if fact_col in df.columns:
            eps_df = df[df[fact_col] == eps_tag].copy()
        else:
            # Fallback if we can't find the column
            print(f"Warning: Could not identify tag column in {cols}")
            return pd.DataFrame()
        
        if eps_df.empty:
            return pd.DataFrame()
            
        return eps_df
    except Exception as e:
        # Don't crash on individual ticker failure
        # print(f"  Debug: Failed to fetch for {cik_or_symbol}: {e}") 
        return pd.DataFrame()

def process_edgar_data(raw_df):
    """
    Refines raw EDGAR data using the Duration-Based Logic:
    1. Calculate duration (days).
    2. Classify (Q, FY, YTD_Q3).
    3. Derive Q4.
    """
    if raw_df.empty:
        return pd.DataFrame()
        
    df = raw_df.copy()
    
    # Ensure date columns
    if 'period_start' not in df.columns or 'period_end' not in df.columns:
        # Some older data might not have period_start, try to infer or skip
        if 'end' in df.columns:
             df.rename(columns={'end': 'period_end'}, inplace=True)
        else:
            return pd.DataFrame()

    df['start_date'] = pd.to_datetime(df['period_start'], errors='coerce')
    df['end_date'] = pd.to_datetime(df['period_end'], errors='coerce')
    df = df.dropna(subset=['start_date', 'end_date'])
    
    # Calculate duration
    df['days'] = (df['end_date'] - df['start_date']).dt.days
    
    # --- Classification Logic ---
    def classify_period(days):
        if 80 <= days <= 105: return 'Q'       # ~90 days
        if 350 <= days <= 380: return 'FY'     # ~365 days
        if 260 <= days <= 290: return 'YTD_Q3' # ~270 days (9 months)
        return 'OTHER'

    df['period_type'] = df['days'].apply(classify_period)
    
    # Keep only relevant columns
    cols = ['end_date', 'val', 'period_type', 'fy', 'fp', 'form']
    # 'val' is usually the value column in edgartools dataframe, sometimes 'value'
    if 'val' not in df.columns and 'value' in df.columns:
        df.rename(columns={'value': 'val'}, inplace=True)
        
    # Standardize helpful columns
    if 'fy' not in df.columns: df['fy'] = df['end_date'].dt.year # Fallback
    if 'fp' not in df.columns: df['fp'] = 'NA'
    
    # Filter for useful rows
    useful_df = df[df['period_type'].isin(['Q', 'FY', 'YTD_Q3'])].copy()
    
    # Deduplicate: if multiple reports for same end_date/period_type, take latest filed?
    # For now, just take the first one or max value (if restatements)
    # Simple approach: drop duplicates
    useful_df = useful_df.sort_values('end_date').drop_duplicates(subset=['end_date', 'period_type'], keep='last')
    
    return useful_df

def derive_quarterly_eps(processed_df):
    """
    Derives discrete Q4 values from FY and YTD_Q3.
    Returns a clean DataFrame with [date, eps, is_derived]
    """
    df = processed_df.copy()
    
    results = []
    
    # Group by Fiscal Year (approximate based on end_date year for calculation alignment)
    # Note: Fiscal Year 'fy' column in EDGAR is robust, let's use it if available, else derive from date
    if 'fy' in df.columns:
        df['year_group'] = df['fy']
    else:
        df['year_group'] = df['end_date'].dt.year

    for year, group in df.groupby('year_group'):
        # 1. Get existing Quarters (Q1, Q2, Q3, maybe Q4 if reported explicitly)
        quarters = group[group['period_type'] == 'Q']
        for _, row in quarters.iterrows():
            results.append({
                'report_date': row['end_date'],
                'eps': row['val'],
                'type': 'Reported_Q',
                'period': row['fp'] if row['fp'] != 'NA' else 'Q?'
            })
            
        # 2. Try to derive Q4
        fy_row = group[group['period_type'] == 'FY']
        ytd_q3_row = group[group['period_type'] == 'YTD_Q3']
        
        if not fy_row.empty and not ytd_q3_row.empty:
            # We have both!
            fy_val = fy_row.iloc[0]['val']
            ytd_val = ytd_q3_row.iloc[0]['val']
            
            q4_val = fy_val - ytd_val
            q4_date = fy_row.iloc[0]['end_date'] # Q4 ends same day as FY
            
            # Check if we already have this Q4 reported explicitly (rare but possible)
            if not any(r['report_date'] == q4_date for r in results):
                results.append({
                    'report_date': q4_date,
                    'eps': q4_val,
                    'type': 'Derived_Q4',
                    'period': 'Q4'
                })
    
    return pd.DataFrame(results)

def fetch_historical_eps(symbol):
    """
    Main function to get EPS history.
    Handles Multi-CIK logic.
    """
    ciks_to_check = [symbol]
    
    # Check config for special mapping
    if symbol in config.SPECIAL_TICKER_CIKS:
        ciks_to_check = config.SPECIAL_TICKER_CIKS[symbol]
        print(f"  Using Multi-CIK mapping for {symbol}: {ciks_to_check}")
    
    all_raw_data = []
    
    for cik in ciks_to_check:
        print(f"  Fetching EDGAR data for {cik}...")
        raw_df = _fetch_edgar_eps_for_cik(cik)
        if not raw_df.empty:
            all_raw_data.append(raw_df)
            
    if not all_raw_data:
        print(f"  No EPS data found for {symbol}")
        return None
        
    # Merge all histories (e.g. Google Inc + Alphabet)
    combined_df = pd.concat(all_raw_data)
    
    # Process
    processed_df = process_edgar_data(combined_df)
    final_eps = derive_quarterly_eps(processed_df)
    
    if final_eps.empty:
        return None
        
    final_eps['symbol'] = symbol
    return final_eps

if __name__ == "__main__":
    # Quick Test
    print("Testing fetch strategy...")
    eps = fetch_historical_eps('GOOG')
    if eps is not None:
        print(eps.sort_values('report_date').tail(10))
    else:
        print("Test failed.")
