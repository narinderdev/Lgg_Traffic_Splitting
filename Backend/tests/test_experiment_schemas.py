from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.common import Segments, VariantCreate
from app.schemas.experiment import ExperimentCreate


def test_experiment_create_requires_weights_to_sum_to_100() -> None:
    with pytest.raises(ValidationError):
        ExperimentCreate(
            name="Weights Test",
            entry_slug="weights-test",
            entry_url="https://example.com",
            segments=Segments(),
            variants=[
                VariantCreate(
                    name="Control",
                    destination_url="https://example.com/a",
                    weight=60,
                    is_control=True,
                ),
                VariantCreate(
                    name="Variant",
                    destination_url="https://example.com/b",
                    weight=30,
                    is_control=False,
                ),
            ],
        )


def test_experiment_create_requires_exactly_one_control() -> None:
    with pytest.raises(ValidationError):
        ExperimentCreate(
            name="Control Test",
            entry_slug="control-test",
            entry_url="https://example.com",
            segments=Segments(),
            variants=[
                VariantCreate(
                    name="Control A",
                    destination_url="https://example.com/a",
                    weight=50,
                    is_control=True,
                ),
                VariantCreate(
                    name="Control B",
                    destination_url="https://example.com/b",
                    weight=50,
                    is_control=True,
                ),
            ],
        )
