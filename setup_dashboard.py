"""
One-time (or re-run monthly) script to set up the dashboards sheet.
Only creates blocks for months that have data in the raw sheet.
Run with: docker compose run bot python setup_dashboard.py

After running: in each chart go to Chart editor -> Customize -> Slice label -> Value
"""
import json
import os
from datetime import date

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
GOOGLE_CREDENTIALS = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

MAX_MONTHS = 12
BLOCK = 25   # rows per month block
CATS = 18    # max categories in chart range


def _income_formula(month_date: date) -> str:
    start = month_date.strftime("%Y-%m-%d")
    if month_date.month == 12:
        end = date(month_date.year + 1, 1, 1).strftime("%Y-%m-%d")
    else:
        end = date(month_date.year, month_date.month + 1, 1).strftime("%Y-%m-%d")
    return (
        f'=SUMIFS(raw!$D:$D,raw!$B:$B,"Доход",'
        f'raw!$A:$A,">={start}",'
        f'raw!$A:$A,"<{end}")'
    )


def _query_formula(month_date: date) -> str:
    start = month_date.strftime("%Y-%m-%d")
    if month_date.month == 12:
        end = date(month_date.year + 1, 1, 1).strftime("%Y-%m-%d")
    else:
        end = date(month_date.year, month_date.month + 1, 1).strftime("%Y-%m-%d")
    return (
        f"""=IFERROR(QUERY(raw!$A:$D,"SELECT B, SUM(D) WHERE B <> 'Доход' """
        f"""AND A >= date '{start}' AND A < date '{end}' """
        f"""GROUP BY B LABEL B '', SUM(D) ''",-1),{{""}})"""
    )


def _month_label(month_date: date) -> str:
    months_ru = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]
    return f"{months_ru[month_date.month - 1]} {month_date.year}"


def get_active_months(raw_ws: gspread.Worksheet) -> list[date]:
    """Return list of month start dates that have data, newest first, max 12."""
    dates = raw_ws.col_values(1)[1:]   # skip header row
    months = set()
    for d in dates:
        if not d:
            continue
        try:
            parsed = date.fromisoformat(d)
            months.add(date(parsed.year, parsed.month, 1))
        except ValueError:
            continue
    return sorted(months, reverse=True)[:MAX_MONTHS]


def main() -> None:
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    raw_ws = spreadsheet.worksheet("raw")
    active_months = get_active_months(raw_ws)

    if not active_months:
        print("No data in raw sheet yet. Run the script after adding transactions.")
        return

    print(f"Found {len(active_months)} month(s) with data: "
          f"{', '.join(_month_label(m) for m in active_months)}")

    try:
        ws = spreadsheet.worksheet("dashboards")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet("dashboards", rows=len(active_months) * BLOCK + 10, cols=20)

    sheet_id = ws.id
    ws.clear()

    # --- Cell updates ---
    updates = []

    for n, month_date in enumerate(active_months):
        r = n * BLOCK   # 0-indexed base row

        updates.append({"range": f"dashboards!A{r + 1}", "values": [[_month_label(month_date)]]})
        updates.append({"range": f"dashboards!A{r + 2}", "values": [["Доход:"]]})
        updates.append({"range": f"dashboards!B{r + 2}", "values": [[_income_formula(month_date)]]})
        updates.append({"range": f"dashboards!A{r + 4}", "values": [[_query_formula(month_date)]]})

    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print("Formulas written.")

    # --- Charts ---
    requests = []

    for n in range(len(active_months)):
        r = n * BLOCK
        data_start = r + 3
        data_end = data_start + CATS

        requests.append({
            "addChart": {
                "chart": {
                    "spec": {
                        "title": "",
                        "pieChart": {
                            "legendPosition": "RIGHT_LEGEND",
                            "threeDimensional": False,
                            "domain": {
                                "sourceRange": {
                                    "sources": [{
                                        "sheetId": sheet_id,
                                        "startRowIndex": data_start,
                                        "endRowIndex": data_end,
                                        "startColumnIndex": 0,
                                        "endColumnIndex": 1,
                                    }]
                                }
                            },
                            "series": {
                                "sourceRange": {
                                    "sources": [{
                                        "sheetId": sheet_id,
                                        "startRowIndex": data_start,
                                        "endRowIndex": data_end,
                                        "startColumnIndex": 1,
                                        "endColumnIndex": 2,
                                    }]
                                }
                            },
                        },
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId": sheet_id,
                                "rowIndex": r,
                                "columnIndex": 3,
                            },
                            "widthPixels": 500,
                            "heightPixels": 460,
                        }
                    },
                }
            }
        })

    spreadsheet.batch_update({"requests": requests})
    print(f"Done: {len(active_months)} pie chart(s) created.")
    print()
    print("Manual step remaining:")
    print("  In each chart: Chart editor -> Customize -> Slice label -> Value")


if __name__ == "__main__":
    main()
