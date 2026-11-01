"""Application services and request validation."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Dict, Mapping

from .financial import (
    ModelInputError,
    calculate_investment,
    calculate_plan,
    decimal_value,
    to_json_value,
)
from .storage import DEFAULT_ASSUMPTIONS, Store


class RequestError(ValueError):
    pass


def _clean_text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise RequestError("%s must be text." % field)
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        raise RequestError("%s must contain 1 to %d characters." % (field, limit))
    return cleaned


def _validate_assumption(key: str, raw_value: Any) -> str:
    if key not in DEFAULT_ASSUMPTIONS:
        raise RequestError("Unknown financial assumption.")
    value = decimal_value(raw_value, key)
    if key in ("starting_units", "unit_price", "variable_cost_per_unit", "fixed_opex",
               "payroll", "depreciation", "interest_expense", "minimum_cash",
               "monthly_capex", "monthly_debt_proceeds", "monthly_debt_repayment",
               "monthly_equity_contribution") and value < 0:
        raise RequestError("%s cannot be negative." % key)
    if key == "monthly_unit_growth" and not Decimal("-0.99") <= value <= 5:
        raise RequestError("monthly_unit_growth must be between -0.99 and 5.")
    if key in ("tax_rate", "collection_rate", "payment_rate"):
        maximum = 1 if key == "tax_rate" else 2
        if not 0 <= value <= maximum:
            raise RequestError("%s must be between 0 and %s." % (key, maximum))
    return str(value)


def create_workspace(store: Store, payload: Mapping[str, Any]) -> Dict[str, Any]:
    company = _clean_text(payload.get("company_name"), "company_name", 120)
    currency = _clean_text(payload.get("currency", "USD"), "currency", 3).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise RequestError("currency must be a three-letter ISO-style code.")
    start_period = _clean_text(payload.get("start_period"), "start_period", 7)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", start_period):
        raise RequestError("start_period must use YYYY-MM format.")
    horizon = payload.get("horizon", 24)
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 60:
        raise RequestError("horizon must be a whole number between 1 and 60 months.")
    provided = payload.get("assumptions", {})
    if not isinstance(provided, dict):
        raise RequestError("assumptions must be an object.")
    assumptions = {
        key: definition[0] for key, definition in DEFAULT_ASSUMPTIONS.items()
    }
    for key, value in provided.items():
        if key.endswith("_rationale") or key.endswith("_source"):
            assumptions[key] = _clean_text(value, key, 500)
        elif key in assumptions:
            assumptions[key] = _validate_assumption(key, value)
        else:
            raise RequestError("Unknown financial assumption.")
    for required in ("starting_units", "unit_price", "variable_cost_per_unit", "fixed_opex", "payroll", "opening_cash"):
        if required not in provided:
            raise RequestError("%s is required to create a plan." % required)
    store.create_workspace(company, currency, start_period, horizon, assumptions)
    return get_workspace(store)


def _raw_assumptions(workspace: Mapping[str, Any]) -> Dict[str, str]:
    return {
        key: item["value"] for key, item in workspace["assumptions"].items()
    }


def _model_for_scenario(workspace: Mapping[str, Any], scenario: Mapping[str, Any]) -> Dict[str, Any]:
    assumptions = _raw_assumptions(workspace)
    assumptions.update(scenario["overrides"])
    result = calculate_plan(assumptions, workspace["start_period"], workspace["horizon"])
    return {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "overrides": scenario["overrides"],
        "periods": result["periods"],
        "totals": result["totals"],
    }


def get_workspace(store: Store) -> Dict[str, Any]:
    workspace = store.get_workspace()
    if workspace is None:
        return {"workspace": None}
    models = [_model_for_scenario(workspace, scenario) for scenario in workspace["scenarios"]]
    investment = None
    if workspace["investment"] is not None:
        inputs = workspace["investment"]
        investment = {
            "inputs": inputs,
            "results": calculate_investment(
                inputs["initial_investment"],
                inputs["annual_cash_flow"],
                inputs["years"],
                inputs["discount_rate"],
                inputs["residual_value"],
            ),
        }
    response = {
        "workspace": {
            "company_name": workspace["company_name"],
            "currency": workspace["currency"],
            "start_period": workspace["start_period"],
            "horizon": workspace["horizon"],
            "created_at": workspace["created_at"],
            "assumptions": workspace["assumptions"],
            "models": models,
            "investment": investment,
            "audit_events": store.list_audit_events(),
        }
    }
    return to_json_value(response)


def update_assumption(store: Store, key: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    if "value" not in payload:
        raise RequestError("value is required.")
    value = _validate_assumption(key, payload["value"])
    reason = _clean_text(payload.get("reason", "Assumption updated"), "reason", 500)
    store.update_assumption(key, value, reason)
    return get_workspace(store)


def create_scenario(store: Store, payload: Mapping[str, Any]) -> Dict[str, Any]:
    name = _clean_text(payload.get("name"), "name", 80)
    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise RequestError("overrides must be an object.")
    validated = {
        key: _validate_assumption(key, value) for key, value in overrides.items()
    }
    identifier = store.create_scenario(name)
    for key, value in validated.items():
        store.update_scenario_override(
            identifier, key, value, "Scenario created"
        )
    return get_workspace(store)


def update_scenario_override(
    store: Store, scenario_id: int, key: str, payload: Mapping[str, Any]
) -> Dict[str, Any]:
    if "value" not in payload:
        raise RequestError("value is required.")
    value = _validate_assumption(key, payload["value"])
    reason = _clean_text(payload.get("reason", "Scenario assumption updated"), "reason", 500)
    store.update_scenario_override(scenario_id, key, value, reason)
    return get_workspace(store)


def save_investment(store: Store, payload: Mapping[str, Any]) -> Dict[str, Any]:
    required = ("initial_investment", "annual_cash_flow", "years", "discount_rate")
    missing = [key for key in required if key not in payload]
    if missing:
        raise RequestError("%s is required." % ", ".join(missing))
    years = payload["years"]
    if isinstance(years, bool) or not isinstance(years, int) or not 1 <= years <= 40:
        raise RequestError("years must be a whole number between 1 and 40.")
    initial = decimal_value(payload["initial_investment"], "initial_investment")
    if initial <= 0:
        raise RequestError("initial_investment must be greater than zero.")
    annual = decimal_value(payload["annual_cash_flow"], "annual_cash_flow")
    rate = decimal_value(payload["discount_rate"], "discount_rate")
    residual = decimal_value(payload.get("residual_value", "0"), "residual_value")
    if rate <= -1:
        raise RequestError("discount_rate must be greater than -1 (-100%).")
    calculate_investment(initial, annual, years, rate, residual)
    store.save_investment(str(initial), str(annual), years, str(rate), str(residual))
    return get_workspace(store)
