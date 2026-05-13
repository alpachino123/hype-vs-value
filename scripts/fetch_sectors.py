import yfinance as yf
import psycopg2
from tqdm import tqdm
import time
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='127.0.0.1', port=5432, database='market_research_db',
        user='postgres', password='2005'
    )

def fetch_and_update_sectors(limit=None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get tickers that don't have sector info yet
    cur.execute("SELECT symbol FROM companies WHERE sector = 'Unknown' OR sector IS NULL ORDER BY symbol")
    rows = cur.fetchall()
    
    symbols = [r[0] for r in rows]
    if limit:
        symbols = symbols[:limit]
        
    print(f"Found {len(symbols)} companies needing sector/industry data.")
    
    success = 0
    errors = 0
    
    for symbol in tqdm(symbols, desc="Fetching Sectors"):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            sector = info.get('sector', 'Unknown')
            industry = info.get('industry', 'Unknown')
            name = info.get('shortName', info.get('longName', 'Unknown'))
            
            # If yfinance doesn't know the sector, it often means the ticker is 
            # fully delisted and purged from their active metadata DB.
            
            cur.execute("""
                UPDATE companies 
                SET sector = %s, industry = %s, company_name = %s
                WHERE symbol = %s
            """, (sector, industry, name, symbol))
            
            conn.commit()
            success += 1
            
            # yfinance rate limits aren't strict for .info, but let's be safe
            time.sleep(0.5)
            
        except Exception as e:
            # print(f"\nError fetching {symbol}: {e}")
            errors += 1
            time.sleep(1) # Extra delay on error
            
    print(f"\nUpdate complete. Successfully fetched: {success}, Errors/Not Found: {errors}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, help='Limit number of tickers to process')
    args = parser.parse_args()
    
    fetch_and_update_sectors(limit=args.limit)
