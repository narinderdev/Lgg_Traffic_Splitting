from __future__ import annotations

from uuid import uuid4

from app.services.experiments import _build_conversion_stats, _compute_significance


def test_compute_significance_flags_clear_winner() -> None:
    z_score, p_value, is_significant = _compute_significance(
        impressions=1000,
        conversions=180,
        control_impressions=1000,
        control_conversions=100,
    )

    assert z_score is not None and z_score > 0
    assert p_value is not None and p_value < 0.05
    assert is_significant is True


def test_build_conversion_stats_computes_uplift() -> None:
    control_id = uuid4()
    variant_id = uuid4()
    totals = [
        (control_id, "Control", True, 1000),
        (variant_id, "Variant A", False, 1000),
    ]
    conversions = [
        (control_id, "Control", True, 100),
        (variant_id, "Variant A", False, 180),
    ]

    stats = _build_conversion_stats(totals, conversions)
    variant = next(item for item in stats if str(item.variant_id) == str(variant_id))

    assert round(variant.conversion_rate, 4) == 0.18
    assert variant.uplift_vs_control is not None
    assert round(variant.uplift_vs_control, 2) == 0.80
    assert variant.is_significant is True
