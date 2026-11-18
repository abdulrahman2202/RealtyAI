from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from backend.models import (
    BaseProperty,
    DarGlobalProperty,
    WasaltProperty,
    ExtractedRecord,
)


# ── Whitespace / encoding normalization ──────────────────────


def normalize_whitespace(text: Optional[str]) -> Optional[str]:
    """Normalize whitespace: trim, collapse internal runs, preserve meaningful single spaces."""
    if not text:
        return None
    # Strip leading/trailing whitespace
    text = text.strip()
    # Collapse runs of whitespace (including \n, \r, \t) to single space
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_encoding(text: Any) -> Optional[str]:
    """Ensure text is valid UTF-8 string; replace problematic chars."""
    if text is None:
        return None
    if isinstance(text, bytes):
        try:
            return text.decode("utf-8")
        except UnicodeDecodeError:
            return text.decode("utf-8", errors="replace")
    if isinstance(text, str):
        return text
    # Fallback: string representation
    return str(text)


# ── Helper: check if a line looks like a property name ──────────


def _is_property_name_line(text: str) -> bool:
    """Determine if a text line looks like a property/project name.

    Heuristics:
    - Not empty
    - Not "AVAILABLE ON REQUEST"
    - Not "Discover"
    - Not purely numeric
    - Starts with uppercase letter
    - Has meaningful length (not just a few chars)
    - Contains alphabetic characters (not just symbols)
    """
    if not text or not text.strip():
        return False
    stripped = text.strip()

    # Skip noise phrases
    if stripped.upper().startswith("AVAILABLE ON REQUEST"):
        return False
    if stripped.startswith("Discover"):
        return False
    if len(stripped) < 3:
        return False

    # Must start with uppercase
    if not stripped[0].isupper():
        return False

    # Must contain alphabetic characters (not just symbols/nums)
    if not any(c.isalpha() for c in stripped):
        return False

    # Should not be all caps short phrase (likely a heading, not a name)
    # e.g., "SOLD" or "COMING SOON" are excluded by the AVAILABLE check above
    # But very short all-caps like "USA" could be a location - be conservative
    if len(stripped) <= 4 and stripped == stripped.upper():
        # Allow short location codes in context, but skip here
        return False

    return True


def _find_property_name(block: list[str]) -> Optional[str]:
    """Find the property name from a block of TXT file lines.

    Each block has varying structure. Look for lines that property name
    heuristics identify as property names.
    """
    for line in block:
        line_stripped = line.strip()
        if _is_property_name_line(line_stripped):
            return line_stripped
    return None


# ── DarGlobal TXT file parser ────────────────────────────────


def parse_darglobal_one_of_one(filepath: path) -> list[dict[str, Any]]:
    """Parse the DarGlobal one-of-one.txt file.

    Property blocks are demarcated by "Discover" lines in the TXT file.
    Does NOT invent missing property information (price, bedrooms, property type,
    currency are all kept as None per requirements).
    Excludes image URLs and broker personal information.
    """
    if not filepath.exists():
        return []

    with filepath.open("r", encoding="utf-8") as f:
        content = f.read()

    records: list[dict[str, Any]] = []
    lines = content.splitlines()

    # ── Step 1: Split into blocks separated by "Discover" lines ────────
    blocks: list[list[str]] = []
    current_block_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Discover"):
            if current_block_lines:
                blocks.append(current_block_lines)
                current_block_lines = []
        else:
            current_block_lines.append(stripped)

    if current_block_lines:
        blocks.append(current_block_lines)

    # ── Step 2: Process each block (skip block 0 = collection header) ────
    for block_idx, block in enumerate(blocks):
        # Skip the collection header (block 0: "Buy Branded Homes..." covering page)
        if block_idx == 0:
            continue

        # Find the property name from the block
        property_name = _find_property_name(block)
        if not property_name:
            # No recognizable property name in this block - skip
            continue

        # ── Determine URL based on property name ──────────────────────
        # Map known property names from the one-of-one collection to full URLs
        url: Optional[str] = None

        # Direct name->URL mappings (exact matches first)
        name_to_url: dict[str, str] = {
            "AIDA | Oman": "https://darglobal.co.uk/one-of-one",
            "Azure Oceanfront Villas Interiors by Fendi Casa": "https://darglobal.co.uk/one-of-one/fendi-casa-azure-oceanfront-villas",
            "THE ALBERT HALL MANSION": "https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION",
            "The Trump Penthouse": "https://darglobal.co.uk/one-of-one/trump-penthouse",
            "Unlisted With Interiors By Pagani": "https://darglobal.co.uk/one-of-one/one-of-one-unlisted-by-pagani",
            "Overlooking Hyde Park, London, England": "https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION",
            "Al Marjan Island, RAK, UAE": "https://darglobal.co.uk/one-of-one/top-of-the-astera",
            "Unlisted are the only two villas in the world fitted with interiors by Pagani": "https://darglobal.co.uk/one-of-one/one-of-one-unlisted-by-pagani",
            "Painite Villas Design Inspired by Automobili Lamborghini": "https://darglobal.co.uk/one-of-one/painite-villas-design-inspired-by-Automobili-Lamborghini",
            "Benavís, Spain": "https://darglobal.co.uk/one-of-one/painite-villas-design-inspired-by-Automobili-Lamborghini",
        }

        # Try exact match first
        if property_name in name_to_url:
            url = name_to_url[property_name]
        else:
            # Try partial/pattern matching
            prop_lower = property_name.lower()
            if "trump penthouse" in prop_lower or "trump-penthouse" in prop_lower:
                url = "https://darglobal.co.uk/one-of-one/trump-penthouse"
            elif "painite" in prop_lower:
                url = "https://darglobal.co.uk/one-of-one/painite-villas-design-inspired-by-Automobili-Lamborghini"
            elif "fendi" in prop_lower:
                url = "https://darglobal.co.uk/one-of-one/fendi-casa-azure-oceanfront-villas"
            elif "albert hall" in prop_lower:
                url = "https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION"
            elif "astera" in prop_lower:
                url = "https://darglobal.co.uk/one-of-one/top-of-the-astera"
            elif "unlisted" in prop_lower:
                url = "https://darglobal.co.uk/one-of-one/one-of-one-unlisted-by-pagani"
            elif "premiere edition" in prop_lower or "branded homes" in prop_lower:
                url = "https://darglobal.co.uk/one-of-one"

        # Skip if no URL can be determined (do not invent URLs)
        if not url:
            continue

        # ── Determine status from "AVAILABLE ON REQUEST" marker ────────
        status: Optional[str] = None
        availability: Optional[str] = None

        # Check if "AVAILABLE ON REQUEST" appears in this block
        block_text = " ".join(block).upper()
        if "AVAILABLE ON REQUEST" in block_text:
            status = "available_on_request"
            availability = "available_on_request"
        # Check for SOLD (without AVAILABLE ON REQUEST)
        if "SOLD" in block_text and "AVAILABLE ON REQUEST" not in block_text:
            if status is None:
                status = "sold"
                availability = "sold"
        # Check for COMING SOON
        if "COMING SOON" in block_text:
            if status is None:
                status = "coming_soon"
                availability = "coming_soon"

        # ── Extract city/location ────────────────────────────────────
        # Look for city in the block lines - check for "|"-separated format
        # or location patterns like "Dubai, UAE"
        city: Optional[str] = None

        # Primary: check the property name line itself for "|" format
        if "|" in property_name:
            parts = [p.strip() for p in property_name.split("|")]
            if len(parts) >= 2:
                city = parts[0]  # First part is city/location

        # Secondary: check other lines in the block for location patterns
        if city is None:
            for line in block:
                line_stripped = line.strip()
                # Pattern: "Dubai, UAE" or "Al Marjan Island, RAK, UAE"
                if re.search(r"[A-Z][a-z]+,\s*[A-Z](?:[a-z]+\s*)*UAE", line_stripped):
                    city = line_stripped
                    break
                # Also check for "City, Region" patterns with other countries
                if re.search(
                    r"[A-Z][a-z]+,\s*[A-Za-z]+\s*(UAE|UK|USA|Spain|Oman|Qatar)$",
                    line_stripped,
                ):
                    city = line_stripped
                    break

        # ── Extract description ────────────────────────────────────────
        # Description is the substantial text in the block after the property name
        # and before "AVAILABLE ON REQUEST" or "Discover" markers
        description_parts: list[str] = []

        # Collect description lines: skip empties, "AVAILABLE ON REQUEST", "Discover"
        # Start after the property name line
        found_name = False
        for line in block:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            if line_stripped == property_name:
                found_name = True
                continue  # Skip the name line itself
            if not found_name:
                # Before we find the name, skip (shouldn't happen but safety)
                continue
            # After finding the name, accumulate description
            if line_stripped == "AVAILABLE ON REQUEST":
                # Description ends at AVAILABLE ON REQUEST
                found_name = False  # Reset for next block consideration
                continue
            if line_stripped.startswith("Discover"):
                found_name = False  # Description ends at Discover
                continue
            # Accumulate description text
            if line_stripped and line_stripped not in (
                "AVAILABLE ON REQUEST",
                "Discover",
            ):
                # Filter out very short noise lines
                if len(line_stripped) > 3:
                    description_parts.append(line_stripped)

        # Normalize description
        description = (
            normalize_whitespace(" ".join(description_parts))
            if description_parts
            else None
        )

        # ── Build the record ──────────────────────────────────────────
        # Map known property names to canonical titles
        title_map: dict[str, str] = {
            "A WORLD OF ONE'S OWN": "Premiere Edition Collection",
            "AIDA | Oman": "AIDA | Oman",
            "Azure Oceanfront Villas Interiors by Fendi Casa": "Fendi Casa Azure Oceanfront Villas",
            "THE ALBERT HALL MANSION": "Albert Hall Mansions",
            "The Trump Penthouse": "Trump Penthouse",
            "Unlisted With Interiors By Pagani": "Unlisted With Interiors By Pagani",
            "Overlooking Hyde Park, London, England": "7&8 Albert Hall Mansions",
            "Al Marjan Island, RAK, UAE": "Top Of the Astera",
            "Painite Villas Design Inspired by Automobili Lamborghini": "Painite Villas",
            "Benavís, Spain": "Painite Villas",
        }

        # Use the property name as title, mapped if known
        title = property_name
        if title in title_map:
            title = title_map[title]

        record = {
            "source": "darglobal.co.uk",
            "url": url,
            "title": normalize_whitespace(title),
            "description": description,
            "city": normalize_whitespace(city) if city else None,
            "country": None,  # Not explicitly stated in one-of-one TXT; keep None per "do not infer" rule
            "property_type": None,  # Not inferred per requirements
            "bedrooms": None,  # Not inferred per requirements
            "price": None,  # "AVAILABLE ON REQUEST" - keep as None, don't invent price
            "currency": None,  # Not inferred per requirements
            "amenities": None,  # Not extracted from TXT per "do not invent" rule
            "facilities": None,  # Not extracted from TXT per "do not invent" rule
            "developer": "DarGlobal",  # Known developer for all DarGlobal properties
            "status": status,
            "availability": availability,
            "reference_number": None,  # Not in this TXT format
            "extracted_at": datetime.now(UTC).isoformat() + "Z",
        }

        records.append(record)

    return records


def parse_darglobal_top_of_astera(filepath: Path) -> list[dict[str, Any]]:
    """Parse the DarGlobal top-of-the-astera.txt file.

    Returns list of dicts with extracted fields.
    Follows "do not invent" rule: no inferred prices, currencies, bedroom counts,
    property types beyond what's explicitly in the text.
    """
    if not filepath.exists():
        return []

    with filepath.open("r", encoding="utf-8") as f:
        content = f.read()

    records: list[dict[str, Any]] = []
    lines = content.splitlines()

    # This file contains one property: Top of the Astera
    # Verified structure from reconnaissance.

    title = None
    description_parts: list[str] = []
    city = None
    status = None
    availability = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Title detection
        if line == "Top Of the Astera":
            title = "Top Of the Astera"

        # City/location from "|"-separated line
        if "|" in line and city is None:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                # Only accept if the first part is NOT a header/intro phrase
                # "Buy Branded Homes" etc. are collection headers, not city names
                first_part = parts[0]
                # Skip if it looks like a collection header or marketing phrase
                skip_phrases = {
                    "buy branded homes",
                    "million dollar houses",
                    "for sale",
                    "darglobal",
                    "premiere edition",
                }
                if first_part.lower() not in skip_phrases:
                    city = first_part

        # Description accumulation: skip headings, keep relevant text
        skip_headings = {
            "A World First",
            "Beyond the Clouds",
            "ELEVATE YOUR WORLD",
            "THE LIVING SPACES",
            "LOCATION",
        }
        if line not in skip_headings and line not in (
            "AVAILABLE ON REQUEST",
            "Discover",
        ):
            # Keep text lines that are substantial and not noise
            if line and len(line) > 5:
                description_parts.append(line)

        # Status detection
        if "COMING SOON" in line:
            status = "coming_soon"
        if "SOLD" in line:
            status = "sold"

        # Availability: based on "AVAILABLE ON REQUEST" pattern in the file
        # The file consistently has "AVAILABLE ON REQUEST" as CTA
        window_text = " ".join(lines).upper()
        if "AVAILABLE ON REQUEST" in window_text and availability is None:
            availability = "available_on_request"

        i += 1

    if title:
        # Join description parts and clean
        raw_description = " ".join(description_parts)
        description = normalize_whitespace(raw_description)

        # Remove redundant "A World First" etc. that might have been included
        # (already handled by skip_headings above, but extra clean)

        record = {
            "source": "darglobal.co.uk",
            "url": "https://darglobal.co.uk/one-of-one/top-of-the-astera",
            "title": title,
            "description": description,
            "city": city,
            "country": None,  # Not explicitly stated as country in TXT; keep None per "do not infer"
            "property_type": None,  # Would be Villa but not inferred per rules
            "bedrooms": None,  # Would be 5 but not inferred per rules
            "price": None,  # "AVAILABLE ON REQUEST" - keep as None, don't invent
            "currency": None,  # Not explicitly stated; keep as None
            "amenities": None,  # Not extracted from TXT per "do not invent" rule
            "facilities": None,  # Not extracted from TXT per "do not invent" rule
            "developer": "DarGlobal",  # Known developer
            "status": status,
            "availability": availability,
            "reference_number": None,
            "extracted_at": datetime.now(UTC).isoformat() + "Z",
        }
        records.append(record)

    return records
