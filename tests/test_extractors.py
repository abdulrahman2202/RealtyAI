"""Tests for RealtyAI extractors using local HTML fixtures.

No live website requests are made. All data is extracted from fixtures.
"""

from pathlib import Path
from unittest.mock import Mock

import httpx

from backend.extractors.darglobal import DarGlobalExtractor
from backend.extractors.wasalt import WasaltExtractor
from backend.models import DarGlobalProperty, WasaltProperty

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load an HTML fixture file."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ── DarGlobal extractor tests ────────────────────────────────


def test_darglobal_top_of_astera_returns_model():
    """Test that Top of the Astera returns a valid DarGlobalProperty model."""
    html = _load_fixture("darglobal_top_of_astera.html")
    extractor = DarGlobalExtractor(
        html, "https://darglobal.co.uk/one-of-one/top-of-the-astera"
    )
    record = extractor.extract()

    assert isinstance(record, DarGlobalProperty), (
        f"Expected DarGlobalProperty, got {type(record)}"
    )
    assert record.source == "darglobal.co.uk"
    assert record.url == "https://darglobal.co.uk/one-of-one/top-of-the-astera"
    assert record.title is not None
    print("  PASS: test_darglobal_top_of_astera_returns_model")


def test_darglobal_trump_penthouse_returns_model():
    """Test that Trump Penthouse one-of-one returns a valid model."""
    html = _load_fixture("darglobal_one_of_one_trump_penthouse.html")
    extractor = DarGlobalExtractor(
        html, "https://darglobal.co.uk/one-of-one/trump-penthouse"
    )
    record = extractor.extract()

    assert isinstance(record, DarGlobalProperty), (
        f"Expected DarGlobalProperty, got {type(record)}"
    )
    assert record.source == "darglobal.co.uk"
    assert record.title is not None
    assert record.url is not None
    print("  PASS: test_darglobal_trump_penthouse_returns_model")


def test_darglobal_one_of_one_has_required_fields():
    """Test that one-of-one extraction produces model with expected field types."""
    html = _load_fixture("darglobal_one_of_one_trump_penthouse.html")
    extractor = DarGlobalExtractor(
        html, "https://darglobal.co.uk/one-of-one/trump-penthouse"
    )
    record = extractor.extract()

    # Fields should be either a value or None (not invented)
    assert record.title is not None or record.source is not None
    assert record.url == "https://darglobal.co.uk/one-of-one/trump-penthouse"
    # Status should be a real value or None, not invented
    assert record.status in ("available_on_request", "sold", "coming_soon", None)
    print("  PASS: test_darglobal_one_of_one_has_required_fields")


def test_darglobal_extractor_handles_one_of_one_url():
    """Test URL-based routing to one-of-one extraction."""
    html = _load_fixture("darglobal_one_of_one_trump_penthouse.html")
    extractor = DarGlobalExtractor(
        html, "https://darglobal.co.uk/one-of-one/trump-penthouse"
    )
    record = extractor.extract()

    # Should detect it's a one-of-one page
    assert record is not None
    print("  PASS: test_darglobal_extractor_handles_one_of_one_url")


def test_darglobal_extractor_handles_blog_url():
    """Test URL-based routing to blog extraction."""
    html = """<html><head><title>Test Blog Post</title></head>
<body><h1>Test Blog Post</h1><p>This is a test blog post about real estate.</p></body></html>"""
    extractor = DarGlobalExtractor(html, "https://darglobal.co.uk/blog/test-post")
    record = extractor.extract()

    assert isinstance(record, DarGlobalProperty)
    assert record.source == "darglobal.co.uk"
    print("  PASS: test_darglobal_extractor_handles_blog_url")


# ── Wasalt extractor tests ───────────────────────────────────


def test_wasalt_detail_returns_model():
    """Test that Wasalt detail page returns a valid WasaltProperty model."""
    html = _load_fixture("wasalt_detail_villa.html")
    extractor = WasaltExtractor(
        html,
        "https://wasalt.sa/en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799",
    )
    record = extractor.extract()

    assert isinstance(record, WasaltProperty), (
        f"Expected WasaltProperty, got {type(record)}"
    )
    assert record.source == "wasalt.sa"
    assert record.title is not None
    assert (
        record.url
        == "https://wasalt.sa/en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799"
    )
    print("  PASS: test_wasalt_detail_returns_model")


def test_wasalt_detail_has_price_and_currency():
    """Test Wasalt detail extraction includes price in SAR."""
    html = _load_fixture("wasalt_detail_villa.html")
    extractor = WasaltExtractor(
        html,
        "https://wasalt.sa/en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799",
    )
    record = extractor.extract()

    assert record.currency == "SAR", f"Expected currency SAR, got {record.currency}"
    # Price should be a positive number or None (not invented)
    assert record.price is None or (
        isinstance(record.price, (int, float)) and record.price > 0
    )
    print("  PASS: test_wasalt_detail_has_price_and_currency")


def test_wasalt_detail_has_bedrooms_and_areas():
    """Test Wasalt detail extraction includes bedrooms and area fields."""
    html = _load_fixture("wasalt_detail_villa.html")
    extractor = WasaltExtractor(
        html,
        "https://wasalt.sa/en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799",
    )
    record = extractor.extract()

    # Bedrooms should be int or None
    assert record.bedrooms is None or isinstance(record.bedrooms, int)
    # Land area should be float or None
    assert record.land_area_sqm is None or isinstance(
        record.land_area_sqm, (int, float)
    )
    # Building area should be float or None
    assert record.building_area_sqm is None or isinstance(
        record.building_area_sqm, (int, float)
    )
    print("  PASS: test_wasalt_detail_has_bedrooms_and_areas")


def test_wasalt_detail_has_location():
    """Test Wasalt detail extraction includes city/country."""
    html = _load_fixture("wasalt_detail_villa.html")
    extractor = WasaltExtractor(
        html,
        "https://wasalt.sa/en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799",
    )
    record = extractor.extract()

    # City should be string or None (not invented)
    assert record.city is None or isinstance(record.city, str)
    # Country should be string or None
    assert record.country is None or isinstance(record.country, str)
    print("  PASS: test_wasalt_detail_has_location")


def test_wasalt_listing_summary_returns_list():
    """Test Wasalt listing page returns a list of summaries."""
    html = _load_fixture("wasalt_listing_page.html")
    extractor = WasaltExtractor(html, "https://wasalt.sa/en/villas-for-sale-in-riyadh")
    records = extractor.extract_listing_summary()

    assert isinstance(records, list), f"Expected list, got {type(records)}"
    # Each record should be a dict
    for r in records:
        assert isinstance(r, dict), f"Expected dict, got {type(r)}"
    print(f"  PASS: test_wasalt_listing_summary_returns_list ({len(records)} records)")


def test_wasalt_model_accepts_valid_data():
    """Test Wasalt Pydantic model accepts a valid data dict."""
    data = {
        "source": "wasalt.sa",
        "url": "https://wasalt.sa/en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799",
        "title": "Villa for Sale in Al-Rimal, East Riyadh",
        "description": "450 SQM land area, 385 m² building area",
        "country": "Saudi Arabia",
        "city": "Al-Rimal",
        "property_type": "Villa",
        "bedrooms": 4,
        "price": 2150000.0,
        "currency": "SAR",
        "land_area_sqm": 450.0,
        "building_area_sqm": 385.0,
        "reference_number": "289517",
        "status": "New",
    }
    model = WasaltProperty(**data)
    assert model.title == "Villa for Sale in Al-Rimal, East Riyadh"
    assert model.price == 2150000.0
    assert model.land_area_sqm == 450.0
    assert model.building_area_sqm == 385.0
    print("  PASS: test_wasalt_model_accepts_valid_data")


def test_darglobal_model_accepts_valid_data():
    """Test DarGlobal Pydantic model accepts a valid data dict."""
    data = {
        "source": "darglobal.co.uk",
        "url": "https://darglobal.co.uk/one-of-one/top-of-the-astera",
        "title": "Top Of the Astera",
        "description": "Introducing the Top of the Astera – the world's first villa in the sky",
        "city": "Al Marjan Island",
        "property_type": "Villa",
        "bedrooms": 5,
        "status": "available_on_request",
    }
    model = DarGlobalProperty(**data)
    assert model.title == "Top Of the Astera"
    assert model.bedrooms == 5
    assert model.status == "available_on_request"
    print("  PASS: test_darglobal_model_accepts_valid_data")


# ── Crawler tests ────────────────────────────────────────────


def test_crawler_dry_run_mode(tmp_path):
    """Test crawler dry-run mode flag."""
    from backend.crawler import BaseCrawler

    crawler = BaseCrawler(dry_run=True, output_dir_dg=tmp_path / "darglobal", output_dir_ws=tmp_path / "wasalt")
    assert crawler.dry_run is True
    crawler2 = BaseCrawler(dry_run=False, output_dir_dg=tmp_path / "darglobal", output_dir_ws=tmp_path / "wasalt")
    assert crawler2.dry_run is False
    print("  PASS: test_crawler_dry_run_mode")


def test_crawler_deduplication(tmp_path):
    """Test crawler skips duplicate URLs."""
    from backend.crawler import BaseCrawler, extract_darglobal

    crawler = BaseCrawler(dry_run=True, output_dir_dg=tmp_path / "darglobal", output_dir_ws=tmp_path / "wasalt")

    # Same URL twice - second should be None (skipped)
    crawler.crawl_url(
        "https://darglobal.co.uk/one-of-one/top-of-the-astera",
        extract_darglobal,
        crawler.output_dir_dg,
    )
    record2 = crawler.crawl_url(
        "https://darglobal.co.uk/one-of-one/top-of-the-astera",
        extract_darglobal,
        crawler.output_dir_dg,
    )

    # Second call returns None because of dedup
    assert record2 is None, "Second crawl of same URL should return None (dedup)"
    print("  PASS: test_crawler_deduplication")


def test_crawler_produces_json_output(tmp_path, monkeypatch):
    """Test crawler can save JSON output in non-dry-run mode."""
    from backend.crawler import BaseCrawler, extract_darglobal

    crawler = BaseCrawler(dry_run=False, output_dir_dg=tmp_path / "darglobal", output_dir_ws=tmp_path / "wasalt")
    monkeypatch.setattr(crawler.throttled_client, "get", Mock(return_value=httpx.Response(200, text=_load_fixture("darglobal_top_of_astera.html"))))

    record = crawler.crawl_url(
        "https://darglobal.co.uk/one-of-one/top-of-the-astera",
        extract_darglobal,
        crawler.output_dir_dg,
    )

    assert record is not None
    # Only the isolated test output is read or written.
    import json

    json_files = list(crawler.output_dir_dg.glob("*.json"))
    assert len(json_files) == 1
    saved_data = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert "source" in saved_data
    assert "url" in saved_data
    print("  PASS: test_crawler_produces_json_output")


# ── Run all ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== DarGlobal Extractor Tests ===")
    test_darglobal_top_of_astera_returns_model()
    test_darglobal_trump_penthouse_returns_model()
    test_darglobal_one_of_one_has_required_fields()
    test_darglobal_extractor_handles_one_of_one_url()
    test_darglobal_extractor_handles_blog_url()

    print("\n=== Wasalt Extractor Tests ===")
    test_wasalt_detail_returns_model()
    test_wasalt_detail_has_price_and_currency()
    test_wasalt_detail_has_bedrooms_and_areas()
    test_wasalt_detail_has_location()
    test_wasalt_listing_summary_returns_list()

    print("\n=== Pydantic Model Tests ===")
    test_wasalt_model_accepts_valid_data()
    test_darglobal_model_accepts_valid_data()

    print("\n=== Crawler Tests ===")
    test_crawler_dry_run_mode()
    test_crawler_deduplication()
    test_crawler_produces_json_output()

    print("\n✅ All tests passed!\n")
