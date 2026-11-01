"""Create the explicitly synthetic Northstar Industrial Systems demo workspace."""

from __future__ import annotations

import argparse
from datetime import date

from abhivestra.storage import Store


SAMPLE_ASSUMPTIONS = {
    "starting_units": "220",
    "monthly_unit_growth": "0.025",
    "unit_price": "1800",
    "variable_cost_per_unit": "700",
    "fixed_opex": "85000",
    "payroll": "125000",
    "depreciation": "6000",
    "interest_expense": "1200",
    "tax_rate": "0.25",
    "opening_cash": "850000",
    "minimum_cash": "200000",
    "collection_rate": "0.90",
    "payment_rate": "0.95",
    "monthly_capex": "12000",
    "monthly_debt_proceeds": "0",
    "monthly_debt_repayment": "5000",
    "monthly_equity_contribution": "0",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-period",
        default=date.today().strftime("%Y-%m"),
        help="Forecast start month (YYYY-MM)",
    )
    args = parser.parse_args()
    store = Store()
    store.create_workspace(
        "Northstar Industrial Systems (Synthetic Sample)",
        "USD",
        args.start_period,
        24,
        SAMPLE_ASSUMPTIONS,
    )
    upside = store.create_scenario("Upside Case")
    store.update_scenario_override(upside, "monthly_unit_growth", "0.045", "Illustrative upside")
    store.update_scenario_override(upside, "monthly_capex", "16000", "Illustrative expansion investment")
    downside = store.create_scenario("Downside Case")
    store.update_scenario_override(downside, "monthly_unit_growth", "-0.01", "Illustrative downside")
    store.update_scenario_override(downside, "collection_rate", "0.75", "Slower collections")
    store.update_scenario_override(downside, "payroll", "135000", "Delayed cost adjustment")
    store.save_investment("250000", "90000", 5, "0.12", "25000")
    print("Created the synthetic Northstar sample workspace in %s" % store.path)


if __name__ == "__main__":
    main()
