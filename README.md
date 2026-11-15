# Company Checker — Business Quant edition

This edition replaces the old Financial Modeling Prep connection with Business Quant's Historical Financial Metrics API.

## Features
- Search up to 5 US-listed ticker symbols at once.
- Annual revenue history.
- Annual operating income history.
- Daily P/E ratio history.
- Tables and line charts for each company.
- Side-by-side latest-value comparison and historical comparison graph.
- Metric slugs are discovered from Business Quant's metadata catalogue rather than guessed.
- One historical API request fetches all three metrics for up to five tickers.
- Caches the metric catalogue for 24 hours and results for 30 minutes.

## Important free-plan limits
Business Quant's currently published Free plan lists:
- 30 API calls per day.
- Latest 2 years of financial statements and metric history in the API.
- Latest 1 year of prices.
- 0.1 GB data transfer per month.

The app therefore defaults to a 2-year window. Availability can vary by ticker and metric. This is not a promise of full global coverage; the API documentation describes US-listed stocks, ETFs and mutual funds.

**Licence caution:** Business Quant describes its free plan as being for trying out/evaluation. Its pricing page distinguishes personal/internal use from commercial use and redistribution. Before relying on this hosted app as an ongoing service, check directly with Business Quant that your private, personal use is permitted on the free plan. Do not make the app public or share Business Quant data onward without the required permission.

## Configure locally
1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # macOS/Linux:
   source .venv/bin/activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Create `.streamlit/secrets.toml`:
   ```toml
   BUSINESSQUANT_API_KEY = "your-business-quant-api-key"
   APP_PASSWORD = "your-private-password"
   ```
6. Run:
   ```bash
   streamlit run app.py
   ```

## Deploy to Streamlit Community Cloud
1. Create a **private** GitHub repository.
2. Upload `app.py`, `requirements.txt`, and `README.md`.
3. Do not upload `.streamlit/secrets.toml` or your API key.
4. Create/deploy the app at https://share.streamlit.io/ and select `app.py`.
5. In app Settings → Secrets, add:
   ```toml
   BUSINESSQUANT_API_KEY = "your-business-quant-api-key"
   APP_PASSWORD = "your-private-password"
   ```
6. Restrict Streamlit viewer access to only the people you intend to invite.

## Data source and API shape
- Base URL: `https://data.businessquant.com`
- Metric catalogue: `GET /metadata?table=historic&api_key=...`
- Historical metrics: `GET /historic?slug=...&ticker=...&period=2y&api_key=...`

The app resolves the slugs for Revenue (Annual), Operating Income (Annual), and Price to Earnings from the catalogue at runtime.

## Notes
- The app does not convert currencies. Check the reporting currency in company filings before comparing financial statement values.
- The P/E history is daily, while revenue and operating income are annual.
- If a metric or ticker is unavailable on the free plan, the app will show missing data or an API error rather than inventing values.
- Never commit API keys to GitHub. If a key is exposed, revoke it and generate a new one.
