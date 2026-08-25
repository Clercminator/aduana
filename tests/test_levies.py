from decimal import Decimal
from pathlib import Path

import pytest

from app.engine.jurisdiction import load_jurisdiction
from app.engine.levies import apply_levies, eval_base
from app.schemas.domain import Money

ROOT = Path(__file__).parents[1]


def test_chile_and_peru_stacks_are_configuration_driven():
    chile = load_jurisdiction(ROOT / "jurisdictions/chile.yaml").config
    peru = load_jurisdiction(ROOT / "jurisdictions/peru.yaml").config
    assert (
        len(apply_levies(Money(amount=Decimal("100"), currency="USD"), Decimal("0.06"), chile)) == 2
    )
    peru_results = apply_levies(Money(amount=Decimal("100"), currency="PEN"), Decimal("0.06"), peru)
    assert [item.code for item in peru_results] == ["AD_VALOREM", "IGV", "IPM", "PERCEPCION"]
    assert peru_results[-1].base_amount.amount == Decimal("125.08")


@pytest.mark.parametrize(
    "expression",
    ["abs(customs_value)", "customs_value.real", "unknown + customs_value", "1 + customs_value"],
)
def test_base_expression_rejects_unsafe_or_unknown_nodes(expression):
    with pytest.raises(ValueError):
        eval_base(expression, {"customs_value": Decimal("100")})
