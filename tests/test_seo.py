"""Проверка SEO в исходном HTTP-ответе: поисковику не требуется JavaScript."""

import json
import struct
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

from fastapi.testclient import TestClient

import database
from router import seo
from router.server import app


class HeadParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.meta = {}
        self.canonical = []
        self.schemas = []
        self.in_schema = False
        self.h1_count = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            name = attrs.get("name") or attrs.get("property")
            self.meta.setdefault(name, []).append(attrs.get("content"))
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs["href"])
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.in_schema = True
        if tag == "h1":
            self.h1_count += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_schema = False

    def handle_data(self, data):
        if self.in_schema:
            self.schemas.append(json.loads(data))


class SeoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(database, "DB_PATH", Path(self.temp.name) / "seo.db")
        self.domain_patch = patch.object(seo, "SITE_URL", "https://blindtyping.codetimes.org")
        self.db_patch.start()
        self.domain_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.domain_patch.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_public_metadata(self):
        for path in seo.PUBLIC_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path + "?utm_source=test", headers={"Host": "untrusted.example"})
                self.assertEqual(response.status_code, 200)
                head = HeadParser(response.text)
                self.assertEqual(head.canonical, [seo.SITE_URL + path])
                self.assertEqual(head.meta["og:url"], [seo.SITE_URL + path])
                self.assertEqual(head.meta["og:image"], [seo.SITE_URL + "/static/img/social-preview.png"])
                self.assertEqual(len(head.meta["description"]), 1)
                self.assertIn("index, follow", head.meta["robots"][0])
                self.assertEqual(head.h1_count, 1)
                self.assertEqual(len(head.schemas), 1)
                self.assertEqual(head.schemas[0]["@context"], "https://schema.org")
                self.assertNotIn("untrusted.example", response.text)
                self.assertNotIn("X-Robots-Tag", response.headers)

    def test_homepage_redirect(self):
        response = self.client.get("/index.html?utm_source=test", follow_redirects=False)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["location"], "/?utm_source=test")

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt")
        self.assertIn("text/plain", robots.headers["content-type"])
        self.assertIn("Sitemap: " + seo.SITE_URL + "/sitemap.xml", robots.text)
        self.assertNotIn("Disallow: /profile", robots.text)
        response = self.client.get("/sitemap.xml")
        self.assertIn("application/xml", response.headers["content-type"])
        xml = ElementTree.fromstring(response.content)
        locations = [node.text for node in xml.findall("{*}url/{*}loc")]
        self.assertEqual(locations, [seo.SITE_URL + path for path in seo.PUBLIC_PATHS])

    def test_private_and_api_noindex(self):
        for path in seo.PRIVATE_PATHS:
            response = self.client.get(path)
            self.assertEqual(response.headers["X-Robots-Tag"], "noindex, follow")
            self.assertEqual(HeadParser(response.text).meta["robots"], ["noindex, follow"])
        for path in ("/docs", "/redoc", "/openapi.json", "/api/v1/stats/leaderboard", "/not-found"):
            self.assertIn("noindex", self.client.get(path).headers["X-Robots-Tag"])

    def test_staging_has_no_public_urls(self):
        with patch.object(seo, "SITE_URL", ""):
            response = self.client.get("/")
            self.assertIn("noindex", response.headers["X-Robots-Tag"])
            head = HeadParser(response.text)
            self.assertEqual(head.canonical, [])
            self.assertEqual(head.schemas, [])
            self.assertIn("Disallow: /\n", self.client.get("/robots.txt").text)
            xml = ElementTree.fromstring(self.client.get("/sitemap.xml").content)
            self.assertEqual(list(xml), [])

    def test_ranking_in_html_and_escaped_names(self):
        registration = self.client.post("/api/v1/auth/register", json={
            "nickname": "<img src=x>", "email": "seo@example.com", "password": "secret123",
        }).json()
        headers = {"Authorization": "Bearer " + registration["token"]}
        self.client.post("/api/v1/stats/submit", headers=headers, json={
            "speed_wpm": 40, "accuracy_pct": 95.5,
        })
        for path in seo.PUBLIC_PATHS:
            response = self.client.get(path)
            self.assertIn('&lt;img src=x&gt;</td>', response.text)
            self.assertNotIn('<img src=x>', response.text)
            self.assertIn('data-field="accuracy" class="num">95,5%</td>', response.text)
            self.assertNotIn("Загрузка рейтинга…", response.text)

    def test_preview_image(self):
        image = self.client.get("/static/img/social-preview.png")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.headers["content-type"], "image/png")
        self.assertEqual(struct.unpack(">II", image.content[16:24]), (1200, 630))
        self.assertEqual(self.client.get("/static/img/favicon.svg").status_code, 200)

    def test_domain_configuration(self):
        self.assertEqual(seo.validate_site_url("https://blindtyping.codetimes.org/"), seo.SITE_URL)
        for invalid in ("javascript:alert(1)", "https://example.com/path", "https://user:pass@example.com", "https://example.com?x=1"):
            with self.subTest(url=invalid), self.assertRaises(ValueError):
                seo.validate_site_url(invalid)


if __name__ == "__main__":
    unittest.main()
