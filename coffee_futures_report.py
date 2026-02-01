#!/usr/bin/env python3
"""Fetch daily Arabica and Robusta coffee futures prices and spreads."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml
import yfinance as yf


@dataclass
class ContractQuote:
    commodity: str
    symbol: str
    close: float | None
    open_interest: float | None
    last_trade_date: str | None


@dataclass
class SpreadQuote:
    commodity: str
    from_symbol: str
    to_symbol: str
    close_spread: float | None


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def fetch_contract_quote(commodity: str, symbol: str) -> ContractQuote:
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="7d")
    if history.empty:
        return ContractQuote(commodity, symbol, None, None, None)

    latest = history.iloc[-1]
    close = float(latest.get("Close")) if pd.notna(latest.get("Close")) else None
    open_interest = (
        float(latest.get("Open Interest"))
        if pd.notna(latest.get("Open Interest"))
        else None
    )
    last_trade_date = (
        history.index[-1].strftime("%Y-%m-%d") if len(history.index) else None
    )
    return ContractQuote(commodity, symbol, close, open_interest, last_trade_date)


def build_contract_symbols(details: dict, count: int = 6, today: date | None = None) -> list[str]:
    symbols = details.get("symbols")
    if symbols:
        return list(symbols)[:count]

    month_codes = details.get("month_codes", [])
    if not month_codes:
        raise ValueError("month_codes must be provided when symbols are not set")

    month_map = {
        "F": 1,
        "G": 2,
        "H": 3,
        "J": 4,
        "K": 5,
        "M": 6,
        "N": 7,
        "Q": 8,
        "U": 9,
        "V": 10,
        "X": 11,
        "Z": 12,
    }
    cycle = []
    for code in month_codes:
        if code not in month_map:
            raise ValueError(f"Unsupported month code: {code}")
        cycle.append((month_map[code], code))
    cycle.sort(key=lambda item: item[0])

    symbol_root = details.get("symbol_root")
    suffix = details.get("exchange_suffix", "")
    if not symbol_root:
        raise ValueError("symbol_root must be provided when symbols are not set")

    today = today or datetime.now(timezone.utc).date()
    roll_day = int(details.get("roll_day", 1))
    effective_month = today.month

    contract_months = {month for month, _ in cycle}
    if today.month in contract_months and today.day < roll_day:
        previous_index = next(
            idx for idx, (month, _) in enumerate(cycle) if month == today.month
        ) - 1
        previous_month = cycle[previous_index][0]
        effective_month = previous_month

    start_index = next(
        (idx for idx, (month, _) in enumerate(cycle) if month >= effective_month),
        0,
    )

    base_year = today.year
    if effective_month > today.month:
        base_year -= 1

    symbols_out: list[str] = []
    for offset in range(count):
        cycle_index = start_index + offset
        year_offset = cycle_index // len(cycle)
        month_num, code = cycle[cycle_index % len(cycle)]
        year = base_year + year_offset
        symbols_out.append(f"{symbol_root}{code}{str(year)[-2:]}{suffix}")
    return symbols_out


def compute_spreads(quotes: Iterable[ContractQuote]) -> list[SpreadQuote]:
    ordered = list(quotes)
    spreads: list[SpreadQuote] = []
    for first, second in zip(ordered, ordered[1:]):
        if first.close is None or second.close is None:
            spread_value = None
        else:
            spread_value = round(second.close - first.close, 6)
        spreads.append(
            SpreadQuote(
                commodity=first.commodity,
                from_symbol=first.symbol,
                to_symbol=second.symbol,
                close_spread=spread_value,
            )
        )
    return spreads


def quotes_to_frame(quotes: Iterable[ContractQuote]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "commodity": quote.commodity,
                "symbol": quote.symbol,
                "close": quote.close,
                "open_interest": quote.open_interest,
                "last_trade_date": quote.last_trade_date,
            }
            for quote in quotes
        ]
    )


def spreads_to_frame(spreads: Iterable[SpreadQuote]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "commodity": spread.commodity,
                "from_symbol": spread.from_symbol,
                "to_symbol": spread.to_symbol,
                "close_spread": spread.close_spread,
            }
            for spread in spreads
        ]
    )


def write_outputs(df: pd.DataFrame, output_dir: Path, name: str, formats: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    for fmt in formats:
        if fmt == "csv":
            df.to_csv(output_dir / f"{name}_{timestamp}.csv", index=False)
        elif fmt == "json":
            output_path = output_dir / f"{name}_{timestamp}.json"
            output_path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
        elif fmt == "xlsx":
            df.to_excel(output_dir / f"{name}_{timestamp}.xlsx", index=False)
        else:
            raise ValueError(f"Unsupported format: {fmt}")


def generate_reports(config_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    config = load_config(config_path)
    output_settings = config.get("output", {})
    output_dir = Path(output_settings.get("directory", "output"))
    formats = output_settings.get("formats", ["csv"])  # type: ignore[assignment]

    all_quotes: list[ContractQuote] = []
    all_spreads: list[SpreadQuote] = []

    for commodity, details in config.get("commodities", {}).items():
        symbols = build_contract_symbols(details)
        if not symbols:
            continue
        commodity_quotes = [fetch_contract_quote(commodity, symbol) for symbol in symbols]
        all_quotes.extend(commodity_quotes)
        all_spreads.extend(compute_spreads(commodity_quotes))

    quotes_df = quotes_to_frame(all_quotes)
    spreads_df = spreads_to_frame(all_spreads)

    write_outputs(quotes_df, output_dir, output_settings.get("filename_prefix", "quotes"), formats)
    write_outputs(spreads_df, output_dir, f"{output_settings.get('filename_prefix', 'quotes')}_spreads", formats)
    return quotes_df, spreads_df, config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config.yaml",
        type=Path,
        help="Path to configuration YAML file",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print output tables to stdout",
    )
    args = parser.parse_args()

    quotes_df, spreads_df, _ = generate_reports(args.config)

    if args.print:
        print("\nContract Quotes")
        print(quotes_df.to_string(index=False))
        print("\nContract Spreads")
        print(spreads_df.to_string(index=False))


if __name__ == "__main__":
    main()
