"""Typed, source-attributed attraction catalog records.

Catalog records describe *claims* from sources; the presence of a source never
means the attraction, opening hours, access or coordinates were checked live.
Fixtures must never be passed off as verified real-world tourism data.
"""
from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CatalogSourceV1(_Frozen):
    source_id: str = Field(
        min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    title: str = Field(min_length=1, max_length=300)
    kind: Literal["official", "editorial", "fixture"]
    url: str | None = Field(default=None, max_length=2048)
    observed_at: date
    valid_through: date

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("https://"):
            raise ValueError("source URLs must use HTTPS")
        return value

    @model_validator(mode="after")
    def valid_range(self) -> "CatalogSourceV1":
        if self.valid_through < self.observed_at:
            raise ValueError("source validity must not precede observation")
        if self.kind != "fixture" and not self.url:
            raise ValueError("non-fixture sources require a URL")
        return self


class GeoPointV1(_Frozen):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    source_id: str = Field(min_length=1, max_length=160)


class AccessibilityV1(_Frozen):
    wheelchair_access: Literal["yes", "no", "unknown"] = "unknown"
    source_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def provenance_for_claim(self) -> "AccessibilityV1":
        if self.wheelchair_access != "unknown" and not self.source_id:
            raise ValueError("known accessibility claims require provenance")
        return self


class DatedOpeningV1(_Frozen):
    on_date: date
    opens_at: time
    closes_at: time
    source_id: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def valid_window(self) -> "DatedOpeningV1":
        if (
            self.opens_at.tzinfo is not None
            or self.closes_at.tzinfo is not None
            or (self.opens_at.hour, self.opens_at.minute)
            >= (self.closes_at.hour, self.closes_at.minute)
        ):
            raise ValueError("opening window requires increasing local clock times")
        if self.opens_at.second or self.closes_at.second:
            raise ValueError("second-precision opening hours are not supported")
        return self


class AttractionRecordV1(_Frozen):
    attraction_id: str = Field(
        min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    knowledge_document_id: str = Field(
        min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._-]*$"
    )
    name: str = Field(min_length=1, max_length=200)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    city: str = Field(min_length=1, max_length=120)
    location: GeoPointV1
    visit_duration_minutes: int = Field(ge=15, le=480)
    duration_source_id: str = Field(min_length=1, max_length=160)
    accessibility: AccessibilityV1 = Field(default_factory=AccessibilityV1)
    opening_windows: tuple[DatedOpeningV1, ...] = Field(default_factory=tuple, max_length=60)
    sources: tuple[CatalogSourceV1, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def source_references_exist(self) -> "AttractionRecordV1":
        identifiers = [item.source_id for item in self.sources]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate source identifiers")

        used = {self.location.source_id, self.duration_source_id}
        if self.accessibility.source_id is not None:
            used.add(self.accessibility.source_id)
        used.update(window.source_id for window in self.opening_windows)
        if not used.issubset(set(identifiers)):
            raise ValueError("unresolved catalog provenance reference")
        if len({(w.on_date, w.opens_at, w.closes_at) for w in self.opening_windows}) != len(self.opening_windows):
            raise ValueError("duplicate dated opening window")
        return self


__all__ = [
    "CatalogSourceV1", "GeoPointV1", "AccessibilityV1",
    "DatedOpeningV1", "AttractionRecordV1",
]
