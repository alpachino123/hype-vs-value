# Hype vs. Value: S&P 500 Quantitative Research

> **Can a stock's relative valuation predict its 1-year forward return?**
> This project analyzes 1.85 million daily observations across the S&P 500 (2011–2026) to quantify the relationship between market sentiment and fundamental value.

---

## 📊 Results Summary

<img width="661" height="371" alt="Image" src="https://github.com/user-attachments/assets/39258ae8-0e21-4f21-bf75-8e212573d9c6" />

---

## 🚀 Project Overview
This research develops a quantitative framework to identify market mispricing. By comparing a stock's current P/E ratio to its own 5-year historical baseline, we calculate a **Hype Score**. The study tracks 635 historical S&P 500 constituents to eliminate survivorship bias and provide a robust backtest of valuation-based investing.

### The "Hype Score" Metric
The core of this research is the Hype Score, a simple yet powerful ratio:
`Hype Score = Current P/E ÷ 5-Year Average P/E`
- **< 1.0**: Trading at a discount to historical norms (Value).
- **> 1.0**: Trading at a premium (Hype).

---

## 💡 Key Insights
1. **Deep Value Outperforms**: Stocks in the lowest Hype Score quintile (Q1) yielded nearly double the 1-year forward returns compared to the index average.
2. **The U-Shaped Curve**: A fascinating discovery where both extreme value (Q1) and extreme hype (Q5) outperformed the middle-of-the-road stocks (Q3), suggesting that market momentum and deep value are both viable alpha drivers, while "fairly priced" stocks often stagnate.
3. **Case Study (AMZN)**: High-reinvestment growth stocks often appear "hyped" for years due to low EPS, highlighting the need for sector-specific adjustments in valuation models.

---

## 🛠️ Tech Stack
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Power Bi](https://img.shields.io/badge/power_bi-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)

---

## 📂 Repository Structure
- `scripts/`: Python ETL pipeline for data extraction (SEC EDGAR & Yahoo Finance).
- `sql/`: Complex views and analytical queries for PostgreSQL.
- `dashboard/`: Power BI .pbix file.
- `research_report/`: Full PDF research paper detailing findings and methodology.

---

## 🔧 Installation & Usage
1. **Database Setup**: Run the schema scripts in `sql/schema.sql` to initialize the PostgreSQL environment.
2. **Data Pipeline**: Configure your `.env` file with DB credentials and run `scripts/main_pipeline.py`.
3. **Visualization**: Open the Power BI file in `dashboard/` and refresh the data source to connect to your local DB.

---

## ⚠️ Limitations
- **Single-Factor Focus**: The model currently relies on P/E; future iterations will incorporate Free Cash Flow (FCF).
- **Sector Bias**: Certain high-growth sectors (Tech) structurally trade at higher multiples, requiring a more nuanced baseline than a simple 5-year average.

---

## 📬 Contact
Developed by **Yosef Anteneh** - Feel free to reach out for collaboration or inquiries regarding the methodology.
