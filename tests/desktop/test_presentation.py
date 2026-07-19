import pytest

from debbie.application.presentation import (
    format_density,
    format_dimension,
    format_equivalent_sheets,
    format_fraction,
    format_mass,
)


def test_engineering_display_formatting_is_centralized_and_normalizes_negative_zero() -> None:
    assert format_mass(-0.0001) == "0.00 kg"
    assert format_mass(333.28125) == "333.28 kg"
    assert format_dimension(3) == "3.00 mm"
    assert format_density(7.9) == "7.900 g/cm³"
    assert format_fraction(0.5) == "50.00%"
    assert format_equivalent_sheets(4.5) == "4.500 sheets"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_cannot_reach_normal_desktop_formatting(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        format_mass(value)
