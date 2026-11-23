import unittest
from datetime import datetime, timedelta, timezone

from stock_news_sources import _items_from_feed, _is_official, _parse_date


class StockNewsSourceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)

        def test_official_domain_allowlist_rejects_unrelated_hosts(self):
        self.assertTrue(_is_official("https://doclib.ngxgroup.com/investors"))
        self.assertTrue(_is_official("https://investor.nvidia.com/news"))
        self.assertFalse(_is_official("https://example.com/ngxgroup.com"))

    def test_official_google_news_item_uses_publisher_domain(self):
        xml = """<rss><channel><item>
          <title>GTCO announces results</title>
          <link>https://news.google.com/rss/articles/example</link>
          <description>Company release</description>
          <pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate>
          <source url="https://www.gtco-plc.com/">GTCO</source>
        </item></channel></rss>"""
        items = _items_from_feed(xml, "Official issuer/exchange discovery", "official", self.now)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "gtco-plc.com")
        self.assertTrue(items[0]["source_verified"])

    def test_official_feed_rejects_non_allowlisted_publisher(self):
        xml = """<rss><channel><item>
          <title>False official claim</title><link>https://news.google.com/example</link>
          <pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate>
          <source url="https://example.com/">Example</source>
        </item></channel></rss>"""
        self.assertEqual(_items_from_feed(xml, "Official", "official", self.now), [])

    def test_reuters_items_keep_publisher_attribution(self):
        xml = """<rss><channel><item>
          <title>NVIDIA market update - Reuters</title><link>https://news.google.com/example</link>
          <pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate>
          <source url="https://www.reuters.com/business/">Reuters</source>
        </item></channel></rss>"""
        items = _items_from_feed(xml, "Reuters via Google News", "independent", self.now)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "Reuters")

    def test_stale_items_are_excluded(self):
        old = (self.now - timedelta(days=10)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        xml = f"""<rss><channel><item>
          <title>Old report</title><link>https://nairametrics.com/old</link>
          <pubDate>{old}</pubDate>
        </item></channel></rss>"""
        self.assertEqual(_items_from_feed(xml, "Nairametrics", "publisher", self.now), [])

    def test_unparseable_date_is_retained_with_missing_timestamp(self):
        self.assertIsNone(_parse_date("not a date"))


if __name__ == "__main__":
    unittest.main()
