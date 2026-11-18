from __future__ import annotations

import re
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup, Tag

from backend.models import DarGlobalProperty, WasaltProperty, BaseProperty


class DarGlobalExtractor:
    """Extractor for DarGlobal.co.uk property pages."""

    DOMAIN = "darglobal.co.uk"

    # Patterns for URL classification
    ONE_OF_ONE_PATH = r"^/one-of-one(/.*)?$"
    PROJECT_PATH_PATTERN = r"^/(?:aida-360|aston-martin-media|la-collina|trump-international-hotel-and-tower-dubai|the-mulliner|fairway-villas-aida-oman|amour-sans-detour|marriott-residences-aida-oma|trump-tower-jeddah|the-great-escape-\d-aida-oman|aida-coastal-investment-villas|aida-trump-international-hotel|aida-trump-international-cliff-villas|aida-trump-villas|sunrise-haven-luxury-villas|les-vagues|neptune|tierra-viva|w-residences|davinci-tower-by-pagani|dg1|marea|rayana/trump-mansions|rayana/trump-international-qatar|rayana/darglobal-mansions|rayana/darglobal-mansions-fendi-casa|amaya/amaya-plots|amaya/padel-living|trump-plaza/executive-residences|trump-plaza/park-residences)$"

    def __init__(self, html: str, url: str) -> None:
        self.soup = BeautifulSoup(html, "html.parser")
        self.url = url
        self.path = urlparse(url).path.rstrip("/")

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _strip(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        return " ".join(text.split())

    @staticmethod
    def _extract_text(selector: Union[Tag, None], default: Optional[str] = None) -> Optional[str]:
        if selector is None:
            return default
        return DarGlobalExtractor._strip(selector.get_text())

    @staticmethod
    def _extract_first_h1(soup: BeautifulSoup) -> Optional[str]:
        h1 = soup.find("h1")
        return DarGlobalExtractor._strip(h1.get_text()) if h1 else None

    @staticmethod
    def _extract_meta(content_class: str, soup: BeautifulSoup, attribute: str = "content") -> Optional[str]:
        meta = soup.find("meta", attrs={"class": content_class})
        return meta.get(attribute) if meta else None

    # ── Property type detection ────────────────────────────────

    @staticmethod
    def _detect_property_type(url_path: str, title: Optional[str], text: str) -> Optional[str]:
        text_lower = (title or "") + " " + (text or "").lower()

        if re.search(r"penthouse|duplex", text_lower):
            return "Penthouse"
        if re.search(r"villa|villas", text_lower):
            return "Villa"
        if re.search(r"apartment|apartments", text_lower):
            return "Apartment"
        if re.search(r"mansion|mansions", text_lower):
            return "Mansion"
        if re.search(r"townhouse|townhouses", text_lower):
            return "Townhouse"
        if re.search(r"plot|plots", text_lower):
            return "Land"
        if re.search(r"floor|floors", text_lower):
            return "Floor"
        if re.search(r"rest house|rest houses", text_lower):
            return "Rest house"
        if re.search(r"hotel|hotels", text_lower):
            return "Hotel"
        if re.search(r"commercial|office|retail", text_lower):
            return "Commercial"
        return None

    # ── Field extraction methods ───────────────────────────────

    def extract_from_one_of_one(self) -> DarGlobalProperty:
        """Extract from /one-of-one/... property pages."""
        title = self._extract_first_h1(self.soup)
        h1_text = title or ""

        # Extract city/location
        city_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", h1_text)
        city = city_match.group(1) if city_match else None

        # Extract bedrooms
        bedroom_match = re.search(r"(\d+)-? ?bedroom", h1_text, re.IGNORECASE)
        bedrooms = int(bedroom_match.group(1)) if bedroom_match else None

        # Extract price text
        price_text = ""
        price_tag = self.soup.find(string=re.compile(r"AVAILABLE ON REQUEST|price|SAR|USD|GBP", re.IGNORECASE))
        if price_tag:
            price_text = price_tag

        # Determine status
        status = "available_on_request"
        if re.search(r"\bSOLD\b", h1_text, re.IGNORECASE):
            status = "sold"
        elif re.search(r"\bCOMING SOON\b", h1_text, re.IGNORECASE):
            status = "coming_soon"

        # Extract description (all paragraph text below h1)
        description_parts = []
        for p in self.soup.find_all("p"):
            t = self._strip(p.get_text())
            if t and t not in ("AVAILABLE ON REQUEST", "Discover", "A WORLD OF ONE'S OWN"):
                description_parts.append(t)
        description = " ".join(description_parts) if description_parts else None

        # Extract amenities
        amenities: List[str] = []
        for span in self.soup.find_all("span"):
            t = self._strip(span.get_text())
            if t and ("Fendi" in t or "Aston" in t or "Pagani" in t or "Lamborghini" in t or "Fendi Casa" in t or "Aston Martin" in t):
                amenities.append(t)

        # Extract developer
        developer = "DarGlobal"

        # Extract image URLs
        images: List[str] = []
        for img in self.soup.find_all("img", src=True):
            src = img["src"]
            if "darglobal" in src.lower() or "cdn" in src.lower():
                images.append(src)

        return DarGlobalProperty(
            source=self.DOMAIN,
            url=self.url,
            title=title or "One-of-One Property",
            description=self._strip(description),
            city=city,
            property_type=self._detect_property_type(self.path, title, description or ""),
            bedrooms=bedrooms,
            status=status,
            amenities=amenities if amenities else None,
            developer=developer,
            images=images if images else None,
        )

    def extract_from_project_detail(self) -> DarGlobalProperty:
        """Extract from project detail pages (AIDA, Trump, etc.)."""
        title = self._extract_first_h1(self.soup)
        h1_text = title or ""

        # Extract location/city from breadcrumbs or hero section
        city = None
        location_tag = self.soup.find(lambda tag: tag.name and "location" in tag.get("class", []).lower() if tag.get("class") else False)
        if not location_tag:
            location_tag = self.soup.find("span", string=re.compile(r"[A-Z][a-z]+,\s*[A-Za-z]+", re.IGNORECASE))
        if location_tag:
            city_text = self._strip(location_tag.get_text())
            city = re.search(r"([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*)", city_text)
            city = city.group(1) if city else None

        # Extract description
        description = None
        desc_container = self.soup.find("div", class_=lambda c: c and "description" in c.lower() if c else False)
        if desc_container:
            description = self._strip(desc_container.get_text())
        if description is None:
            # Fallback: first meaningful paragraph block
            for p in self.soup.find_all("p"):
                t = self._strip(p.get_text())
                if t and len(t) > 50 and "AVAILABLE ON REQUEST" not in t:
                    description = t
                    break

        # Extract bedrooms
        bedrooms = None
        br_match = re.search(r"(\d+)\s*bedroom|bedrooms?\s*:?\s*(\d+)", h1_text, re.IGNORECASE)
        if br_match:
            bedrooms = int(br_match.group(1) or br_match.group(2))

        # Extract price
        price = None
        currency = None
        price_tag = self.soup.find(string=re.compile(r"[\d,]+\s*(SAR|USD|GBP|AED)", re.IGNORECASE))
        if price_tag:
            pm = re.search(r"([\d,]+)\s*(SAR|USD|GBP|AED)", price_tag, re.IGNORECASE)
            if pm:
                price = float(pm.group(1).replace(",", ""))
                currency = pm.group(2)

        # If no price on page, check for "AVAILABLE ON REQUEST"
        if price is None:
            if self.soup.find(string=re.compile(r"AVAILABLE ON REQUEST", re.IGNORECASE)):
                price = None
                currency = None

        # Extract amenities
        amenities: List[str] = []
        for strong in self.soup.find_all("strong"):
            t = self._strip(strong.get_text())
            if t and len(t) > 3:
                amenities.append(t)

        # Extract facilities
        facilities: List[str] = []
        for li in self.soup.find_all("li"):
            t = self._strip(li.get_text())
            if t and len(t) > 10:
                facilities.append(t)

        # Extract size
        size_sqm = None
        size_match = re.search(r"(\d+(?:\.\d+)?)\s*[mM]2|(\d+(?:\.\d+)?)\s*sqm", h1_text + " " + (description or ""), re.IGNORECASE)
        if size_match:
            val = size_match.group(1) or size_match.group(2)
            try:
                size_sqm = float(val)
            except (ValueError, TypeError):
                pass

        # Extract developer
        developer = "DarGlobal"

        # Extract images
        images: List[str] = []
        for img in self.soup.find_all("img", src=True):
            src = img["src"]
            if src.startswith("http") and "darglobal" in src.lower():
                images.append(src)

        # Extract reference number
        reference_number = None
        ref_tag = self.soup.find(string=re.compile(r"Ref no|Reference|property ref", re.IGNORECASE))
        if ref_tag:
            ref_match = re.search(r"[#]?(\d+)", self._strip(ref_tag))
            if ref_match:
                reference_number = ref_match.group(1)

        # Determine status
        status = "available"
        if self.soup.find(string=re.compile(r"AVAILABLE ON REQUEST", re.IGNORECASE)):
            status = "available_on_request"
        elif self.soup.find(string=re.compile(r"\bSOLD\b", re.IGNORECASE)):
            status = "sold"

        return DarGlobalProperty(
            source=self.DOMAIN,
            url=self.url,
            title=title or "DarGlobal Project",
            description=description,
            city=city,
            property_type=self._detect_property_type(self.path, title, description or ""),
            bedrooms=bedrooms,
            price=price,
            currency=currency,
            amenities=amenities if amenities else None,
            facilities=facilities if facilities else None,
            developer=developer,
            status=status,
            images=images if images else None,
            reference_number=reference_number,
        )

    def extract_from_blog(self) -> DarGlobalProperty:
        """Extract from blog post pages."""
        title = self._extract_first_h1(self.soup)

        # Extract article body
        article = self.soup.find("article") or self.soup.find("main") or self.soup
        description = None
        for p in article.find_all("p") if article else self.soup.find_all("p"):
            t = self._strip(p.get_text())
            if t and len(t) > 20:
                if description is None:
                    description = t
                else:
                    description += " " + t

        # Extract categories/tags
        categories: List[str] = []
        for tag_link in self.soup.find_all("a", href=re.compile(r"/blog/|/insights/")):
            t = self._strip(tag_link.get_text())
            if t and len(t) > 2:
                categories.append(t)

        # Extract image URLs
        images: List[str] = []
        for img in self.soup.find_all("img", src=True):
            src = img["src"]
            if src.startswith("http"):
                images.append(src)

        return DarGlobalProperty(
            source=self.DOMAIN,
            url=self.url,
            title=title or "Blog Post",
            description=description,
            city=None,
            property_type=None,
            bedrooms=None,
            price=None,
            currency=None,
            amenities=categories if categories else None,
            facilities=None,
            developer="DarGlobal",
            images=images if images else None,
        )

    # ── Public entry point ──────────────────────────────────────

    def extract(self) -> DarGlobalProperty:
        """Extract property data based on URL pattern."""
        path = self.path.lower()

        # One-of-One collection or property pages
        if re.search(self.ONE_OF_ONE_PATH, self.path):
            return self.extract_from_one_of_one()

        # Project detail pages (AIDA, Trump, branded residences)
        if any(re.search(pat, path) for pat in [
            r"/aida", r"/trump", r"/davinci", r"/dg1", r"/marea", r"/rayana",
            r"/urban-oasis", r"/tierra-viva", r"/neptune", r"/the-astera",
            r"/la-collina", r"/marriott-residences", r"/fairway-villas",
        ]):
            return self.extract_from_project_detail()

        # Blog posts
        if "/blog/" in path or "/insights/" in path:
            return self.extract_from_blog()

        # Fallback generic extraction
        return DarGlobalProperty(
            source=self.DOMAIN,
            url=self.url,
            title="DarGlobal Page",
            description=self._strip(self.soup.get_text()[:500]),
        )