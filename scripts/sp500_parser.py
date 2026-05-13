"""
S&P 500 Membership Parser
Parses the historical CSV to determine which dates each ticker was in the S&P 500
"""
import pandas as pd
from datetime import datetime
import config

def parse_sp500_membership(csv_path):
    """
    Parse CSV to create a lookup: {ticker: [(start_date, end_date), ...]}
    Returns dictionary mapping ticker symbols to list of membership periods
    """
    print("Parsing S&P 500 membership dates from CSV...")
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Dictionary to store membership periods
    # Format: {ticker: [(start_date, end_date), ...]}
    membership = {}
    
    # Track when each ticker was last seen
    last_seen = {}
    
    for idx, row in df.iterrows():
        date = row['date']
        tickers_today = [t.strip() for t in row['tickers'].split(',')]
        
        # Update last seen for current tickers
        for ticker in tickers_today:
            if ticker not in membership:
                membership[ticker] = []
            
            # If this is first time seeing ticker, start a new period
            if ticker not in last_seen:
                membership[ticker].append({'start': date, 'end': None})
            
            last_seen[ticker] = date
        
        # Check which tickers are no longer in the list (removed from S&P)
        all_tracked = set(last_seen.keys())
        current_tickers = set(tickers_today)
        removed = all_tracked - current_tickers
        
        for ticker in removed:
            # Close the current membership period
            if membership[ticker] and membership[ticker][-1]['end'] is None:
                membership[ticker][-1]['end'] = last_seen[ticker]
            del last_seen[ticker]
    
    # Close any open-ended periods (still in S&P as of last CSV date)
    for ticker in last_seen:
        if membership[ticker] and membership[ticker][-1]['end'] is None:
            membership[ticker][-1]['end'] = df['date'].max()
    
    print(f"Parsed membership for {len(membership)} unique tickers")
    return membership

def is_in_sp500(ticker, date, membership_dict):
    """
    Check if a ticker was in the S&P 500 on a specific date
    """
    if ticker not in membership_dict:
        return False
    
    for period in membership_dict[ticker]:
        if period['start'] <= date <= period['end']:
            return True
    
    return False

if __name__ == "__main__":
    # Test
    CSV_PATH = r"C:\Users\Yosi\Downloads\S&P 500 Historical Components & Changes(01-17-2026).csv"
    membership = parse_sp500_membership(CSV_PATH)
    
    # Sample test
    test_ticker = 'AAPL'
    if test_ticker in membership:
        print(f"\n{test_ticker} S&P 500 membership periods:")
        for period in membership[test_ticker]:
            print(f"  {period['start']} to {period['end']}")
