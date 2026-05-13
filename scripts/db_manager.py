import psycopg2
from psycopg2.extras import execute_batch
import config

def get_db_connection():
    """Establish and return a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD
    )
    return conn

def upsert_companies(companies_data):
    """
    Batch insert/update companies.
    expected data: list of tuples (symbol, company_name, sector, industry, exchange)
    """
    sql = """
    INSERT INTO companies (symbol, company_name, sector, industry, exchange)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (symbol) DO UPDATE SET
        company_name = EXCLUDED.company_name,
        sector = EXCLUDED.sector,
        industry = EXCLUDED.industry,
        exchange = EXCLUDED.exchange;
    """
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            execute_batch(cur, sql, companies_data)
        conn.commit()
        print(f"Upserted {len(companies_data)} companies.")
    except Exception as e:
        print(f"Error upserting companies: {e}")
        conn.rollback()
    finally:
        conn.close()

def upsert_daily_prices(prices_data):
    """
    Batch insert/update daily prices.
    expected data: list of tuples (symbol, price_date, open, high, low, close, adj_close, volume, in_sp500)
    """
    sql = """
    INSERT INTO daily_prices (symbol, price_date, open_price, high_price, low_price, close_price, adj_close_price, volume, in_sp500)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (symbol, price_date) DO NOTHING;
    """
    # NOTE: utilizing 'DO NOTHING' for faster history loads unless we really need to update old candles
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            execute_batch(cur, sql, prices_data)
        conn.commit()
        print(f"Upserted {len(prices_data)} price records.")
    except Exception as e:
        print(f"Error upserting prices: {e}")
        conn.rollback()
    finally:
        conn.close()

def upsert_fundamentals(fundamentals_data):
    """
    Batch insert/update fundamentals (EPS).
    expected data: list of tuples (symbol, report_date, eps, revenue, net_income, total_assets, total_liabilities)
    """
    # Note: We might only have symbol, report_date, eps for now.
    # The query handles NULLs for other columns if they are not provided in the tuple,
    # BUT the tuple matches the VALUES placeholders. 
    # Current plan only focused on EPS, so let's make sure our tuple structure matches using default Nones.
    
    sql = """
    INSERT INTO fundamentals (symbol, report_date, eps, revenue, net_income, total_assets, total_liabilities)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (symbol, report_date) DO UPDATE SET
        eps = EXCLUDED.eps,
        revenue = COALESCE(EXCLUDED.revenue, fundamentals.revenue),
        net_income = COALESCE(EXCLUDED.net_income, fundamentals.net_income);
    """
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            execute_batch(cur, sql, fundamentals_data)
        conn.commit()
    except Exception as e:
        print(f"Error upserting fundamentals: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_existing_tickers():
    """Return a set of symbols already in the database."""
    conn = get_db_connection()
    symbols = set()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT symbol FROM companies")
            rows = cur.fetchall()
            symbols = {row[0] for row in rows}
    finally:
        conn.close()
    return symbols

def get_symbols_with_prices():
    """Returns a set of symbols that already have records in daily_prices."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT symbol FROM daily_prices")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

def upsert_market_analysis(analysis_data):
    """
    Batch insert/update market analysis.
    expected data: list of tuples (symbol, analysis_date, fair_value, hype_score, price_to_fair_ratio)
    """
    sql = """
    INSERT INTO market_analysis (symbol, analysis_date, fair_value, hype_score, price_to_fair_ratio)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (symbol, analysis_date) DO UPDATE SET
        fair_value = EXCLUDED.fair_value,
        hype_score = EXCLUDED.hype_score,
        price_to_fair_ratio = EXCLUDED.price_to_fair_ratio;
    """
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            execute_batch(cur, sql, analysis_data)
        conn.commit()
    except Exception as e:
        print(f"Error upserting market analysis: {e}")
        conn.rollback()
    finally:
        conn.close()
