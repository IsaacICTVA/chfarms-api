import asyncio
import unittest

from sheets_sync import GoogleSheetsService, QueueItem, SheetSettings, queue_item_to_row


class FakeWorksheet:
    def __init__(self): self.rows = []
    def append_rows(self, rows, value_input_option): self.rows.extend(rows)
    def get_all_records(self): return [{"Date": "2026-09-07"}]


class FakeWorkbook:
    def __init__(self): self.tabs = {}
    def worksheet(self, name): return self.tabs.setdefault(name, FakeWorksheet())


class SheetsSyncTests(unittest.TestCase):
    def setUp(self):
        self.workbook = FakeWorkbook()
        settings = SheetSettings("sheet-id", '{"client_email":"svc@example.com","private_key":"key"}')
        client = lambda _: type("Client", (), {"open_by_key": lambda _, __: self.workbook})()
        self.service = GoogleSheetsService(settings, client)

    def test_translates_broiler_row(self):
        tab, row = queue_item_to_row(QueueItem("append_row", data={"date":"2026-09-07", "batch":"19a"}))
        self.assertEqual(tab, "03_Broiler Live Log")
        self.assertEqual(row[:2], ["2026-09-07", "19a"])

    def test_flush_batches_per_tab_and_reads_records(self):
        result = asyncio.run(self.service.flush([
            {"action":"append_row", "sheet_tab":"03_Broiler Live Log", "data":{"batch":"19a"}},
            {"action":"append_row", "sheet_tab":"03_Broiler Live Log", "data":{"batch":"19b"}},
        ]))
        self.assertEqual(result.flushed, 2)
        self.assertFalse(result.errors)
        self.assertEqual(len(self.workbook.tabs["03_Broiler Live Log"].rows), 2)
        self.assertEqual(asyncio.run(self.service.read_records()), [{"Date":"2026-09-07"}])

    def test_invalid_item_is_failed(self):
        result = asyncio.run(self.service.flush([{"action":"delete", "data":{}}]))
        self.assertEqual(result.flushed, 0)
        self.assertEqual(result.failed_indexes, (0,))


if __name__ == "__main__":
    unittest.main()
