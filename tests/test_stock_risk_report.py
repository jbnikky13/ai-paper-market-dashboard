import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import stock_risk_monitor


class StockRiskReportCaptureTests(unittest.TestCase):
    def test_company_news_matching_excludes_generic_macro_context(self):
        macro = {
            "title": "Nigeria inflation and central bank interest rate outlook",
            "description": "Naira exchange rate and inflation update",
        }
        for item in stock_risk_monitor.WATCHLIST:
            self.assertFalse(stock_risk_monitor._matches_news(macro, item))
        self.assertTrue(stock_risk_monitor._is_market_context(macro))

    def test_issuer_headlines_match_only_the_named_company(self):
        tip_story = {"title": "The Initiates Plc announces audited results", "description": ""}
        tip = next(x for x in stock_risk_monitor.WATCHLIST if x["symbol"] == "TIP")
        gtco = next(x for x in stock_risk_monitor.WATCHLIST if x["symbol"] == "GTCO")
        self.assertTrue(stock_risk_monitor._matches_news(tip_story, tip))
        self.assertFalse(stock_risk_monitor._matches_news(tip_story, gtco))

    def test_build_report_captures_telegram_html_without_sending(self):
        now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
        story = {
            "title": "NVIDIA announces quarterly results",
            "url": "https://example.test/nvidia-results",
            "description": "Company results update",
            "source": "Nairametrics",
            "category": "publisher",
        }
        meta = {
            "provider": "Nairametrics + Reuters + official issuer/exchange discovery",
            "status": "ok",
            "count": 1,
            "providers": [{"provider": "Nairametrics", "status": "ok", "count": 1}],
        }
        quote = {
            "price": 180.0, "currency": "USD", "daily": 1.25, "weekly": 2.5,
            "timestamp": now, "source": "Test fixture",
        }
        with patch.object(stock_risk_monitor, "_news_for_watchlist", return_value=([story], meta)), \
             patch.object(stock_risk_monitor, "kobo_ngx", return_value=({}, "NO_KEY", "Kobo Terminal")), \
             patch.object(stock_risk_monitor, "_get_history", return_value=(dict(quote), None)), \
             patch.object(stock_risk_monitor, "send") as send_mock:
            lines, results = stock_risk_monitor.build_report(now=now)
            telegram_text = "\n".join(lines)

        self.assertIn("DAILY STOCK RISK WATCH", telegram_text)
        self.assertIn("NVIDIA announces quarterly results", telegram_text)
        self.assertIn("Data confidence:", telegram_text)
        self.assertIn("Nairametrics", telegram_text)
        self.assertIn("Not investment advice", telegram_text)
        self.assertEqual(len(results), len(stock_risk_monitor.WATCHLIST))
        send_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()