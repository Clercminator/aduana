from __future__ import annotations

import ast
from decimal import Decimal

from app.engine.jurisdiction import JurisdictionConfig
from app.engine.money import round_money
from app.schemas.domain import LevyResult, Money

_ALLOWED = (ast.Expression, ast.BinOp, ast.Add, ast.Sub, ast.Name, ast.Load)


def eval_base(expression: str, environment: dict[str, Decimal]) -> Decimal:
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in environment:
            raise ValueError(f"unknown base name: {node.id}")

    def visit(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Name):
            return environment[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return visit(node.left) + visit(node.right)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            return visit(node.left) - visit(node.right)
        raise ValueError("invalid base expression")

    return visit(tree)


def apply_levies(
    customs_value: Money, hs_rate: Decimal, cfg: JurisdictionConfig
) -> list[LevyResult]:
    environment = {"customs_value": customs_value.amount}
    results: list[LevyResult] = []
    for levy in cfg.levies:
        base_amount = eval_base(levy.base, environment)
        if levy.rate.type == "hs_lookup":
            rate = hs_rate
        elif levy.rate.value is not None:
            rate = levy.rate.value
        else:
            raise ValueError(f"flat levy {levy.code} lacks value")
        amount = round_money(
            Money(amount=base_amount * rate, currency=customs_value.currency), levy.rounding.dp
        )
        environment[levy.code] = amount.amount
        results.append(
            LevyResult(
                code=levy.code,
                label=levy.label,
                base_expression=levy.base,
                base_amount=Money(amount=base_amount, currency=customs_value.currency),
                rate=rate,
                amount=amount,
                recoverable=levy.recoverable,
            )
        )
    return results
