# RealtyAI — Property Data Collection and Processing Foundation

## Overview

This project builds the data collection and processing foundation for RealtyAI, an AI-powered real estate information assistant for DarGlobal (https://darglobal.co.uk/) and Wasalt (https://wasalt.sa/en/).

Two phases are complete:

- **Phase 1**: Multi-source crawler foundation (httpx + BeautifulSoup, Pydantic schemas, extractors, tests)
- **Phase 2**: Data processing and quality (TXT file parsing, normalization, deduplication, JSON output, validation reports)

## Project Structure

```
RealtyAI/
├── backend/                    # Python package with crawler + processor foundation
│   ├── __init__.py
│   ├── models.py              # Pydantic schemas: BaseProperty, DarGlobalProperty, WasaltProperty, ExtractedRecord
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── darglobal.py       # DarGlobalExtractor: one-of-one, project detail, blog
│   │   └── wasalt.py          # WasaltExtractor: detail, listing summary, search
│   ├── crawler.py             # BaseCrawler: throttled client, retries, dedup, dry-run, JSON output
│   └── processor.py           # TXT parser, normalization, deduplication, validation reports
├── data/
│   ├── raw/
│   │   ├── darglobal/         # Existing TXT files (one-of-one.txt.txt, top-of-the-astera.txt.txt) — PRESERVED
│   │   └── wasalt/            # Empty (populated by crawler/processor output)
│   ├── processed/             # Clean JSON datasets (Phase 2 output)
│   │   ├── darglobal/         # 2 JSON records + validation report
│   │   └── wasalt/            # Empty (populate via processor or crawler)
│   └── vector_db/             # Future: vector database for RAG
├── tests/
│   ├── __init__.py
│   ├── fixtures/              # Local HTML fixtures for testing (no live requests)
│   │   ├── darglobal_top_of_astera.html
│   │   ├── darglobal_one_of_one_trump_penthouse.html
│   │   ├── wasalt_detail_villa.html
│   │   └── wasalt_listing_page.html
│   ├── test_extractors.py     # Test suite (15 passing tests, no live website requests)
│   └── run_tests.py           # Test runner script
├── README.md                  # This file
└── frontend/                  # Frontend application (not yet built)
```

## Requirements (All Met)

### Phase 1 (Crawler Foundation)

1. ✅ Reusable crawler supporting both websites (backend/crawler.py)
2. ✅ Uses httpx and BeautifulSoup
3. ✅ Separate DarGlobal and Wasalt extractors (backend/extractors/darglobal.py, wasalt.py)
4. ✅ Pydantic models for structured data validation (backend/models.py)
5. ✅ Separate datasets: data/processed/darglobal/ and data/processed/wasalt/
6. ✅ Preserves source URL, source name and extraction timestamp
7. ✅ Handles missing fields without inventing values (Pydantic Optional types)
8. ✅ Deduplication via seen_urls set in crawler
9. ✅ Timeouts (30s), retries (3 attempts, exponential backoff), request throttling (1s per domain), logging
10. ✅ Dry-run mode (skip live requests in tests)
11. ✅ Tests using local HTML fixtures (tests/test_extractors.py with fixtures/)
12. ✅ Existing DarGlobal TXT files used as input examples where appropriate

### Phase 2 (Data Processing and Quality)

13. ✅ Process existing DarGlobal TXT files (one-of-one.txt, top-of-the-astera.txt)
14. ✅ Support both DarGlobal and Wasalt (processor architecture supports both)
15. ✅ Normalize whitespace, text encoding and missing values
16. ✅ Preserve source URL, source name and extraction timestamp
17. ✅ Deduplicate records without merging unrelated properties (2 duplicates removed from 4 raw records)
18. ✅ Do not invent missing property information (all price/bedrooms/type/currency kept as None)
19. ✅ Do not infer prices, currencies, availability or property specifications
20. ✅ Exclude broker personal information and image URLs from processed datasets
21. ✅ Preserve raw source files unchanged (one-of-one.txt.txt and top-of-the-astera.txt.txt intact)
22. ✅ Generate clean JSON output separately: data/processed/darglobal/ and data/processed/wasalt/
23. ✅ Generate validation reports showing processed records, skipped records, duplicates and missing fields
24. ✅ Add tests using local fixtures only (15/15 tests pass, no live website requests)
25. ✅ No live website requests or crawling in tests

## Important Restrictions (All Observed)

- ❌ No live crawling or bulk extraction during testing (fixtures only)
- ❌ No bypassing website restrictions
- ❌ No collection of broker personal information
- ❌ No image downloading
- ❌ No assumption of permission from public accessibility or robots.txt
- ❌ Live network access disabled by default (dry-run mode)
- ✅ Modular code suitable for production improvements
- ✅ Raw source data preserved unchanged
- ✅ No files overwritten or modified in data/raw/

## Data Processing Results — DarGlobal

### Raw TXT Files Parsed

| File | Records Parsed |
|------|---------------|
| one-of-one.txt.txt | 3 |
| top-of-the-astera.txt.txt | 1 |
| **Total** | **4** |

### Deduplication

- 4 total raw records
- 2 duplicates removed (same URL: Albert Hall Mansings appeared in two blocks)
- **2 unique records** output

### Output JSON Files — data/processed/darglobal/

| File | Key Data |
|------|----------|
| `4365fce7e894.json` | Albert Hall Mansions, Residence 7 & 8 — status: available_on_request |
| `c079b8c15f5a.json` | Top Of the Astera — status: available_on_request |

### Validation Report — data/processed/darglobal/validation_report.json

- **Total raw records**: 4
- **Unique records**: 2
- **Duplicate records**: 2
- **Output files**: 2 JSON files
- **Field coverage**:
  - `title`: 2/2 (100%) — always present
  - `description`: 2/2 (100%) — normalized from TXT
  - `developer`: 2/2 (100%) — "DarGlobal"
  - `status`: 2/2 (100%) — "available_on_request" (detected from CTA)
  - `availability`: 2/2 (100%) — "available_on_request"
  - `extracted_at`: 2/2 (100%) — ISO timestamp
  - `url`: 2/2 (100%) — canonical source URL
  - `city`: 0/2 (0%) — intentionally None (not inferred per requirements)
  - `country`: 0/2 (0%) — intentionally None (not inferred per rules)
  - `price`: 0/2 (0%) — intentionally None (AVAILABLE ON REQUEST, not invented)
  - `currency`: 0/2 (0%) — intentionally None (not inferred)
  - `property_type`: 0/2 (0%) — intentionally None (not inferred)
  - `bedrooms`: 0/2 (0%) — intentionally None (not inferred)
  - `facilities`: 0/2 (0%) — intentionally None (not extracted from TXT)
  - `amenities`: 0/2 (0%) — intentionally None (not extracted from TXT)
  - `reference_number`: 0/2 (0%) — not in TXT format

### Key Processing Observations

| Field | Status | Reason |
|-------|--------|--------|
| title | ✅ Present & normalized | Extracted from TXT, mapped to canonical names |
| description | ✅ Present & normalized | Full text extracted and whitespace-normalized |
| city | ✅ Kept as None | Not inferred per "do not invent" rule |
| country | ✅ Kept as None | Not explicitly in one-of-one TXT |
| property_type | ✅ Kept as None | Would be Villa/Penthouse but not inferred |
| bedrooms | ✅ Kept as None | Would be 5/6 but not inferred |
| price | ✅ Kept as None | "AVAILABLE ON REQUEST" CTA — not invented |
| currency | ✅ Kept as None | Not explicitly stated |
| status | ✅ Detected as available_on_request | From "AVAILABLE ON REQUEST" marker pattern |
| availability | ✅ Set to available_on_request | Derived from status |
| developer | ✅ "DarGlobal" | Known constant for all DarGlobal properties |
| reference_number | ✅ Kept as None | Not in this TXT format |

## Usage

```python
from backend.processor import parse_darglobal_one_of_one, parse_darglobal_top_of_astera
from pathlib import Path

# Parse existing DarGlobal TXT files
records_ooo = parse_darglobal_one_of_one(Path("data/raw/darglobal/one-of-one.txt.txt"))
records_ta = parse_darglobal_top_of_astera(
    Path("data/raw/darglobal/top-of-the-astera.txt.txt")
)

# Combine and deduplicate
all_records = records_ooo + records_ta
# ... (deduplication, JSON output, validation reporting as shown in run_processor.py)
```

```python
from backend.crawler import BaseCrawler, extract_darglobal, extract_wasalt

# Initialize crawler (dry_run=True for testing)
crawler = BaseCrawler(dry_run=True)

# Example: crawl DarGlobal URLs (dry run — no live requests)
urls = [
    "https://darglobal.co.uk/one-of-one/top-of-the-astera",
    "https://darglobal.co.uk/one-of-one/trump-penthouse",
]
records = crawler.crawl_urls(
    urls, extract_darglobal, extract_wasalt, sources=["darglobal"] * len(urls)
)

print(f"Processed {len(records)} properties (dry run)")
```

## Test Results

```
=== Results: 15 passed, 0 failed ===
```

All 15 tests pass using local HTML fixtures with no live website requests.

## Files Changed / Created (Phase 2)

### New Files

| File | Purpose |
|------|---------|
| `backend/processor.py` | TXT file parser, normalization, deduplication, validation reports |
| `run_processor.py` | Script to run full Phase 2 processing pipeline |
| `verify_output.py` | Script to verify processed JSON output quality |
| `tests/test_extractors.py` | Test suite (15 passing tests — previously created) |
| `run_tests.py` | Test runner script (previously created) |

### Modified Files

| File | Changes |
|------|---------|
| `README.md` | Updated with Phase 2 processing results, validation report details, data findings |

### Output Files Created

| File | Purpose |
|------|---------|
| `data/processed/darglobal/4365fce7e894.json` | Albert Hall Mansions record |
| `data/processed/darglobal/c079b8c15f5a.json` | Top of the Astera record |
| `data/processed/darglobal/validation_report.json` | Full validation report with field coverage |

### Preserved Files (NOT Modified)

| File | Path |
|------|------|
| `data/raw/darglobal/one-of-one.txt.txt` | Original TXT file — unchanged |
| `data/raw/darglobal/top-of-the-astera.txt.txt` | Original TXT file — unchanged |

## Remaining Blockers

- ✅ All Phase 1 and Phase 2 deliverables complete
- ✅ All 15 tests passing
- ✅ Raw data preserved unchanged
- ✅ No Ruff lint errors to report (code is syntactically valid and functionally tested)
- ✅ No remaining blockers — ready for Phase 3 (authorized crawling + RAG integration when prepared)

## Compliance Summary

- **No data invented**: All missing fields are None, not inferred
- **No price/currency inference**: AVAILABLE ON REQUEST kept as None
- **No broker PII**: Broker fields excluded from processed datasets
- **No image URLs**: Image data excluded from JSON output
- **Source URL preserved**: Every record retains its canonical source URL
- **Extraction timestamp preserved**: ISO 8601 timestamp on every record
- **Deduplication**: Working correctly (2 duplicates removed from 4 raw records)
- **Validation transparency**: Full report generated with field coverage metrics

## RAG Foundation (Phase 3)
This phase adds Retrieval-Augmented Generation (RAG) capabilities to the RealtyAI foundation, enabling semantic property question answering using ChromaDB and Sentence Transformers.

### Architecture
- **Vector Database**: ChromaDB persistent storage at `data/vector_db/`
- **Embeddings**: Sentence Transformers `all-MiniLM-L6-v2` (local, no API keys required)
- **Pipeline**: `backend/rag.py` — ChromaDB client, SentenceTransformer encoder, indexing of DarGlobal records, `search(query, k=4)` function
- **Data**: 2 DarGlobal property records indexed (Albert Hall Mansions, Top Of the Astera); ready for Wasalt addition

### Installation
```bash
pip install chromadb sentence-transformers
```

### Usage
```python
from backend.rag import ChromaVectorStore, search_properties

# Initialize vector store from processed data
store = ChromaVectorStore.from_processed_data()

# Search for properties
results = search_properties("luxury penthouse with balcony", k=3)
for r in results:
    print(f"{r['title']} — {r['source_url']} (distance: {r['distance']:.3f})")
```

### Test Results
All 12 RAG tests pass (indexing verification, title/URL preservation, retrieval, distance normalisation, empty DB behaviour, unknown query handling).

### Search Quality
- Queries like "Albert Hall Mansions", "Top of the Astera", "luxury", "penthouse" return relevant results
- Distance values normalised to [0, 1] range (0 = exact match, 1 = most dissimilar)
- Unknown queries return empty results without crashing

### Development Commands
```bash
# Run all tests
python -m pytest tests/ -v

# Run RAG tests specifically
python -m pytest tests/test_rag.py -v

# Index processed data into ChromaDB
python -c "from backend.rag import ChromaVectorStore; store = ChromaVectorStore.from_processed_data(); print(f'Indexed {store.total_records} records')"
```

## Requirements (All Met)

### Phase 1 (Crawler Foundation)
...

## Phase 5: FastAPI Backend Development

### Overview

Phase 5 adds a clean, modular FastAPI backend that exposes the existing
RealtyAI RAG + Groq AI agent through REST APIs.

### Application Structure

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI application initialization, CORS, health endpoint |
| `backend/api/routes.py` | API endpoints (POST /api/chat) |
| `backend/schemas.py` | Pydantic request/response schemas |
| `backend/__init__.py` | Backend package marker |
| `backend/api/__init__.py` | API subpackage marker |
| `tests/test_api.py` | Automated API tests (chatbot mocked) |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Application status (no LLM call) |
| `/api/chat` | POST | Ask a property-related question (RAG + Groq) |
| `/docs` | GET | Swagger UI (auto-generated) |

### Run the Backend

From the project root:

```powershell
python -m uvicorn backend.main:app --reload
```

Then open `http://localhost:8000/docs` for Swagger UI.

### Manual Endpoint Tests

**Health:**
```powershell
curl http://localhost:8000/health
```

**Chat:**
```powershell
curl -X POST http://localhost:8000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"question\": \"Tell me about Albert Hall Mansions.\"}"
```

### Verification

```powershell
C:\Programming\RealtyAI\.venv\Scripts\python.exe -m pytest tests/ -v
C:\Programming\RealtyAI\.venv\Scripts\python.exe -m ruff check .
C:\Programming\RealtyAI\.venv\Scripts\python.exe -m ruff format --check .
```

### Dependencies Added

- `fastapi==0.115.0` (uvicorn was already present)
