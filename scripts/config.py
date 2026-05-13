import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "market_research_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# EDGAR Configuration
EDGAR_IDENTITY = os.getenv("EDGAR_IDENTITY")

# Tiingo API Keys (multiple for rotation when daily limit hit)
TIINGO_API_KEYS = [
    os.getenv("TIINGO_API_KEY_1"),
    os.getenv("TIINGO_API_KEY_2"),
    os.getenv("TIINGO_API_KEY_3"),
    os.getenv("TIINGO_API_KEY_4"),
    os.getenv("TIINGO_API_KEY_5"),
]
# Remove any None entries (in case a key wasn't set)
TIINGO_API_KEYS = [k for k in TIINGO_API_KEYS if k]

# Pandas Display Options
import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

# Special CIK Mapping for Restructured Companies
# format: 'TICKER': ['CURRENT_CIK', 'HISTORICAL_CIK']
SPECIAL_TICKER_CIKS = {
    'GOOG': ['1652044', '1288776'],  # Alphabet Inc (2015-Now), Google Inc (Pre-2015)
    'GOOGL': ['1652044', '1288776'],
    # Add other known mergers here as discovered
}
