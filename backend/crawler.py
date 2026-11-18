from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List, Type, Union, Callable

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from backend.models import (
    BaseProperty,
    DarGlobalProperty,
    WasaltProperty,
    ExtractedRecord,
)

# ── Logging configuration ────────────────────────────────────

logger = logging.getLogger("realtyai")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ── Crawler configuration ────────────────────────────────────

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
MIN_DELAY_BETWEEN_REQUESTS = 1.0  # seconds, per domain
MAX_CONCURRENT = 1

# HTTP error codes we'll retry on
RETRYABLE_STATUS_CODES = {500, 502, 503, 504, 408, 429}


# ── Retry decorator ──────────────────────────────────────────


def _is_retryable(httpx_exc: Any) -> bool:
    """Check if an exception is retryable."""
    if isinstance(httpx_exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if (
        hasattr(httpx_exc, "status_code")
        and httpx_exc.status_code in RETRYABLE_STATUS_CODES
    ):
        return True
    return False


retry_decorator = retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_is_retryable),
)


# ── Core fetcher ─────────────────────────────────────────────


class ThrottledClient:
    """HTTP client with per-domain rate limiting."""

    def __init__(self, min_delay: float = MIN_DELAY_BETWEEN_REQUESTS) -> None:
        self.min_delay = min_delay
        self.last_request_time: dict[str, float] = {}
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout=DEFAULT_TIMEOUT),
        )

    def _throttle(self, url: str) -> None:
        """Enforce minimum delay between requests to same domain."""
        domain = urlparse(url).netloc
        now = time.time()
        last = self.last_request_time.get(domain, 0)
        elapsed = now - last
        if elapsed < self.min_delay:
            sleep_time = self.min_delay - elapsed
            logger.debug(f"Throttling: sleeping {sleep_time:.2f}s for {domain}")
            time.sleep(sleep_time)
        self.last_request_time[domain] = time.time()

    @retry_decorator
    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET request with retry and throttling."""
        self._throttle(url)
        try:
            resp = self.client.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRYABLE_STATUS_CODES:
                logger.warning(
                    f"Retryable HTTP error {e.response.status_code} for {url}"
                )
                raise
            raise


# ── Crawler base ─────────────────────────────────────────────


class BaseCrawler:
    """Reusable crawler foundation supporting DarGlobal and Wasalt."""

    def __init__(
        self,
        dry_run: bool = True,
        respect_robots: bool = True,
        output_dir_dg: Optional[Path] = None,
        output_dir_ws: Optional[Path] = None,
    ) -> None:
        self.dry_run = dry_run
        self.respect_robots = respect_robots
        self.throttled_client = ThrottledClient()
        self.output_dir_dg = output_dir_dg or Path("data/processed/darglobal")
        self.output_dir_ws = output_dir_ws or Path("data/processed/wasalt")
        self.seen_urls: set[str] = set()
        self.total_processed = 0
        self.total_skipped = 0
        self.total_errors = 0

        # Ensure output directories exist
        self.output_dir_dg.mkdir(parents=True, exist_ok=True)
        self.output_dir_ws.mkdir(parents=True, exist_ok=True)

    # ── Public API ──────────────────────────────────────────

    def crawl_url(
        self,
        url: str,
        extractor_func: Callable[[str, str], BaseProperty],
        output_dir: Path,
        filename_pattern: str = "{uuid}.json",
    ) -> Optional[ExtractedRecord]:
        """Crawl a single URL, extract data, and save.

        Args:
            url: Full URL to crawl
            extractor_func: Function(html, url) -> BaseProperty
            output_dir: Directory to write JSON output
            filename_pattern: Filename pattern (uses url hash by default)

        Returns:
            ExtractedRecord if successful, None on skip
        """
        # Deduplication check
        if url in self.seen_urls:
            logger.debug(f"Skipping duplicate URL: {url}")
            self.total_skipped += 1
            return None

        self.seen_urls.add(url)
        logger.info(f"Crawling: {url}")

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would fetch {url} (skipping live request per test requirements)"
            )
            # In dry run mode, use the extractor directly with fixture data approach.
            # Since tests provide HTML via extractor_func, we simulate by calling
            # the extractor with a placeholder - the actual test will provide pre-loaded HTML.
            try:
                # Do NOT make a live request in dry run mode
                # Instead, return None to indicate "would process if HTML provided"
                # The test infrastructure handles actual extraction from fixtures
                self.total_processed += 1
                return None  # Dry run: skip, test uses real fetch path
            except Exception as e:
                logger.error(f"Error in dry run for {url}: {e}")
                self.total_errors += 1
                return None

        # Real fetch
        try:
            resp = self.throttled_client.get(url)
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            self.total_errors += 1
            return None

        # Extract data
        try:
            record = extractor_func(resp.text, url)
        except Exception as e:
            logger.error(f"Extraction error for {url}: {e}")
            self.total_errors += 1
            return None

        # Validate with Pydantic model
        if not isinstance(record, BaseProperty):
            logger.error(
                f"Extractor did not return BaseProperty subclass, got {type(record)}"
            )
            self.total_errors += 1
            return None

        # Save to JSON
        try:
            out_path = output_dir / filename_pattern.format(
                uuid=int(hashlib(url)) % 1000000  # simple hash-based naming
            )
            # Use model_dump for JSON serialization
            data = record.model_dump(
                mode="json", exclude={"extracted_at", "source", "url"}
            )
            # Add source and URL back
            data["source"] = record.source
            data["url"] = record.url
            data["extracted_at"] = (
                record.extracted_at.isoformat()
                if record.extracted_at
                else datetime.utcnow().isoformat()
            )

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"Saved: {out_path}")
            self.total_processed += 1
            return record

        except Exception as e:
            logger.error(f"Save error for {url}: {e}")
            self.total_errors += 1
            return None

    def crawl_urls(
        self,
        urls: list[str],
        extractor_dg: Callable[[str, str], BaseProperty],
        extractor_ws: Callable[[str, str], BaseProperty],
        sources: Optional[list[str]] = None,
    ) -> list[ExtractedRecord]:
        """Crawl multiple URLs, dispatching to appropriate extractor.

        Args:
            urls: List of URLs to crawl
            extractor_dg: DarGlobal extractor function
            extractor_ws: Wasalt extractor function
            sources: Optional list of source names ("darglobal" or "wasalt")

        Returns:
            List of ExtractedRecord objects
        """
        records: list[ExtractedRecord] = []
        sources = sources or ["darglobal", "wasalt"]

        for i, url in enumerate(urls):
            # Determine source
            if sources and i < len(sources):
                source_name = sources[i]
            elif "darglobal.co.uk" in url:
                source_name = "darglobal"
            elif "wasalt.sa" in url:
                source_name = "wasalt"
            else:
                source_name = "unknown"

            # Select extractor
            if source_name == "darglobal":
                extractor = extractor_dg
                output_dir = self.output_dir_dg
            elif source_name == "wasalt":
                extractor = extractor_ws
                output_dir = self.output_dir_ws
            else:
                logger.warning(f"Unknown source for URL: {url}")
                continue

            record = self.crawl_url(url, extractor, output_dir)
            if record is not None:
                records.append(record)

            # Progress logging
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(urls)} URLs processed")

        return records


def hashlib_url(url: str) -> int:
    """Simple hash function for generating filenames."""
    import hashlib

    return int(hashlib.sha256(url.encode()).hexdigest(), 16) % (10**6)


# ── Convenience extractor wrappers ──────────────────────────


def extract_darglobal(html: str, url: str) -> BaseProperty:
    """Wrapper for DarGlobal extractor."""
    from backend.extractors.darglobal import DarGlobalExtractor

    return DarGlobalExtractor(html, url).extract()


def extract_wasalt(html: str, url: str) -> BaseProperty:
    """Wrapper for Wasalt extractor."""
    from backend.extractors.wasalt import WasaltExtractor

    return WasaltExtractor(html, url).extract()
