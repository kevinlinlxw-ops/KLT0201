#!/usr/bin/env python3
"""Web app for coffee futures quotes and spreads."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from coffee_futures_report import generate_reports

app = FastAPI(title="Coffee Futures Dashboard")
templates = Jinja2Templates(directory="templates")


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    quotes_df, spreads_df, _ = generate_reports(Path("config.yaml"))
    return quotes_df, spreads_df


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    quotes_df, spreads_df = _load_data()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "quotes": quotes_df.to_dict(orient="records"),
            "spreads": spreads_df.to_dict(orient="records"),
        },
    )


@app.get("/export.xlsx")
def export_excel() -> StreamingResponse:
    quotes_df, spreads_df = _load_data()
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        quotes_df.to_excel(writer, sheet_name="quotes", index=False)
        spreads_df.to_excel(writer, sheet_name="spreads", index=False)
    output.seek(0)
    filename = f"coffee_futures_{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
