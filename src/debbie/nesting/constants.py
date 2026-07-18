"""Stable first-engine identity required by OPT-002."""

ENGINE_VERSION = "0.1.0"
STRATEGY_ID = "left_to_right_rectangular_v1"
STRATEGY_DISPLAY_NAME = "Deterministic Left-to-Right Rectangular Placement"
DECISION_POLICY_VERSION = "debbie-policy-2026-07-18-v1"
FEASIBILITY_CLASS = "Free rectangular placement — non-guillotine"

OBJECTIVE_POLICY = (
    "maximize_placed_required_demand",
    "minimize_physical_stock_sheets_consumed",
    "minimize_total_nominal_full_stock_area_consumed",
    "minimize_unused_usable_area",
    "stable_deterministic_tie_breakers",
)
