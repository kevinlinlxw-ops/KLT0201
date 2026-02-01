# Coffee Futures Daily Fetcher

This project fetches daily Arabica (ICE KC) and Robusta (ICE RC) coffee futures data from Yahoo Finance and produces:

- Daily close for the front contract plus the next five contracts.
- Daily open interest (when available from the data provider).
- Spread between each adjacent contract in the configured curve.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure Contracts

Edit `config.yaml` to match the contract series you need. You can either provide explicit symbols or let the script build the front month + next five contracts automatically based on month codes.

```yaml
commodities:
  arabica:
    symbol_root: KC
    month_codes: [H, K, N, U, Z]
    exchange_suffix: .NYB
    # Optional: if you want full manual control, set symbols and the script will use them.
    # symbols:
    #   - KCH25.NYB
    #   - KCK25.NYB
```

## Run

```bash
python coffee_futures_report.py --print
```

Outputs are stored in `output/` in CSV, JSON, and Excel formats by default.

## Web App

Run the FastAPI app to view a dashboard and download Excel output:

```bash
uvicorn app:app --reload --port 8000
```

Then open http://localhost:8000 to view the dashboard and download an Excel workbook with quotes and spreads.

## Notes

- Open interest data is only included when the data provider returns it.
- The generated contract list rolls to the next month in the configured `month_codes` calendar. To delay the roll, set `roll_day` for a commodity (e.g., `roll_day: 5`).
- If you want a different data source, adjust `fetch_contract_quote` in `coffee_futures_report.py`.
