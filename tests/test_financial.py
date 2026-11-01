import unittest
from decimal import Decimal

from abhivestra.financial import (
    ModelInputError,
    calculate_investment,
    calculate_plan,
    period_label,
)


BASE = {
    "starting_units": "100",
    "monthly_unit_growth": "0",
    "unit_price": "10",
    "variable_cost_per_unit": "4",
    "fixed_opex": "300",
    "payroll": "100",
    "depreciation": "20",
    "interest_expense": "10",
    "tax_rate": "0.25",
    "opening_cash": "1000",
    "minimum_cash": "0",
    "collection_rate": "1",
    "payment_rate": "1",
    "monthly_capex": "50",
    "monthly_debt_proceeds": "0",
    "monthly_debt_repayment": "0",
    "monthly_equity_contribution": "0",
}


class FinancialModelTests(unittest.TestCase):
    def test_p_and_l_and_cash_reconciliation(self):
        result = calculate_plan(BASE, "2026-01", 2)
        first = result["periods"][0]
        self.assertEqual(first["revenue"], Decimal("1000.00"))
        self.assertEqual(first["cogs"], Decimal("400.00"))
        self.assertEqual(first["gross_profit"], Decimal("600.00"))
        self.assertEqual(first["ebitda"], Decimal("200.00"))
        self.assertEqual(first["ebit"], Decimal("180.00"))
        self.assertEqual(first["profit_before_tax"], Decimal("170.00"))
        self.assertEqual(first["tax_expense"], Decimal("42.50"))
        self.assertEqual(first["net_income"], Decimal("127.50"))
        self.assertEqual(
            first["closing_cash"],
            first["opening_cash"] + first["cash_inflows"] - first["cash_outflows"],
        )
        self.assertEqual(result["periods"][1]["opening_cash"], first["closing_cash"])

    def test_break_even(self):
        row = calculate_plan(BASE, "2026-01", 1)["periods"][0]
        self.assertEqual(row["contribution_per_unit"], Decimal("6.00"))
        self.assertEqual(row["break_even_units"], Decimal("66.67"))
        self.assertEqual(row["break_even_revenue"], Decimal("666.67"))

    def test_non_viable_contribution_has_no_break_even(self):
        values = dict(BASE, variable_cost_per_unit="12")
        row = calculate_plan(values, "2026-01", 1)["periods"][0]
        self.assertIsNone(row["break_even_units"])
        self.assertIsNone(row["break_even_revenue"])

    def test_growth_applies_from_second_period(self):
        values = dict(BASE, monthly_unit_growth="0.1")
        rows = calculate_plan(values, "2026-01", 2)["periods"]
        self.assertEqual(rows[1]["units"], Decimal("110.0"))

    def test_period_rollover(self):
        self.assertEqual(period_label("2026-12", 1), "2027-01")

    def test_invalid_horizon_rejected(self):
        with self.assertRaises(ModelInputError):
            calculate_plan(BASE, "2026-01", 0)

    def test_investment_npv_and_irr(self):
        result = calculate_investment("1000", "600", 2, "0.1")
        self.assertEqual(result["npv"], Decimal("41.32"))
        self.assertEqual(result["irr_status"], "single_solution")
        self.assertAlmostEqual(float(result["irr"]), 0.1306623863, places=7)
        self.assertEqual(result["simple_payback_years"], Decimal("1.67"))

    def test_investment_no_irr(self):
        result = calculate_investment("1000", "-100", 3, "0.1")
        self.assertEqual(result["irr_status"], "no_solution_in_search_range")
        self.assertIsNone(result["irr"])

    def test_multiple_irr_solutions_are_not_reported_as_one(self):
        result = calculate_investment("100", "230", 2, "0.1", "-360")
        self.assertEqual(result["irr_status"], "multiple_solutions")
        self.assertIsNone(result["irr"])

    def test_negative_discount_rate_below_minus_one_rejected(self):
        with self.assertRaises(ModelInputError):
            calculate_investment("100", "50", 2, "-1")


if __name__ == "__main__":
    unittest.main()
