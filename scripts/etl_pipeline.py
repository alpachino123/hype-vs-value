import pandas as pd
import data_fetcher
import db_manager
import analytics
import config
from tqdm import tqdm
import time
import os
import sp500_parser

# Configuration for Batching
CSV_PATH = r"C:\Users\Yosi\Downloads\S&P 500 Historical Components & Changes(01-17-2026).csv"

# Execution Flags (Staged Approach)
FETCH_FUNDAMENTALS = False  # Stage 1 COMPLETE
FETCH_PRICES = True          # Stage 2 ACTIVE
RUN_ANALYTICS = False        # Stage 3

def run_pipeline():
    print("Starting Hype vs Value ETL Pipeline...")
    
    # 1. Fetch S&P 500 List
    print("\n[Phase 1] Extracting Unique Tickers from History CSV...")
    try:
        tickers = data_fetcher.fetch_all_unique_tickers(CSV_PATH)
        # Store companies in DB (basic insert for now, enriching later if needed)
        company_records = [(t, f"Company {t}", "Unknown", "Unknown", "Unknown") for t in tickers]
        db_manager.upsert_companies(company_records)
        
        # Parse S&P 500 membership dates
        print("Parsing S&P 500 membership dates...")
        sp500_membership = sp500_parser.parse_sp500_membership(CSV_PATH)
        
        # FULL RUN: Process all tickers
        print(f"DEBUG: Processing all {len(tickers)} tickers.")
    except Exception as e:
        print(f"CRITICAL ERROR in Phase 1: {e}")
        return

    # 2. Process Data Per Ticker
    print(f"\n[Phase 2] Fetching & Processing Data for {len(tickers)} tickers...")
    
    # --- Resume support: skip tickers already in the DB ---
    if FETCH_PRICES:
        already_done = db_manager.get_symbols_with_prices()
        before = len(tickers)
        tickers = [t for t in tickers if t not in already_done]
        print(f"  Skipping {before - len(tickers)} tickers already in daily_prices.")
        print(f"  Remaining to fetch: {len(tickers)}")

    success_count = 0
    skipped_count = 0   # no data from API (delisted, not found)
    error_count = 0
    keys_exhausted = False
    
    for symbol in tqdm(tickers):
        if keys_exhausted:
            break
        try:
            # A. Fetch Fundamentals (Stage 1)
            eps_df = None
            if FETCH_FUNDAMENTALS:
                # Fundamentals (EDGAR)
                eps_df = data_fetcher.fetch_historical_eps(symbol)
                if eps_df is not None and not eps_df.empty:
                    # DB Insert Fundamentals
                    fund_records = []
                    for _, row in eps_df.iterrows():
                        fund_records.append((
                            symbol, 
                            row['report_date'], 
                            row['eps'], 
                            None, None, None, None 
                        ))
                    db_manager.upsert_fundamentals(fund_records)
            
            # B. Fetch Prices (Stage 2)
            price_df = None
            if FETCH_PRICES:
                price_df = data_fetcher.fetch_price_history(symbol)
                
                # Detect key exhaustion — stop processing rather than silently skipping
                if data_fetcher._tiingo_keys_exhausted:
                    print("\nTiingo keys exhausted — stopping pipeline to avoid silent skips.")
                    keys_exhausted = True
                    break
                
                if price_df is not None and not price_df.empty:
                    # DB Insert Prices with S&P membership flag
                    price_records = []
                    for _, row in price_df.iterrows():
                        in_sp500 = sp500_parser.is_in_sp500(
                            symbol,
                            pd.to_datetime(row['price_date']),
                            sp500_membership
                        )
                        price_records.append((
                            symbol,
                            row['price_date'],
                            row['open_price'],
                            row['high_price'],
                            row['low_price'],
                            row['close_price'],
                            row['adj_close_price'],
                            row['volume'],
                            in_sp500
                        ))
                    db_manager.upsert_daily_prices(price_records)
                    success_count += 1
                else:
                    skipped_count += 1  # delisted / no data
                    continue  # don't double-count below
            
            # C. Analyze (Stage 3)
            if RUN_ANALYTICS and price_df is not None and eps_df is not None:
                metrics_df = analytics.analyze_single_ticker(symbol, price_df, eps_df)
                
                # DB Insert Analysis
                if metrics_df is not None and not metrics_df.empty:
                    analysis_records = []
                    for _, row in metrics_df.iterrows():
                        fv = row['fair_value'] if pd.notnull(row['fair_value']) else None
                        hs = row['hype_score'] if pd.notnull(row['hype_score']) else None
                        pfr = None 
                        
                        analysis_records.append((
                            symbol,
                            row['price_date'],
                            fv,
                            hs,
                            pfr
                        ))
                    db_manager.upsert_market_analysis(analysis_records)
            
            if not FETCH_PRICES:
                success_count += 1  # fundamentals-only mode
                time.sleep(0.5)   # light delay for EDGAR calls
            # Note: FETCH_PRICES delay is handled inside data_fetcher.fetch_price_history()

            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            error_count += 1
            
    print(f"\nPipeline Complete.")
    print(f"  Inserted (success): {success_count}")
    print(f"  No data (delisted): {skipped_count}")
    print(f"  Errors:             {error_count}")
    if keys_exhausted:
        print("  STOPPED EARLY: All Tiingo API keys exhausted. Re-run tomorrow or add more keys.")

if __name__ == "__main__":
    run_pipeline()
