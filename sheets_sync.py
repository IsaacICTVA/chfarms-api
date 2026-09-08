"""Framework-neutral, async-safe Google Sheets gateway for CH Farms."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

LOGGER = logging.getLogger(__name__)
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DEFAULT_BROILER_TAB = "03_Broiler Live Log"
SUPPORTED_TABS = frozenset({DEFAULT_BROILER_TAB, "07_Customer_Order_Quote", "05_Egg_Stock_Log", "03_Feed_Stock_Cost", "02_Processing Log", "04_Vaccine_Drug_Log", "05_Layer_Log"})


class SheetsConfigurationError(RuntimeError):
    """Google Sheets configuration is absent or invalid."""


@dataclass(frozen=True)
class SheetSettings:
    sheet_id: str
    credentials_json: str

    @classmethod
    def from_environment(cls) -> "SheetSettings":
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        raw = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        encoded = os.getenv("GOOGLE_CREDENTIALS_BASE64", "").strip()
        if raw and encoded:
            raise SheetsConfigurationError("Set only GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_BASE64.")
        if encoded:
            try:
                raw = base64.b64decode(encoded, validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise SheetsConfigurationError("GOOGLE_CREDENTIALS_BASE64 is invalid.") from exc
        if not sheet_id:
            raise SheetsConfigurationError("GOOGLE_SHEET_ID is not set.")
        if not raw:
            raise SheetsConfigurationError("Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_BASE64.")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SheetsConfigurationError("Google credentials are not valid JSON.") from exc
        if not isinstance(parsed, dict) or not parsed.get("client_email") or not parsed.get("private_key"):
            raise SheetsConfigurationError("Google credentials are incomplete.")
        return cls(sheet_id, raw)


@dataclass(frozen=True)
class QueueItem:
    action: str
    sheet_tab: str = DEFAULT_BROILER_TAB
    data: Mapping[str, Any] = field(default_factory=dict)
    ts: str = ""

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]) -> "QueueItem":
        data = item.get("data", {})
        if not isinstance(data, Mapping):
            raise ValueError("Queue item data must be an object.")
        return cls(str(item.get("action", "append_row")), str(item.get("sheet_tab") or DEFAULT_BROILER_TAB), data, str(item.get("ts", "")))


@dataclass(frozen=True)
class FlushResult:
    flushed: int
    failed_indexes: tuple[int, ...]
    errors: tuple[str, ...]


def _value(data: Mapping[str, Any], key: str, default: Any = "") -> Any:
    value = data.get(key, default)
    return "" if value is None else value


def queue_item_to_row(item: QueueItem) -> tuple[str, list[Any]]:
    """Validate and serialize one local queue item into an append-only row."""
    tab = "03_Feed_Stock_Cost" if item.action == "feed_delivery" else item.sheet_tab
    if tab not in SUPPORTED_TABS:
        raise ValueError(f"Unsupported Google Sheet tab: {tab}")
    if item.action not in {"append_row", "feed_delivery"}:
        raise ValueError(f"Unsupported queue action: {item.action}")
    d = item.data
    rows = {
        DEFAULT_BROILER_TAB: [_value(d,"date"),_value(d,"batch"),_value(d,"mort",0),_value(d,"feed",0),_value(d,"notes"),_value(d,"logged_by"),item.ts],
        "07_Customer_Order_Quote": [_value(d,"quote_number"),_value(d,"quote_date"),_value(d,"customer_name"),_value(d,"phone"),_value(d,"product"),_value(d,"quantity",0),_value(d,"unit_price",0),_value(d,"total_value",0),_value(d,"delivery_date"),_value(d,"payment_terms"),_value(d,"status"),_value(d,"availability_eta"),_value(d,"agent"),_value(d,"notes"),item.ts],
        "05_Egg_Stock_Log": [_value(d,"date"),_value(d,"pullet_collected",0),_value(d,"pullet_sold",0),_value(d,"pullet_closing",0),_value(d,"medium_collected",0),_value(d,"medium_sold",0),_value(d,"medium_closing",0),_value(d,"daily_revenue",0),_value(d,"logged_by"),item.ts],
        "03_Feed_Stock_Cost": [_value(d,"date"),_value(d,"code"),_value(d,"bags",0),_value(d,"supplier"),_value(d,"ref"),item.ts],
        "02_Processing Log": [_value(d,"batch"),_value(d,"date"),_value(d,"birds",0),_value(d,"weight_kg",0),_value(d,"price_per_kg",0),_value(d,"revenue",0),_value(d,"note"),_value(d,"logged_by"),item.ts],
        "04_Vaccine_Drug_Log": [_value(d,"date"),_value(d,"batch"),_value(d,"vaccine"),_value(d,"notes"),_value(d,"logged_by"),item.ts],
        "05_Layer_Log": [_value(d,"date"),_value(d,"counter"),_value(d,"layer_opening",0),_value(d,"layer_mortality",0),_value(d,"layer_closing",0),_value(d,"notes"),item.ts],
    }
    return tab, rows[tab]


class GoogleSheetsService:
    """Blocking gspread calls are isolated with asyncio.to_thread for FastAPI."""
    def __init__(self, settings: SheetSettings | None = None, client_factory: Callable[[SheetSettings], Any] | None = None) -> None:
        self.settings = settings or SheetSettings.from_environment()
        self._client_factory = client_factory or self._build_client

    @staticmethod
    def _build_client(settings: SheetSettings) -> Any:
        import gspread
        from google.oauth2.service_account import Credentials
        credentials = Credentials.from_service_account_info(json.loads(settings.credentials_json), scopes=[SHEETS_SCOPE])
        return gspread.authorize(credentials)

    def _workbook(self) -> Any:
        return self._client_factory(self.settings).open_by_key(self.settings.sheet_id)

    def _flush_sync(self, queue: Sequence[Mapping[str, Any]]) -> FlushResult:
        grouped: dict[str, list[tuple[int, list[Any]]]] = {}
        errors: list[str] = []
        failed: list[int] = []
        for index, raw in enumerate(queue):
            try:
                tab, row = queue_item_to_row(QueueItem.from_mapping(raw))
                grouped.setdefault(tab, []).append((index, row))
            except (TypeError, ValueError) as exc:
                failed.append(index); errors.append(f"Queue item {index}: {exc}")
        if not grouped:
            return FlushResult(0, tuple(failed), tuple(errors))
        try:
            workbook = self._workbook()
        except Exception:
            LOGGER.exception("Unable to open configured Google Sheet")
            return FlushResult(0, tuple(range(len(queue))), ("Google Sheets connection failed.",))
        flushed = 0
        for tab, entries in grouped.items():
            try:
                workbook.worksheet(tab).append_rows([row for _, row in entries], value_input_option="USER_ENTERED")
                flushed += len(entries)
            except Exception:
                LOGGER.exception("Google Sheets batch append failed for tab %s", tab)
                failed.extend(index for index, _ in entries)
                errors.append(f"Tab '{tab}' batch write failed.")
        return FlushResult(flushed, tuple(sorted(set(failed))), tuple(errors))

    async def flush(self, queue: Sequence[Mapping[str, Any]]) -> FlushResult:
        return await asyncio.to_thread(self._flush_sync, queue)

    def _read_records_sync(self, tab: str, limit: int | None) -> list[dict[str, Any]]:
        if tab not in SUPPORTED_TABS:
            raise ValueError(f"Unsupported Google Sheet tab: {tab}")
        records = self._workbook().worksheet(tab).get_all_records()
        return records if limit is None else records[:limit]

    async def read_records(self, tab: str = DEFAULT_BROILER_TAB, limit: int | None = None) -> list[dict[str, Any]]:
        if limit is not None and not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        return await asyncio.to_thread(self._read_records_sync, tab, limit)

    async def status(self) -> dict[str, Any]:
        try:
            await asyncio.to_thread(self._workbook)
            return {"configured": True, "available": True, "sheet_id_configured": True}
        except Exception:
            LOGGER.exception("Google Sheets status check failed")
            return {"configured": True, "available": False, "detail": "Google Sheets connection failed."}


def get_sheets_service() -> GoogleSheetsService:
    return GoogleSheetsService()
