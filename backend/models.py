from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BaseProperty(BaseModel):
    source: str = Field(description="Source website name")
    url: str = Field(description="Canonical source URL")
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="ISO extraction timestamp",
    )

    model_config = {"populate_by_name": True, "validate_assignment": True}


class DarGlobalProperty(BaseProperty):
    title: str = Field(description="Property/project name")
    description: Optional[str] = Field(
        default=None, description="Full property description"
    )
    country: Optional[str] = Field(default=None, description="Country")
    city: Optional[str] = Field(default=None, description="City/area")
    property_type: Optional[str] = Field(
        default=None, description="Apartment, Villa, Penthouse, etc."
    )
    bedrooms: Optional[int] = Field(default=None, description="Number of bedrooms")
    size_sqm: Optional[float] = Field(
        default=None, description="Property size in square meters"
    )
    price: Optional[float] = Field(default=None, description="Price in base currency")
    currency: Optional[str] = Field(
        default=None, description="Currency code (e.g., USD, SAR, GBP)"
    )
    amenities: Optional[list[str]] = Field(
        default=None, description="Feature amenities"
    )
    facilities: Optional[list[str]] = Field(
        default=None, description="Building facilities"
    )
    developer: Optional[str] = Field(
        default=None, description="Developer or agency name"
    )
    status: Optional[str] = Field(
        default=None,
        description="Availability status (e.g., Available, SOLD, COMING SOON)",
    )
    images: Optional[list[str]] = Field(default=None, description="Image URLs")
    reference_number: Optional[str] = Field(
        default=None, description="Property reference number"
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude={"extracted_at", "source", "url"})

    def to_json(self) -> str:
        import json

        return json.dumps(self.model_dump(mode="json"), indent=2, default=str)


class WasaltProperty(BaseProperty):
    title: str = Field(description="Property title/name")
    description: Optional[str] = Field(
        default=None, description="Property specifications breakdown"
    )
    country: Optional[str] = Field(default=None, description="Country")
    city: Optional[str] = Field(default=None, description="Neighborhood/area")
    property_type: Optional[str] = Field(
        default=None,
        description="Villa, Apartment, Land, Building, Duplex, Floor, Rest house",
    )
    bedrooms: Optional[int] = Field(default=None, description="Number of bedrooms")
    land_area_sqm: Optional[float] = Field(
        default=None, description="Land area in square meters"
    )
    building_area_sqm: Optional[float] = Field(
        default=None, description="Building area in square meters"
    )
    price: Optional[float] = Field(default=None, description="Price in SAR")
    currency: Optional[str] = Field(default="SAR", description="Currency code")
    amenities: Optional[list[str]] = Field(
        default=None, description="Feature amenities"
    )
    facilities: Optional[list[str]] = Field(
        default=None, description="Building facilities"
    )
    broker: Optional[dict[str, Any]] = Field(
        default=None, description="Broker/agent information"
    )
    status: Optional[str] = Field(
        default=None, description="Availability status (e.g., New, Resale)"
    )
    reference_number: Optional[str] = Field(
        default=None, description="Property reference number"
    )
    last_updated: Optional[str] = Field(
        default=None, description="Last updated timestamp string"
    )
    images: Optional[list[str]] = Field(default=None, description="Image URLs")

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude={"extracted_at", "source", "url"})

    def to_json(self) -> str:
        import json

        return json.dumps(self.model_dump(mode="json"), indent=2, default=str)


class ExtractedRecord(BaseModel):
    """Unified record for pipeline ingestion."""

    source: str
    url: str
    data: dict[str, Any]
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"populate_by_name": True, "validate_assignment": True}
