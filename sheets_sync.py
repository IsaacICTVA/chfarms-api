"""
CH Farms — Google Sheets Write-back Module
Handles all writes from OFFLINE_QUEUE → live Google Sheet
Tab: 03_Broiler Live Log, 07_Customer_Order_Quote, 05_Egg_Stock_Log
"""

import os, json, datetime

def get_sheets_service():
    """Build authenticated Sheets service from GOOGLE_CREDENTIALS env var."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_json:
            return None, "GOOGLE_CREDENTIALS env var not set"

        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        return gc, None
    except Exception as e:
        return None, str(e)


def open_sheet(gc, sheet_id, tab_name):
    """Open a specific tab in the Google Sheet."""
    try:
        wb = gc.open_by_key(sheet_id)
        ws = wb.worksheet(tab_name)
        return ws, None
    except Exception as e:
        return None, str(e)


def flush_queue(queue, sheet_id):
    """
    Flush all queued writes to Google Sheet.
    queue: list of dicts with keys: action, sheet_tab, data, ts
    Returns: (flushed_count, errors)
    """
    if not queue:
        return 0, []

    gc, err = get_sheets_service()
    if err:
        return 0, [f"Auth failed: {err}"]

    flushed = 0
    errors = []

    for item in queue:
        action    = item.get("action")
        tab_name  = item.get("sheet_tab", "03_Broiler Live Log")
        data      = item.get("data", {})

        try:
            ws, err = open_sheet(gc, sheet_id, tab_name)
            if err:
                errors.append(f"Tab '{tab_name}' not found: {err}")
                continue

            if action == "append_row" and tab_name == "03_Broiler Live Log":
                # Append daily log row: Date | Batch | Mortality | Feed Bags | Notes | Logged By
                row = [
                    data.get("date", ""),
                    data.get("batch", ""),
                    data.get("mort", 0),
                    data.get("feed", 0),
                    data.get("notes", ""),
                    data.get("logged_by", ""),
                    item.get("ts", ""),
                ]
                ws.append_row(row, value_input_option="USER_ENTERED")
                flushed += 1

            elif action == "append_row" and tab_name == "07_Customer_Order_Quote":
                # Write quote row
                q = data
                row = [
                    q.get("quote_number", ""),
                    q.get("quote_date", ""),
                    q.get("customer_name", ""),
                    q.get("phone", ""),
                    q.get("product", ""),
                    q.get("quantity", 0),
                    q.get("unit_price", 0),
                    q.get("total_value", 0),
                    q.get("delivery_date", ""),
                    q.get("payment_terms", ""),
                    q.get("status", ""),
                    q.get("availability_eta", ""),
                    q.get("agent", ""),
                    q.get("notes", ""),
                    item.get("ts", ""),
                ]
                ws.append_row(row, value_input_option="USER_ENTERED")
                flushed += 1

            elif action == "append_row" and tab_name == "05_Egg_Stock_Log":
                d = data
                row = [
                    d.get("date", ""),
                    d.get("pullet_collected", 0),
                    d.get("pullet_sold", 0),
                    d.get("pullet_closing", 0),
                    d.get("medium_collected", 0),
                    d.get("medium_sold", 0),
                    d.get("medium_closing", 0),
                    d.get("daily_revenue", 0),
                    d.get("logged_by", ""),
                ]
                ws.append_row(row, value_input_option="USER_ENTERED")
                flushed += 1

            elif action == "feed_delivery":
                # Log feed delivery to 03_Feed_Stock_Cost or similar tab
                d_tab = "03_Feed_Stock_Cost"
                ws2, _ = open_sheet(gc, sheet_id, d_tab)
                if ws2:
                    row = [
                        data.get("date", ""),
                        data.get("code", ""),
                        data.get("bags", 0),
                        data.get("supplier", ""),
                        data.get("ref", ""),
                        item.get("ts", ""),
                    ]
                    ws2.append_row(row, value_input_option="USER_ENTERED")
                    flushed += 1

        except Exception as e:
            errors.append(f"Row write error [{action}/{tab_name}]: {str(e)}")

    return flushed, errors


def read_live_log(sheet_id, tab_name="03_Broiler Live Log"):
    """
    Read all records from the live broiler log tab.
    Returns list of dicts or error string.
    """
    gc, err = get_sheets_service()
    if err:
        return None, f"Auth: {err}"
    ws, err = open_sheet(gc, sheet_id, tab_name)
    if err:
        return None, err
    try:
        records = ws.get_all_records()
        return records, None
    except Exception as e:
        return None, str(e)
