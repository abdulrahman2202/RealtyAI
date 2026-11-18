from __future__ import annotations

import re
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup, Tag

from backend.models import DarGlobalProperty, WasaltProperty, BaseProperty


class WasaltExtractor:
    """Extractor for Wasalt property pages."""

    DOMAIN = "wasalt.sa"

    # Detail URL pattern: /en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799
    DETAIL_PATH_PATTERN = r"^/en/property/sale/[-_\w]+-\d+$"
    LISTING_PATH_PATTERN = r"^/en/(?:villas-for-sale|apartments-for-sale|lands-for-sale)/.+$"
    SEARCH_PATH_PATTERN = r"^/en/sale/search\?"

    def __init__(self, html: str, url: str) -> None:
        self.soup = BeautifulSoup(html, "html.parser")
        self.url = url
        self.path = urlparse(url).path.rstrip("/")
        self.query = parse_qs(urlparse(url).query)

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _strip(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        return " ".join(text.split())

    @staticmethod
    def _extract_text(selector: Tag, default: Optional[str] = None) -> Optional[str]:
        if selector is None:
            return default
        return WasaltExtractor._strip(selector.get_text())

    # ── Field extraction from detail pages ─────────────────────

    def extract_detail(self) -> WasaltProperty:
        """Extract from property detail pages like /en/property/sale/villa-450-sqm-facing-south-on-18m-width-street-5971799."""
        title = self._extract_first_h1() or "Wasalt Property"

        # Extract price and currency
        price, currency = self._extract_price()

        # Extract bedrooms
        bedrooms = self._extract_bedrooms()

        # Extract location
        city, country = self._extract_location()

        # Extract property type
        property_type = self._extract_property_type()

        # Extract land and building area
        land_area, building_area = self._extract_areas()

        # Extract description
        description = self._extract_description()

        # Extract amenities
        amenities = self._extract_amenities()

        # Extract facilities
        facilities = self._extract_facilities()

        # Extract reference number
        reference_number = self._extract_reference_number()

        # Extract last updated
        last_updated = self._extract_last_updated()

        # Extract broker info (but avoid personal data)
        broker = self._extract_broker()

        # Extract images
        images = self._extract_images()

        # Determine status
        status = self._extract_status()

        return WasaltProperty(
            source=self.DOMAIN,
            url=self.url,
            title=title,
            description=description,
            country=country,
            city=city,
            property_type=property_type,
            bedrooms=bedrooms,
            land_area_sqm=land_area,
            building_area_sqm=building_area,
            price=price,
            currency=currency,
            amenities=amenities if amenities else None,
            facilities=facilities if facilities else None,
            broker=broker,
            status=status,
            reference_number=reference_number,
            last_updated=last_updated,
            images=images if images else None,
        )

    def _extract_first_h1(self) -> Optional[str]:
        h1 = self.soup.find("h1")
        return self._strip(h1.get_text()) if h1 else None

    def _extract_price(self) -> tuple[Optional[float], str]:
        """Extract price in SAR. Returns (price_value, 'SAR')."""
        # Look for price in hero/spec section
        price_patterns = [
            r"[\d,\s]+(?:\.\d+)?\s*SAR",
            r"SAR[\d,\s]+(?:\.\d+)?",
        ]

        # Check main price element
        price_text = None
        price_elem = self.soup.find("span", string=re.compile(r"[\d,]+\s*SAR", re.IGNORECASE))
        if price_elem:
            price_text = self._strip(price_elem.get_text())

        # Check in spec table/description
        if price_text is None:
            for span in self.soup.find_all("span"):
                t = self._strip(span.get_text())
                if re.search(r"\d{2,3},\d{3}", t) and "SAR" in t:
                    price_text = t
                    break

        if price_text is None:
            return None, "SAR"

        # Parse the numeric value
        pm = re.search(r"([\d,]+)\s*SAR", price_text, re.IGNORECASE)
        if pm:
            try:
                value = float(pm.group(1).replace(",", ""))
                return value, "SAR"
            except (ValueError, TypeError):
                pass

        return None, "SAR"

    def _extract_bedrooms(self) -> Optional[int]:
        """Extract number of bedrooms."""
        # Check H1 or hero text
        h1_text = self._extract_first_h1() or ""
        br_match = re.search(r"(\d+)\s*bedroom|bedrooms?\s*(:?\s*\d+)", h1_text, re.IGNORECASE)
        if br_match:
            try:
                return int(br_match.group(1))
            except (ValueError, TypeError):
                pass

        # Check in description/specs
        for span in self.soup.find_all("span"):
            t = self._strip(span.get_text())
            m = re.search(r"\b(\d+)\s*bedroom", t, re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, TypeError):
                    pass

        return None

    def _extract_location(self) -> tuple[Optional[str], Optional[str]]:
        """Extract city and country."""
        # Typical format: "Al-Rimal, East Riyadh" or similar
        city = None
        country = "Saudi Arabia"  # Wasalt is Saudi-based

        # Look for location tag
        location_tag = self.soup.find("span", string=re.compile(r".+,\s+.+"))
        if location_tag:
            loc_text = self._strip(location_tag.get_text())
            parts = [p.strip() for p in loc_text.split(",")]
            if len(parts) >= 2:
                city = parts[0]
                # Country is usually the last part or known
                country = parts[-1] if len(parts) > 2 else "Saudi Arabia"

        # Also check breadcrumbs or hero section
        if not city:
            hero_text = self._extract_first_h1() or ""
            loc_match = re.search(r"([A-Za-z\s-]+),\s*([A-Za-z\s]+)", hero_text)
            if loc_match:
                city = loc_match.group(1).strip()

        return city, country

    def _extract_property_type(self) -> Optional[str]:
        """Extract property type from category badges or description."""
        type_lower = ""

        # Check page title/H1
        h1 = self._extract_first_h1() or ""
        type_lower += h1.lower() + " "

        # Check for type badges in the page
        for span in self.soup.find_all("span", class_=re.compile(r".*(villa|apartment|land|building|duplex|floor|rest).*", re.IGNORECASE)):
            t = self._strip(span.get_text())
            if t:
                type_lower += t.lower() + " "

        # Check badges
        for badges in self.soup.find_all("div", class_=re.compile(r".*badge.*")):
            t = self._strip(badges.get_text())
            type_lower += t.lower() + " "

        # Map to canonical types
        type_mapping = {
            "villa": "Villa",
            "apartment": "Apartment",
            "land": "Land",
            "building": "Building",
            "duplex": "Duplex",
            "floor": "Floor",
            "rest house": "Rest house",
        }

        for key, canonical in type_mapping.items():
            if re.search(r"\b" + re.escape(key) + r"\b", type_lower):
                return canonical

        return None

    def _extract_areas(self) -> tuple[Optional[float], Optional[float]]:
        """Extract land area and building area in sqm."""
        land_area: Optional[float] = None
        building_area: Optional[float] = None

        # Look for area specs in detail sections
        for span in self.soup.find_all("span"):
            t = self._strip(span.get_text())
            # Pattern: "450 SQM" or "385 m²"
            m = re.search(r"(\d+(?:\.\d+)?)\s*[Ss][Qq][Mm]", t)
            if m:
                val = float(m.group(1))
                if land_area is None:
                    land_area = val
                elif building_area is None:
                    building_area = val

            m2 = re.search(r"(\d+(?:\.\d+)?)\s*[mm²|m²]", t)
            if m2:
                val = float(m2.group(1))
                if land_area is None:
                    land_area = val
                elif building_area is None:
                    building_area = val

        # If only one area found, try to distinguish
        if land_area is not None and building_area is None:
            # Re-check: land area typically smaller or larger depending on property type
            # For villas: land often larger; for apartments: building area larger
            # Try to find a second distinct value
            all_areas = re.findall(r"(\d+(?:\.\d+)?)\s*[Ss][Qq][Mm]", self._strip(self.soup.get_text()))
            if len(all_areas) >= 2:
                building_area = float(all_areas[1])

        return land_area, building_area

    def _extract_description(self) -> Optional[str]:
        """Extract property specifications description."""
        # Look for a detailed spec section
        desc_candidates = []

        # .specs, .details, .property-specs
        for selector in [".specs", ".details", ".property-specs"]:
            elem = self.soup.select_one(selector)
            if elem:
                desc_candidates.append(elem.get_text())

        # Fallback: find the main content area's first substantial text block
        if not desc_candidates:
            main = self.soup.find("main") or self.soup.find("div", class_=lambda c: c and "main" in c.lower() if c else False)
            if main:
                for p in main.find_all("p"):
                    t = self._strip(p.get_text())
                    if t and len(t) > 30:
                        desc_candidates.append(t)
                        break

        # Also try: the largest text block in the page body
        if not desc_candidates:
            body_text = self._strip(self.soup.get_text())
            # Split by common separators and take the longest substantial block
            blocks = re.split(r"[.\n]{2,}", body_text)
            best = None
            for b in blocks:
                b = b.strip()
                if len(b) > 50 and len(b) > (len(best or "") if best else 0):
                    best = b
            if best:
                desc_candidates.append(best)

        if desc_candidates:
            return " ".join(desc_candidates)[:2000]  # Cap length

        return None

    def _extract_amenities(self) -> List[str]:
        """Extract feature amenities."""
        amenities: List[str] = []

        # Look for feature lists
        for li in self.soup.find_all("li"):
            t = self._strip(li.get_text())
            if t and len(t) > 3 and len(t) < 100:
                # Filter out noise terms
                noise_terms = {"sqm", "m²", "bedroom", "bathroom", "saudi", "code", "professional",
                               "modern", "high-quality", "photo", "documented", "steel", "tank",
                               "sewage", "water", "plumbing", "foundations"}
                t_lower = t.lower()
                if not any(nt in t_lower for nt in noise_terms):
                    amenities.append(t)

        # Also check for strong-tagged features
        for strong in self.soup.find_all("strong"):
            t = self._strip(strong.get_text())
            if t and len(t) > 3 and len(t) < 100:
                amenities.append(t)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for a in amenities:
            if a not in seen:
                seen.add(a)
                deduped.append(a)

        return deduped

    def _extract_facilities(self) -> List[str]:
        """Extract building facilities."""
        facilities: List[str] = []

        # Look for facility lists - common patterns
        for h4 in self.soup.find_all("h4"):
            t = self._strip(h4.get_text())
            if t and len(t) > 3 and len(t) < 100:
                # Common facility keywords
                facility_keywords = ["water", "sewage", "plumbing", " tank", "steel", "code", "finish",
                                     "modern", "professional", "documented"]
                t_lower = t.lower()
                if any(kw in t_lower for kw in facility_keywords):
                    facilities.append(t)

        # Check for facility icon/text blocks
        for div in self.soup.find_all("div"):
            t = self._strip(div.get_text())
            if t and any(kw in t.lower() for kw in ["water", "sewage", "steel", "code", "finish"]):
                if len(t) > 10 and len(t) < 200:
                    facilities.append(t)

        # Deduplicate
        seen = set()
        deduped = []
        for f in facilities:
            if f not in seen:
                seen.add(f)
                deduped.append(f)

        return deduped

    def _extract_reference_number(self) -> Optional[str]:
        """Extract property reference number."""
        # Pattern: "Ref no. 289517"
        ref_tag = self.soup.find(string=re.compile(r"Ref no|Reference|Ref#", re.IGNORECASE))
        if ref_tag:
            m = re.search(r"[#]?(\d+)", self._strip(ref_tag))
            if m:
                return m.group(1)

        # Also check in page text
        for span in self.soup.find_all("span"):
            t = self._strip(span.get_text())
            m = re.search(r"Ref no\.?\s*(\d+)", t, re.IGNORECASE)
            if m:
                return m.group(1)

        return None

    def _extract_last_updated(self) -> Optional[str]:
        """Extract last updated timestamp."""
        # Pattern: "Last updated: 4 days ago"
        for span in self.soup.find_all("span"):
            t = self._strip(span.get_text())
            if re.search(r"last updated|updated ago", t, re.IGNORECASE):
                return t
        return None

    def _extract_broker(self) -> Optional[Dict[str, Any]]:
        """Extract broker/agent information. Avoid personal data."""
        broker: Dict[str, Any] = {}

        # Look for agent name
        for span in self.soup.find_all("span"):
            t = self._strip(span.get_text())
            if re.search(r"Agent|Broker|License", t, re.IGNORECASE):
                broker["name"] = t  # May contain agent name; filter later if needed
                break

        # Look for license numbers
        license_patterns = ["FAL", "REGA", "license", "FAL No", "REG Ad"]
        for span in self.soup.find_all("span"):
            t = self._strip(span.get_text())
            for pat in license_patterns:
                if re.search(pat, t, re.IGNORECASE):
                    if "broker" not in broker or not broker["name"]:
                        broker["license_number"] = t
                    break

        # Only include if we have meaningful data (not just noise)
        if not broker.get("name") and not broker.get("license_number"):
            return None

        # Filter out purely numeric strings that aren't license numbers
        if broker.get("license_number") and broker["license_number"].isdigit() and len(broker["license_number"]) < 5:
            broker.pop("license_number", None)

        return broker if broker else None

    def _extract_images(self) -> List[str]:
        """Extract image URLs from the property detail page."""
        images: List[str] = []

        for img in self.soup.find_all("img", src=True):
            src = img["src"]
            # Wasalt uses imagedelivery.net CDN
            if "imagedelivery.net" in src or src.startswith("http"):
                images.append(src)

        # Limit to reasonable number
        return images[:10]

    def _extract_status(self) -> Optional[str]:
        """Extract availability status."""
        h1_text = self._extract_first_h1() or ""

        if re.search(r"\bNew\b", h1_text, re.IGNORECASE):
            return "New"
        if re.search(r"\bResale\b", h1_text, re.IGNORECASE):
            return "Resale"
        if re.search(r"\bAvailable\b", h1_text, re.IGNORECASE):
            return "Available"
        if re.search(r"\bSold\b", h1_text, re.IGNORECASE):
            return "Sold"

        # Check in description/text
        full_text = self._strip(self.soup.get_text()).lower()
        if "available" in full_text and "sold" not in full_text:
            return "Available"
        if "sold" in full_text:
            return "Sold"

        return None

    # ── Listing page extraction (summary data from category pages) ──

    def extract_listing_summary(self) -> List[Dict[str, Any]]:
        """Extract summary data from listing/category pages.
        Returns list of dicts with minimal fields for property card summaries.
        """
        properties = []

        # Property cards are typically in divs with specific classes
        cards = self.soup.find_all("div", class_=lambda c: c and ("card" in c.lower() or "property" in c.lower() or "listing" in c.lower()) if c else False)

        if not cards:
            # Fallback: look for any div with price-like content
            cards = self.soup.find_all("div")

        for card in cards[:20]:  # Limit to first 20 cards
            try:
                summary: Dict[str, Any] = {}

                # Try to extract title/name
                title_elem = card.find("h3") or card.find("h2") or card.find("h4")
                if title_elem:
                    summary["title"] = self._strip(title_elem.get_text())

                # Try to extract price
                price_elem = card.find(string=re.compile(r"[\d,]+\s*SAR", re.IGNORECASE))
                if price_elem:
                    pm = re.search(r"([\d,]+)\s*SAR", self._strip(price_elem), re.IGNORECASE)
                    if pm:
                        summary["price"] = float(pm.group(1).replace(",", ""))
                        summary["currency"] = "SAR"

                # Try to extract bedrooms
                br_elem = card.find(string=re.compile(r"\d+\s*bedroom", re.IGNORECASE))
                if br_elem:
                    m = re.search(r"(\d+)", self._strip(br_elem))
                    if m:
                        summary["bedrooms"] = int(m.group(1))

                # Try to extract location
                loc_elem = card.find(string=re.compile(r".+,\s+.+", re.IGNORECASE))
                if loc_elem:
                    summary["location"] = self._strip(loc_elem)

                if summary:
                    properties.append(summary)
            except Exception:
                continue

        return properties

    # ── Public entry point ──────────────────────────────────────

    def extract(self) -> Union[WasaltProperty, List[Dict[str, Any]]]:
        """Extract data based on URL pattern."""
        if re.search(self.DETAIL_PATH_PATTERN, self.path):
            return self.extract_detail()
        if re.search(self.LISTING_PATH_PATTERN, self.path):
            return self.extract_listing_summary()
        if re.search(self.SEARCH_PATH_PATTERN, self.path):
            return self.extract_listing_summary()
        return {"url": self.url, "note": "Unknown Wasalt page type"}


# Convenience function for pipeline use
def extract_wasalt(html: str, url: str) -> WasaltProperty:
    """Extract Wasalt property data from HTML."""
    return WasaltExtractor(html, url).extract()