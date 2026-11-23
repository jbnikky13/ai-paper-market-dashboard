import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import telegram_bot


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class KoboNGXTests(unittest.TestCase):
    def test_documented_stocks_payload_maps_watchlist_and_source_timestamps(self):
        payload = {
            "stocks": [
                {
                    "symbol": "GTCO",
                    "name": "Guaranty Trust Holding Company Plc",
                    "current_price": 116,
                    "previous_close": 117,
                    "change_percent": -0.85,
                    "pct_change_7d": -2.93,
                    "trade_date": "2026-11-23T00:00:00",
                },
                {
                    "symbol": "MTNN",
                    "name": "MTN Nigeria Communications Plc",
                    "current_price": 800,
                    "change_percent": 1.25,
                    "pct_change_7d": 3.5,
                    "trade_date": "2026-11-23T00:00:00",
                },
                {
                    "symbol": "TIP",
                    "name": "The Initiates Plc",
                    "current_price": 5.5,
                    "change_percent": 0.0,
                    "pct_change_7d": None,
                    "trade_date": "2026-11-23T00:00:00",
                },
                {
                    "symbol": "DANGCEM",
                    "name": "Dangote Cement Plc",
                    "current_price": 710,
                    "change_percent": -1.1,
                    "pct_change_7d": -4.2,
                    "trade_date": "2026-11-23T00:00:00",
                },
            ],
            "as_of": "2026-11-23T16:00:00.000Z",
            "stale_after": "2099-01-01T00:00:00.000Z",
        }
        with patch.object(telegram_bot, "KOBO_KEY", "test-key"), \
             patch.object(telegram_bot, "kobo_request", return_value=(FakeResponse(payload), None)):
            rows, status, source = telegram_bot.kobo_ngx()

        self.assertEqual(status, "LIVE")
        self.assertEqual(source, "Kobo Terminal NGX API")
        self.assertEqual(set(rows), {"GTCO", "MTNN", "TIP", "DANGCEM"})
        self.assertEqual(rows["GTCO"]["price"], 116.0)
        self.assertEqual(rows["GTCO"]["change"], -0.85)
        self.assertEqual(rows["GTCO"]["weekly"], -2.93)
        self.assertEqual(rows["GTCO"]["weekly_label"], "7-day")
        self.assertEqual(rows["GTCO"]["timestamp"], datetime(2026, 11, 23, 0, 0, tzinfo=timezone.utc))
        self.assertIn("2026-11-23 16:00 UTC", rows["GTCO"]["timestamp_label"])
        self.assertFalse(rows["GTCO"]["stale"])

    def test_missing_key_does_not_attempt_request(self):
        with patch.object(telegram_bot, "KOBO_KEY", ""), \
             patch.object(telegram_bot, "kobo_request") as request_mock:
            rows, status, _ = telegram_bot.kobo_ngx()
        self.assertEqual(rows, {})
        self.assertEqual(status, "NO_KEY")
        request_mock.assert_not_called()

    def test_expired_snapshot_is_marked_stale(self):
        payload = {
            "stocks": [{"symbol": "GTCO", "current_price": 116, "change_percent": -0.85}],
            "as_of": "2026-11-18T23:17:57.326Z",
            "stale_after": "2026-11-19T08:00:00.000Z",
        }
        with patch.object(telegram_bot, "KOBO_KEY", "test-key"), \
             patch.object(telegram_bot, "kobo_request", return_value=(FakeResponse(payload), None)):
            rows, status, _ = telegram_bot.kobo_ngx()
        self.assertEqual(status, "STALE")
        self.assertTrue(rows["GTCO"]["stale"])


if __name__ == "__main__":
    unittest.main()
