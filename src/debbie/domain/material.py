"""Immutable Work-level material identity and density (MATERIAL-001)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from numbers import Real

from .errors import InvalidDensityError, InvalidMaterialError

MAX_MATERIAL_KEY_LENGTH = 128
MAX_MATERIAL_NAME_LENGTH = 256
MAX_MATERIAL_DESCRIPTION_LENGTH = 2048


def _required_text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise InvalidMaterialError(f"{field} must be text")
    normalized = value.strip()
    if not normalized:
        raise InvalidMaterialError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise InvalidMaterialError(f"{field} must not exceed {maximum} characters")
    return normalized


@dataclass(frozen=True, slots=True)
class MaterialCategoryKey:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _required_text(
                self.value, field="material category key", maximum=MAX_MATERIAL_KEY_LENGTH
            ),
        )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class MaterialGradeKey:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _required_text(
                self.value, field="material grade key", maximum=MAX_MATERIAL_KEY_LENGTH
            ),
        )

    def __str__(self) -> str:
        return self.value


class DensitySource(str, Enum):
    LIBRARY_DEFAULT = "library_default"
    EXPLICIT_OVERRIDE = "explicit_override"


@dataclass(frozen=True, slots=True)
class Density:
    """Effective density snapshot in g/cm³ (numerically equal to kg/dm³)."""

    grams_per_cubic_centimetre: float

    def __post_init__(self) -> None:
        value = self.grams_per_cubic_centimetre
        if isinstance(value, bool) or not isinstance(value, Real):
            raise InvalidDensityError("density must be a real number in g/cm³")
        normalized = float(value)
        if not isfinite(normalized) or normalized <= 0.0:
            raise InvalidDensityError("density must be finite and greater than zero")
        object.__setattr__(self, "grams_per_cubic_centimetre", normalized)


@dataclass(frozen=True, slots=True)
class MaterialIdentity:
    category_key: MaterialCategoryKey
    category_display_name: str = field(compare=False, hash=False)
    grade_key: MaterialGradeKey
    grade_display_name: str = field(compare=False, hash=False)
    effective_density: Density
    density_source: DensitySource
    description: str | None = field(default=None, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not isinstance(self.category_key, MaterialCategoryKey):
            raise InvalidMaterialError("category_key must be MaterialCategoryKey")
        if not isinstance(self.grade_key, MaterialGradeKey):
            raise InvalidMaterialError("grade_key must be MaterialGradeKey")
        if not isinstance(self.effective_density, Density):
            raise InvalidMaterialError("effective_density must be Density")
        object.__setattr__(
            self,
            "category_display_name",
            _required_text(
                self.category_display_name,
                field="material category display name",
                maximum=MAX_MATERIAL_NAME_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "grade_display_name",
            _required_text(
                self.grade_display_name,
                field="material grade display name",
                maximum=MAX_MATERIAL_NAME_LENGTH,
            ),
        )
        try:
            object.__setattr__(self, "density_source", DensitySource(self.density_source))
        except (TypeError, ValueError) as error:
            raise InvalidMaterialError("density_source is unsupported") from error
        if self.description is not None:
            if not isinstance(self.description, str):
                raise InvalidMaterialError("material description must be text or None")
            description = self.description.strip()
            if len(description) > MAX_MATERIAL_DESCRIPTION_LENGTH:
                raise InvalidMaterialError(
                    f"material description must not exceed {MAX_MATERIAL_DESCRIPTION_LENGTH} characters"
                )
            object.__setattr__(self, "description", description or None)
