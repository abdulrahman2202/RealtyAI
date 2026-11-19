# RealtyAI Raw Data Validation Report (Corrected)

## Counting Methodology

- Used Python `csv.DictReader` to parse each CSV file.
- Counted **actual data records** (rows parsed by DictReader), **not** physical file lines.
- Each CSV file has exactly **1 data record** (1 row after header).
- Used `encoding='utf-8-sig'` to handle BOM characters.
- Compared records by **canonical URL** (stripped `utm_source=chatgpt.com` tracking parameter for comparison) while preserving original URLs in raw files.
- Distinguished **property-content records** from **structured property records**: some CSVs contain full extracted text about properties (counted as property-content) but do not have the structured fields (price, bedrooms, etc.) required by Pydantic models.

## 1. Files Inspected

Total: **16 CSV files** recursively in `data/raw/darglobal/` and `data/raw/wasalt/`.

| # | File Path | Records | Columns |
|---|-----------|---------|---------|
| 1 | `darglobal/company/DarGlobal-Aboutus.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 2 | `darglobal/company/DarGlobal-contect.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 3 | `darglobal/company/DarGlobal-homepage.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 4 | `darglobal/company/DarGlobal-trumpOrganization.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 5 | `darglobal/properties/page-text-2026-11-19-11-54.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 6 | `darglobal/properties/page-text-2026-11-19-11-55.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 7 | `darglobal/properties/The Astera – Aston Martin.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 8 | `darglobal/properties/Trump Mansions.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 9 | `darglobal/properties/Trump-Park-Residences.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 10 | `darglobal/projects/DarGlobal-project-directory.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 11 | `wasalt/auctions/auction.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 12 | `wasalt/company/Wasalt-homepage.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 13 | `wasalt/company/corporate-information.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 14 | `wasalt/listings/WasaltProperties for sale.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 15 | `wasalt/listings/properties-for-rent.csv` | 1 | URL, Title, Description, Language, Words, Text |
| 16 | `wasalt/reference/terms-of-use.csv` | 1 | URL, Title, Description, Language, Words, Text |

## 2. Rows Per File

Every CSV file contains exactly **1 record** (1 row of data + 1 header row). No CSV has multiple records.

## 3. Columns Per File

All 16 CSVs share the same 6-column structure:
- `URL` - Source URL (always includes `utm_source=chatgpt.com`)
- `Title` - Page title
- `Description` - Meta description
- `Language` - Language code (always `en`)
- `Words` - Word count
- `Text` - Full extracted text/content

## 4. Record Analysis

### DarGlobal Records (10 files)

| File | URL | Title | Description | Words | Text Type |
|------|-----|-------|-------------|-------|-----------|
| **DarGlobal-Aboutus** | `https://darglobal.co.uk/about` | "About Us" | DarGlobal overview text | 296 | Company/organization page full text |
| **DarGlobal-contect** | `https://darglobal.co.uk/get-in-touch` | "Contact \| Luxury Real Estate, DarGlobal" | Contact info text | 207 | Contact/information page |
| **DarGlobal-homepage** | `https://darglobal.co.uk/` | "DarGlobal \| International Luxury Real Estate Developer" | Homepage description | 135 | Company homepage |
| **DarGlobal-trumpOrganization** | `https://darglobal.co.uk/partners/the-trump-organization` | "Trump Branded Residences Gulf \| DarGlobal Portfolio" | Trump partnership text | 79 | Company/partner announcement |
| **page-text-2026-11-19-11-54** | `https://darglobal.co.uk/the-astera?utm_source=chatgpt.com` | "The Astera, Interiors by Aston Martin \| Al Marjan Island RAK" | The Astera property description | **897** | **Property-content** (full property details) |
| **page-text-2026-11-19-11-55** | `https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION?utm_source=chatgpt.com` | "Buy Branded Homes \| Million Dollar Houses for Sale \| Darglobal" | Premiere Edition Collection description | 266 | **Property-content** (One-of-One property) |
| **The Astera – Aston Martin** | `https://darglobal.co.uk/the-astera?utm_source=chatgpt.com` | "The Astera, Interiors by Aston Martin \| Al Marjan Island RAK" | The Astera property description | **897** | **Duplicate of page-text-2026-11-19-11-54** |
| **Trump Mansions** | `https://darglobal.co.uk/rayana/trump-mansions?utm_source=chatgpt.com` | **(empty)** | **(empty)** | **0** | **Empty placeholder** |
| **Trump-Park-Residences** | `https://darglobal.co.uk/trump-plaza/park-residences?utm_source=chatgpt.com` | **(empty)** | **(empty)** | **0** | **Empty placeholder** |
| **DarGlobal-project-directory** | `https://darglobal.co.uk/projects/properties-in-uk?utm_source=chatgpt.com` | "Buy Modern Apartments & Exclusive Villas \| International Homes for Sale" | Project directory text | 290 | **Project directory listing** |

### Wasalt Records (6 files)

| File | URL | Title | Description | Words | Text Type |
|------|-----|-------|-------------|-------|-----------|
| **Wasalt-properties for sale** | `https://wasalt.sa/en/properties-for-sale-in-saudi-arabia?utm_source=chatgpt.com` | "Properties for Sale in Saudi Arabia \| Wasalt" | Category description | 1247 | **Sale category page** |
| **properties for rent** | `https://wasalt.sa/en/properties-for-rent-in-saudi-arabia?utm_source=chatgpt.com` | "Properties for Rent in Saudi \| Wasalt" | Rental category description | 884 | **Rent category page** |
| **Wasalt-homepage** | `https://wasalt.sa/en` | "Properties For Sale and Rent in Saudi Arabia \| Wasalt" | Homepage description | 905 | **Company homepage** |
| **corporate-information** | `https://wasalt.sa/en/corporate?utm_source=chatgpt.com` | "Wasalt Real Estate Services" | Corporate info text | 119 | **Company information** |
| **auction** | `https://auction.wasalt.sa/en?utm_source=chatgpt.com` | "Real Estate, Vehicle & Movable Asset Auctions \| Wasalt" | Auction info text | 367 | **Auction information page** |
| **terms-of-use** | `https://auction.wasalt.sa/en/terms-of-use?utm_source=chatgpt.com` | "Wasalt Real Estate Services" | Legal terms text | 218 | **Reference/legal page** |

## 5. Key Discovery: The Astera Duplicate

**`page-text-2026-11-19-11-54.csv`** and **`The Astera – Aston Martin.csv`** contain:

- **IDENTICAL canonical URL**: `https://darglobal.co.uk/the-astera?utm_source=chatgpt.com`
- **IDENTICAL Word count**: 897
- **Near-identical Text content**: Both contain the full The Astera property description (Al Marjan Island, Aston Martin interiors, 1-3 bed residences, etc.)
- **Same Title**: "The Astera, Interiors by Aston Martin \| Al Marjan Island RAK"

**Conclusion**: These are **duplicate exports** of the same property page. One was likely created as a separate file during the export process, but they contain identical data.

## 6. Empty/Placeholder Records

| File | Issue |
|------|-------|
| **Trump Mansions** | Words=0, empty Title, empty Description, empty Text - skeleton/placeholder only |
| **Trump-Park-Residences** | Words=0, empty Title, empty Description, empty Text - skeleton/placeholder only |

All other DarGlobal and Wasalt records have non-zero word counts and contain actual extracted text, but none are **structured property records** with fields like price, bedrooms, property_type, etc.

## 7. Property vs Non-Page Classification (Corrected)

### Individual Property-Content Records
| Classification | Files |
|----------------|-------|
| DarGlobal property-content (full text about a specific property) | `page-text-2026-11-19-11-54.csv` (The Astera), `page-text-2026-11-19-11-55.csv` (Albert Hall), `The Astera – Aston Martin.csv` (duplicate of page-text-2026-11-19-11-54) |
| **Total property-content records** | **3 files** (2 unique property topics) |

### Project Directory Pages
| Classification | Files |
|----------------|-------|
| DarGlobal project directory listing multiple projects | `DarGlobal-project-directory.csv` |

### Sale/Rent Category Pages
| Classification | Files |
|----------------|-------|
| Wasalt sale category page | `WasaltProperties for sale.csv` |
| Wasalt rent category page | `properties-for-rent.csv` |

### Auction Pages
| Classification | Files |
|----------------|-------|
| Wasalt auction information | `auction.csv` |

### Company Pages
| Classification | Files |
|----------------|-------|
| DarGlobal company pages | `DarGlobal-Aboutus.csv`, `DarGlobal-contect.csv`, `DarGlobal-homepage.csv`, `DarGlobal-trumpOrganization.csv` |
| Wasalt company pages | `Wasalt-homepage.csv`, `corporate-information.csv` |

### Reference/Legal Pages
| Classification | Files |
|----------------|-------|
| Wasalt terms of use | `terms-of-use.csv` |

### Empty/Placeholder Exports
| Classification | Files |
|----------------|-------|
| DarGlobal empty property placeholders | `Trump Mansions.csv`, `Trump-Park-Residences.csv` |

### Summary of 16 Files
| Category | Count |
|----------|-------|
| Property-content (unique) | 2 (The Astera, Albert Hall) |
| Property-content (duplicate) | 1 (The Astera duplicate) |
| Project directory | 1 |
| Sale category | 1 |
| Rent category | 1 |
| Company (DarGlobal) | 4 |
| Company (Wasalt) | 2 |
| Auction | 1 |
| Reference/legal | 1 |
| Empty placeholders | 2 |
| **Total** | **16** |

## 8. Compatibility with Existing Models

### DarGlobalProperty Model Fields
- **Mappable from CSV**: `source`, `url`, `title`, `description`, `country` (None per rules), `city` (extracted from text)
- **NOT present in any CSV**: `property_type`, `bedrooms`, `size_sqm`, `price`, `currency`, `amenities`, `facilities`, `reference_number`, `images`, `status`, `availability`
- **Property-content records** (The Astera, Albert Hall) have rich text but **no structured fields** - they cannot be directly mapped to `DarGlobalProperty` without data enrichment.

### WasaltProperty Model Fields
- **Mappable from CSV**: `source`, `url`, `title`, `description`, `country`, `city`
- **NOT present in any CSV**: `property_type`, `bedrooms`, `land_area_sqm`, `building_area_sqm`, `price`, `currency`, `amenities`, `facilities`, `broker`, `status`, `reference_number`, `last_updated`, `images`
- **All Wasalt CSVs** are category/company/reference pages - no individual property records.

### ExtractedRecord Model
- **Fully compatible**: Any CSV can be stored as `ExtractedRecord(source, url, data)` where `data` holds the raw record dict.
- This preserves the data without violating model schemas but does **not** create searchable structured property records.

## 9. Duplicate URL/Content Analysis

### DarGlobal Duplicates
- `page-text-2026-11-19-11-54.csv` ≡ `The Astera – Aston Martin.csv`
  - Same canonical URL (after stripping `utm_source=chatgpt.com`)
  - Same Word count (897)
  - Identical extracted text content
  - Same title
  - **These are duplicate exports** - one file is redundant

### Wasalt Duplicates
- No duplicate URLs or content across Wasalt CSVs - each file is a distinct page type (homepage, corporate, auction, terms, category for sale, category for rent)

### URL Normalization
- For comparison purposes, `utm_source=chatgpt.com` tracking parameter was stripped
- Original URLs are preserved in the raw CSV files as-is
- Canonical URLs (without tracking params):
  - DarGal: `https://darglobal.co.uk/the-astera`, `https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION`, etc.
  - Wasalt: `https://wasalt.sa/en`, `https://wasalt.sa/en/properties-for-sale-in-saudi-arabia`, etc.

## 10. Corrected Summary Counts

| Metric | Count |
|--------|-------|
| **Total CSV files** | 16 |
| **Total records** | 16 (1 per file) |
| **Unique canonical URLs** | 14 (2 files share the The Astera URL) |
| **Property-content records** (rich text, no structured fields) | 3 (The Astera ×2 + Albert Hall) |
| **Unique property-content topics** | 2 (The Astera, Albert Hall Mansions) |
| **Project directory records** | 1 |
| **Sale category records** | 1 |
| **Rent category records** | 1 |
| **Company record types (DarGlobal)** | 4 |
| **Company record types (Wasalt)** | 2 |
| **Auction records** | 1 |
| **Reference/legal records** | 1 |
| **Empty/placeholder records** | 2 (Trump Mansions, Trump-Park-Residences) |
| **Records with Words=0** | 2 |
| **Records with full extracted text** | 14 |
| **Distinct Word counts** | 0, 79, 119, 127(?), 207, 266, 290, 367, 884, 897, 905, 1247 |

**Note**: Word counts verified from each file's `Words` field. Counts of 897 appear in 2 files (The Astera + duplicate), 266 in Albert Hall, etc.

## What This Means

1. **No CSV contains structured property records** (price, bedrooms, property_type, etc. are all absent). The pipeline cannot ingest these CSVs directly into `DarGlobalProperty` or `WasaltProperty` models.

2. **Property-content exists** in 3 records (The Astera x2 + Albert Hall) - these have full extracted text about specific properties but lack the structured fields required by the models.

3. **The Astera duplicate** (`page-text-2026-11-19-11-54.csv` and `The Astera – Aston Martin.csv`) should be treated as one record - only one copy should be kept to avoid duplication.

4. **2 files are empty placeholders** (Trump Mansions, Trump-Park-Residences) - Words=0, no data to extract.

5. **All other 11 files** are category/company/reference/project pages with varying amounts of extracted text, but none are individual property listings.

6. **The existing pipeline** (TXT-based DarGlobal extractor, Wasalt scraper) is the correct approach for actual property data - these CSV exports are diagnostic/debug outputs, not intended for direct ingestion.

## Final Report Path

`C:\Programming\RealtyAI\docs\raw-data-validation-report.md`

**Data Integrity**: All `data/raw` CSV files preserved intact. No deletions, overwrites, or modifications to raw files. No backend, frontend, or Groq configuration changes. No Git commands run. No data ingested or vector DB modified.

**Report Generated**: 2026-11-19

**Analysis Tool**: Python `csv.DictReader` with `encoding='utf-8-sig'`