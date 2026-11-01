"""Decimal-safe financial calculations used by every application view."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Dict, List, Mapping, Optional, Sequence


ZERO = Decimal("0")
ONE = Decimal("1")
CENT = Decimal("0.01")


class ModelInputError(ValueError):
    """Raised when financial inputs are invalid or cannot be modelled."""


def decimal_value(value: Any, label: str = "value") -> Decimal:
    if isinstance(value, bool):
        raise ModelInputError("%s must be a finite number." % label)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ModelInputError("%s must be a finite number." % label)
    if not result.is_finite():
        raise ModelInputError("%s must be a finite number." % label)
    return result


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT)


def _assumption(
    assumptions: Mapping[str, Any],
    key: str,
    minimum: Optional[Decimal] = None,
    maximum: Optional[Decimal] = None,
) -> Decimal:
    if key not in assumptions:
        raise ModelInputError("Missing required assumption: %s." % key)
    value = decimal_value(assumptions[key], key)
    if minimum is not None and value < minimum:
        raise ModelInputError("%s must be at least %s." % (key, minimum))
    if maximum is not None and value > maximum:
        raise ModelInputError("%s must be no more than %s." % (key, maximum))
    return value


def period_label(start_period: str, offset: int) -> str:
    try:
        year, month = (int(part) for part in start_period.split("-", 1))
        date(year, month, 1)
    except (AttributeError, TypeError, ValueError):
        raise ModelInputError("start_period must use YYYY-MM format.")
    absolute_month = year * 12 + month - 1 + offset
    return "%04d-%02d" % (absolute_month // 12, absolute_month % 12 + 1)


def calculate_plan(
    assumptions: Mapping[str, Any],
    start_period: str,
    horizon: int,
) -> Dict[str, Any]:
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 60:
        raise ModelInputError("horizon must be a whole number between 1 and 60 months.")

    opening_cash = _assumption(assumptions, "opening_cash")
    units = _assumption(assumptions, "starting_units", ZERO)
    unit_growth = _assumption(assumptions, "monthly_unit_growth", Decimal("-0.99"), Decimal("5"))
    unit_price = _assumption(assumptions, "unit_price", ZERO)
    variable_cost = _assumption(assumptions, "variable_cost_per_unit", ZERO)
    fixed_opex = _assumption(assumptions, "fixed_opex", ZERO)
    payroll = _assumption(assumptions, "payroll", ZERO)
    depreciation = _assumption(assumptions, "depreciation", ZERO)
    interest = _assumption(assumptions, "interest_expense", ZERO)
    tax_rate = _assumption(assumptions, "tax_rate", ZERO, ONE)
    minimum_cash = _assumption(assumptions, "minimum_cash", ZERO)
    collection_rate = _assumption(assumptions, "collection_rate", ZERO, Decimal("2"))
    payment_rate = _assumption(assumptions, "payment_rate", ZERO, Decimal("2"))
    capex = _assumption(assumptions, "monthly_capex", ZERO)
    debt_proceeds = _assumption(assumptions, "monthly_debt_proceeds", ZERO)
    debt_repayment = _assumption(assumptions, "monthly_debt_repayment", ZERO)
    equity_contribution = _assumption(assumptions, "monthly_equity_contribution", ZERO)

    rows: List[Dict[str, Any]] = []
    current_cash = opening_cash
    with localcontext() as context:
        context.prec = 28
        for index in range(horizon):
            if index:
                units *= ONE + unit_growth
            revenue = units * unit_price
            cogs = units * variable_cost
            gross_profit = revenue - cogs
            operating_expenses = fixed_opex + payroll
            ebitda = gross_profit - operating_expenses
            ebit = ebitda - depreciation
            profit_before_tax = ebit - interest
            tax = max(ZERO, profit_before_tax * tax_rate)
            net_income = profit_before_tax - tax

            cash_collections = revenue * collection_rate
            operating_payments = (cogs + operating_expenses) * payment_rate
            cash_inflows = cash_collections + debt_proceeds + equity_contribution
            cash_outflows = (
                operating_payments + tax + interest + capex + debt_repayment
            )
            net_cash_movement = cash_inflows - cash_outflows
            closing_cash = current_cash + net_cash_movement
            contribution_per_unit = unit_price - variable_cost
            break_even_units = (
                operating_expenses / contribution_per_unit
                if contribution_per_unit > ZERO
                else None
            )
            break_even_revenue = (
                break_even_units * unit_price if break_even_units is not None else None
            )

            rows.append(
                {
                    "period": period_label(start_period, index),
                    "units": units,
                    "revenue": money(revenue),
                    "cogs": money(cogs),
                    "gross_profit": money(gross_profit),
                    "gross_margin": gross_profit / revenue if revenue else None,
                    "fixed_opex": money(fixed_opex),
                    "payroll": money(payroll),
                    "operating_expenses": money(operating_expenses),
                    "ebitda": money(ebitda),
                    "ebitda_margin": ebitda / revenue if revenue else None,
                    "depreciation": money(depreciation),
                    "ebit": money(ebit),
                    "interest_expense": money(interest),
                    "profit_before_tax": money(profit_before_tax),
                    "tax_expense": money(tax),
                    "net_income": money(net_income),
                    "opening_cash": money(current_cash),
                    "cash_collections": money(cash_collections),
                    "cash_inflows": money(cash_inflows),
                    "cash_outflows": money(cash_outflows),
                    "net_cash_movement": money(net_cash_movement),
                    "closing_cash": money(closing_cash),
                    "minimum_cash": money(minimum_cash),
                    "cash_status": (
                        "negative"
                        if closing_cash < ZERO
                        else "below_reserve"
                        if closing_cash < minimum_cash
                        else "within_reserve"
                    ),
                    "contribution_per_unit": money(contribution_per_unit),
                    "break_even_units": (
                        break_even_units.quantize(Decimal("0.01"))
                        if break_even_units is not None
                        else None
                    ),
                    "break_even_revenue": (
                        money(break_even_revenue)
                        if break_even_revenue is not None
                        else None
                    ),
                    "margin_of_safety": (
                        money(revenue - break_even_revenue)
                        if break_even_revenue is not None
                        else None
                    ),
                }
            )
            current_cash = closing_cash

    totals = {
        "revenue": money(sum((row["revenue"] for row in rows), ZERO)),
        "gross_profit": money(sum((row["gross_profit"] for row in rows), ZERO)),
        "ebitda": money(sum((row["ebitda"] for row in rows), ZERO)),
        "net_income": money(sum((row["net_income"] for row in rows), ZERO)),
        "closing_cash": rows[-1]["closing_cash"],
        "minimum_projected_cash": min(row["closing_cash"] for row in rows),
        "average_monthly_net_cash_movement": money(
            sum((row["net_cash_movement"] for row in rows), ZERO) / Decimal(horizon)
        ),
        "break_even_revenue": rows[-1]["break_even_revenue"],
        "cash_breaches": sum(1 for row in rows if row["cash_status"] != "within_reserve"),
    }
    return {"periods": rows, "totals": totals}


def net_present_value(rate: Decimal, cash_flows: Sequence[Decimal]) -> Decimal:
    if rate <= Decimal("-1"):
        raise ModelInputError("discount_rate must be greater than -100%.")
    with localcontext() as context:
        context.prec = 28
        return sum(
            (cash_flow / ((ONE + rate) ** period) for period, cash_flow in enumerate(cash_flows)),
            ZERO,
        )


def _irr_roots(cash_flows: Sequence[Decimal]) -> List[Decimal]:
    lower = Decimal("-0.999")
    points = [lower + (Decimal("0.999") * Decimal(index) / Decimal("500")) for index in range(501)]
    points.extend(Decimal(index) / Decimal("100") for index in range(1, 1001))
    roots: List[Decimal] = []

    def record(root: Decimal) -> None:
        if all(abs(root - known) > Decimal("0.0001") for known in roots):
            roots.append(root)

    left = points[0]
    left_value = net_present_value(left, cash_flows)
    for right in points[1:]:
        right_value = net_present_value(right, cash_flows)
        if left_value == ZERO:
            record(left)
        elif right_value == ZERO:
            record(right)
        elif (left_value < ZERO) != (right_value < ZERO):
            low, high = left, right
            low_value = left_value
            for _ in range(160):
                middle = (low + high) / Decimal("2")
                middle_value = net_present_value(middle, cash_flows)
                if abs(middle_value) < Decimal("0.0000000001"):
                    low = high = middle
                    break
                if (middle_value < ZERO) == (low_value < ZERO):
                    low, low_value = middle, middle_value
                else:
                    high = middle
            root = (low + high) / Decimal("2")
            record(root)
        left, left_value = right, right_value
    return roots


def calculate_investment(
    initial_investment: Any,
    annual_cash_flow: Any,
    years: int,
    discount_rate: Any,
    residual_value: Any = ZERO,
) -> Dict[str, Any]:
    initial = decimal_value(initial_investment, "initial_investment")
    annual = decimal_value(annual_cash_flow, "annual_cash_flow")
    rate = decimal_value(discount_rate, "discount_rate")
    residual = decimal_value(residual_value, "residual_value")
    if initial <= ZERO:
        raise ModelInputError("initial_investment must be greater than zero.")
    if isinstance(years, bool) or not isinstance(years, int) or not 1 <= years <= 40:
        raise ModelInputError("years must be a whole number between 1 and 40.")
    if rate <= Decimal("-1"):
        raise ModelInputError("discount_rate must be greater than -100%.")

    cash_flows = [-initial]
    for year in range(1, years + 1):
        cash_flows.append(annual + (residual if year == years else ZERO))
    npv = net_present_value(rate, cash_flows)
    roots = _irr_roots(cash_flows)
    irr = roots[0] if len(roots) == 1 else None

    simple_payback = None
    discounted_payback = None
    cumulative = ZERO
    discounted_cumulative = ZERO
    for year in range(1, years + 1):
        flow = cash_flows[year]
        previous = cumulative
        previous_discounted = discounted_cumulative
        cumulative += flow
        discounted_flow = flow / ((ONE + rate) ** year)
        discounted_cumulative += discounted_flow
        if simple_payback is None and cumulative >= initial:
            simple_payback = Decimal(year - 1) + (
                (initial - previous) / flow if flow > ZERO else ZERO
            )
        if discounted_payback is None and discounted_cumulative >= initial:
            discounted_payback = Decimal(year - 1) + (
                (initial - previous_discounted) / discounted_flow
                if discounted_flow > ZERO
                else ZERO
            )

    pv_inflows = sum((flow / ((ONE + rate) ** year) for year, flow in enumerate(cash_flows[1:], 1)), ZERO)
    return {
        "npv": money(npv),
        "irr": irr,
        "irr_status": (
            "single_solution"
            if len(roots) == 1
            else "multiple_solutions"
            if len(roots) > 1
            else "no_solution_in_search_range"
        ),
        "simple_payback_years": (
            simple_payback.quantize(Decimal("0.01")) if simple_payback is not None else None
        ),
        "discounted_payback_years": (
            discounted_payback.quantize(Decimal("0.01"))
            if discounted_payback is not None
            else None
        ),
        "profitability_index": (
            pv_inflows / initial if initial > ZERO else None
        ),
        "cash_flows": [money(flow) for flow in cash_flows],
        "timing_convention": "Initial investment at time 0; annual cash flows at each year-end.",
        "irr_search_range": "Rates from -99.9% to 1000%; multiple roots may exist outside or between scan points.",
    }


def to_json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]
    return value
