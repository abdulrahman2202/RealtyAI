#!/usr/bin/env python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tests.test_extractors import *

tests = [
    # DarGlobal
    (
        "darglobal_top_of_astera_returns_model",
        test_darglobal_top_of_astera_returns_model,
    ),
    (
        "darglobal_trump_penthouse_returns_model",
        test_darglobal_trump_penthouse_returns_model,
    ),
    (
        "darglobal_one_of_one_has_required_fields",
        test_darglobal_one_of_one_has_required_fields,
    ),
    (
        "darglobal_extractor_handles_one_of_one_url",
        test_darglobal_extractor_handles_one_of_one_url,
    ),
    ("darglobal_extractor_handles_blog_url", test_darglobal_extractor_handles_blog_url),
    # Wasalt
    ("wasalt_detail_returns_model", test_wasalt_detail_returns_model),
    ("wasalt_detail_has_price_and_currency", test_wasalt_detail_has_price_and_currency),
    ("wasalt_detail_has_bedrooms_and_areas", test_wasalt_detail_has_bedrooms_and_areas),
    ("wasalt_detail_has_location", test_wasalt_detail_has_location),
    ("wasalt_listing_summary_returns_list", test_wasalt_listing_summary_returns_list),
    # Models
    ("wasalt_model_accepts_valid_data", test_wasalt_model_accepts_valid_data),
    ("darglobal_model_accepts_valid_data", test_darglobal_model_accepts_valid_data),
    # Crawler
    ("crawler_dry_run_mode", test_crawler_dry_run_mode),
    ("crawler_deduplication", test_crawler_deduplication),
    ("crawler_produces_json_output", test_crawler_produces_json_output),
]

passed = 0
failed = 0

for name, func in tests:
    try:
        func()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL: {name} - {e}")
        failed += 1

print(f"\n=== Results: {passed} passed, {failed} failed ===")
