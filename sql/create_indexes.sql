-- Step 1 of 3: Create indexes to make the joins fast
-- Run this FIRST before running stage3_analytics.py

-- Index on daily_prices for fast per-symbol date ordering
CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol_date ON daily_prices (symbol, price_date);

-- Index on fundamentals for fast per-symbol date lookups
CREATE INDEX IF NOT EXISTS idx_fundamentals_symbol_date ON fundamentals (symbol, report_date);

-- Confirm the indexes exist
SELECT tablename, indexname FROM pg_indexes
WHERE indexname IN ('idx_daily_prices_symbol_date', 'idx_fundamentals_symbol_date');
