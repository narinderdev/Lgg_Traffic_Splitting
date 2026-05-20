from __future__ import annotations

from app.schemas.common import (
    MultivariateFactor,
    MultivariateFactorOption,
    MultivariatePreviewRequest,
)
from app.services.experiments import build_multivariate_preview


def test_multivariate_preview_generates_combinations() -> None:
    payload = MultivariatePreviewRequest(
        destination_url="https://example.com/landing",
        hyros_tag_prefix="mv",
        factors=[
            MultivariateFactor(
                key="headline",
                label="Headline",
                options=[
                    MultivariateFactorOption(key="a", label="A"),
                    MultivariateFactorOption(key="b", label="B"),
                ],
            ),
            MultivariateFactor(
                key="cta",
                label="CTA",
                options=[
                    MultivariateFactorOption(key="x", label="X"),
                    MultivariateFactorOption(key="y", label="Y"),
                ],
            ),
        ],
    )

    variants = build_multivariate_preview(payload)

    assert len(variants) == 4
    assert sum(variant.weight for variant in variants) == 100
    assert variants[0].is_control is True
    assert variants[0].routing_metadata["multivariate_values"] == {"headline": "a", "cta": "x"}
