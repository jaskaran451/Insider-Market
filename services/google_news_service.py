import html
import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urlparse

import feedparser
import requests


class GoogleNewsService:
    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self, language="en-US", country="US", edition="US:en"):
        self.language = language
        self.country = country
        self.edition = edition

    def get_company_news(self, symbol, company_name=None, limit=30, when="7d"):
        symbol = (symbol or "").upper().strip()
        company_name = (company_name or symbol).strip()
        query = self.build_query(symbol, company_name)
        feed_url = self.build_feed_url(query, when)

        try:
            response = requests.get(
                feed_url,
                headers={"User-Agent": "InsiderAI/1.0"},
                timeout=15,
            )
            response.raise_for_status()

            parsed_feed = feedparser.parse(response.content)
            entries = parsed_feed.get("entries", [])

            if parsed_feed.get("bozo") and not entries:
                raise ValueError("Google News returned an invalid RSS feed")

            feed = []
            seen_urls = set()

            for entry in entries[:limit]:
                article = self.map_article(entry, symbol)

                if not article:
                    continue

                url = article.get("url")

                if url in seen_urls:
                    continue

                seen_urls.add(url)
                feed.append(article)

            return {
                "success": True,
                "source": "Google News",
                "query": query,
                "feed": feed,
            }

        except Exception as error:
            print(f"[GOOGLE NEWS ERROR] {symbol}:", error)
            return {
                "success": False,
                "source": "Google News",
                "query": query,
                "feed": [],
                "_error": str(error),
            }

    def build_feed_url(self, query, when):
        safe_when = when if re.fullmatch(r"\d+[hdwmy]", str(when or "")) else "7d"
        search_query = quote_plus(f"{query} when:{safe_when}")

        return (
            f"{self.BASE_URL}?q={search_query}"
            f"&hl={self.language}&gl={self.country}&ceid={self.edition}"
        )

    def build_query(self, symbol, company_name):
        clean_name = self.clean_company_name(company_name)

        if clean_name and clean_name.upper() != symbol:
            return f'"{clean_name}" OR "{symbol} stock"'

        return f'"{symbol} stock"'

    def clean_company_name(self, name):
        if not name:
            return ""

        value = str(name).strip()
        patterns = [
            r"\bInc\.?\b",
            r"\bIncorporated\b",
            r"\bCorp\.?\b",
            r"\bCorporation\b",
            r"\bCompany\b",
            r"\bCo\.?\b",
            r"\bLtd\.?\b",
            r"\bLimited\b",
            r"\bPLC\b",
            r"\bHoldings?\b",
            r"\bClass\s+[A-Z]\b",
            r"\bCommon Stock\b",
        ]

        for pattern in patterns:
            value = re.sub(pattern, "", value, flags=re.I)

        value = re.sub(r"\s+", " ", value)
        return value.strip(" ,.-")

    def map_article(self, entry, symbol):
        title = self.clean_text(entry.get("title"))
        url = (entry.get("link") or "").strip()

        if not title or not url:
            return None

        source = self.get_source(entry)
        published = entry.get("published") or entry.get("updated")
        summary = self.clean_summary(
            entry.get("summary") or entry.get("description")
        )
        topics = self.extract_topics(f"{title} {summary}")

        return {
            "title": title,
            "summary": summary,
            "banner_image": self.extract_image(entry),
            "source": source,
            "url": url,
            "time_published": self.convert_date(published),
            "topics": topics,
            "ticker_sentiment": [
                {
                    "ticker": symbol,
                    "ticker_sentiment_label": "Neutral",
                    "ticker_sentiment_score": 0.0,
                }
            ],
        }

    def get_source(self, entry):
        source = entry.get("source")

        if isinstance(source, dict):
            value = source.get("title") or source.get("href")

            if value:
                return str(value).strip()

        if source:
            return str(source).strip()

        link = entry.get("link") or ""

        try:
            domain = urlparse(link).netloc
            return domain.replace("www.", "") or "Google News"
        except Exception:
            return "Google News"

    def clean_summary(self, value):
        if not value:
            return ""

        text = str(value)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        return text[:1200]

    def clean_text(self, value):
        if not value:
            return ""

        text = html.unescape(str(value))
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_image(self, entry):
        media_content = entry.get("media_content") or []

        if isinstance(media_content, list) and media_content:
            first = media_content[0]

            if isinstance(first, dict):
                return first.get("url")

        media_thumbnail = entry.get("media_thumbnail") or []

        if isinstance(media_thumbnail, list) and media_thumbnail:
            first = media_thumbnail[0]

            if isinstance(first, dict):
                return first.get("url")

        return None

    def convert_date(self, value):
        if not value:
            return ""

        try:
            parsed = parsedate_to_datetime(value)

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
        except Exception:
            return str(value)

    def extract_topics(self, text):
        text = (text or "").lower()
        topic_keywords = {
            "Earnings": [
                "earnings",
                "revenue",
                "profit",
                "guidance",
                "quarterly results",
            ],
            "Analyst Ratings": [
                "upgrade",
                "downgrade",
                "price target",
                "outperform",
                "underperform",
            ],
            "Partnerships": [
                "partnership",
                "collaboration",
                "contract",
                "agreement",
                "deal",
            ],
            "Mergers & Acquisitions": [
                "acquisition",
                "merger",
                "buyout",
                "takeover",
            ],
            "Legal": [
                "lawsuit",
                "investigation",
                "probe",
                "settlement",
                "regulator",
            ],
            "Management": [
                "chief executive",
                "ceo",
                "chief financial",
                "cfo",
                "management",
            ],
            "Product": [
                "product",
                "platform",
                "technology",
                "launch",
                "software",
            ],
            "Stock Movement": [
                "stock",
                "shares",
                "surges",
                "falls",
                "jumps",
                "drops",
            ],
        }
        topics = []

        for topic, keywords in topic_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text)

            if matches:
                relevance = min(1.0, 0.5 + (matches * 0.15))
                topics.append(
                    {
                        "topic": topic,
                        "relevance_score": round(relevance, 2),
                    }
                )

        return topics


google_news_service = GoogleNewsService()
