-- =============================================================
-- SQL VIEWS FOR POWER BI — PAGE 2: SECTOR ANALYSIS
-- Run this script once in pgAdmin or DBeaver to create the views.
-- =============================================================

-- View 1: Quarterly Median Hype Score per Sector (for Heatmap)
CREATE OR REPLACE VIEW vw_sector_heatmap AS
SELECT
    c.sector,
    DATE_TRUNC('quarter', ma.analysis_date)::date            AS quarter_start,
    TO_CHAR(DATE_TRUNC('quarter', ma.analysis_date), 'YYYY "Q"Q') AS quarter_label,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ma.hype_score) AS median_hype_score,
    COUNT(DISTINCT ma.symbol)                                  AS num_stocks
FROM market_analysis ma
JOIN companies c ON ma.symbol = c.symbol
WHERE ma.hype_score BETWEEN 0.05 AND 15
  AND c.sector NOT IN ('Unknown', '')
GROUP BY c.sector, DATE_TRUNC('quarter', ma.analysis_date)
ORDER BY quarter_start, c.sector;


-- View 2: Monthly Median Hype per Sector (for Line Chart with Slicer)
CREATE OR REPLACE VIEW vw_sector_monthly_hype AS
SELECT
    c.sector,
    DATE_TRUNC('month', ma.analysis_date)::date              AS month_start,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ma.hype_score) AS median_hype_score,
    COUNT(DISTINCT ma.symbol)                                  AS num_stocks
FROM market_analysis ma
JOIN companies c ON ma.symbol = c.symbol
WHERE ma.hype_score BETWEEN 0.05 AND 15
  AND c.sector NOT IN ('Unknown', '')
GROUP BY c.sector, DATE_TRUNC('month', ma.analysis_date)
ORDER BY month_start, c.sector;


-- View 3: Hype Score per Sector at 3 Known Bubble Peaks
CREATE OR REPLACE VIEW vw_sector_bubble_comparison AS
SELECT
    c.sector,
    'Dot-com Peak (2000)'    AS bubble_period,
    2000                      AS bubble_year,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ma.hype_score) AS median_hype_score,
    COUNT(DISTINCT ma.symbol)                                    AS num_stocks
FROM market_analysis ma
JOIN companies c ON ma.symbol = c.symbol
WHERE ma.analysis_date BETWEEN '2000-01-01' AND '2000-12-31'
  AND ma.hype_score BETWEEN 0.05 AND 15
  AND c.sector NOT IN ('Unknown', '')
GROUP BY c.sector

UNION ALL

SELECT
    c.sector,
    'GFC Pre-Crash (2007)'   AS bubble_period,
    2007                      AS bubble_year,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ma.hype_score) AS median_hype_score,
    COUNT(DISTINCT ma.symbol)                                    AS num_stocks
FROM market_analysis ma
JOIN companies c ON ma.symbol = c.symbol
WHERE ma.analysis_date BETWEEN '2007-07-01' AND '2007-12-31'
  AND ma.hype_score BETWEEN 0.05 AND 15
  AND c.sector NOT IN ('Unknown', '')
GROUP BY c.sector

UNION ALL

SELECT
    c.sector,
    'COVID Rally Peak (2021)' AS bubble_period,
    2021                       AS bubble_year,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ma.hype_score) AS median_hype_score,
    COUNT(DISTINCT ma.symbol)                                    AS num_stocks
FROM market_analysis ma
JOIN companies c ON ma.symbol = c.symbol
WHERE ma.analysis_date BETWEEN '2021-01-01' AND '2021-12-31'
  AND ma.hype_score BETWEEN 0.05 AND 15
  AND c.sector NOT IN ('Unknown', '')
GROUP BY c.sector

ORDER BY bubble_year, median_hype_score DESC;
