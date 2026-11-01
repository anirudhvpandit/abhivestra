import tempfile
import unittest
from pathlib import Path

from abhivestra.service import (
    RequestError,
    create_scenario,
    create_workspace,
    get_workspace,
    update_assumption,
)
from abhivestra.storage import Store


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp_dir.name) / "test.sqlite3"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_workspace_persists_assumptions_and_audit(self):
        create_workspace(
            self.store,
            {
                "company_name": "Test Company",
                "currency": "USD",
                "start_period": "2026-01",
                "horizon": 12,
                "assumptions": {
                    "starting_units": "10",
                    "unit_price": "100",
                    "variable_cost_per_unit": "40",
                    "fixed_opex": "100",
                    "payroll": "200",
                    "opening_cash": "1000",
                },
            },
        )
        update_assumption(self.store, "unit_price", {"value": "110", "reason": "Price update"})
        loaded = get_workspace(self.store)["workspace"]
        self.assertEqual(loaded["company_name"], "Test Company")
        self.assertEqual(loaded["assumptions"]["unit_price"]["value"], "110")
        self.assertEqual(loaded["models"][0]["periods"][0]["revenue"], "1100.00")
        self.assertEqual(loaded["audit_events"][0]["entity"], "assumption")

    def test_scenario_override_isolated_from_base_and_invalid_scenario_is_atomic(self):
        create_workspace(
            self.store,
            {
                "company_name": "Scenario Test",
                "currency": "USD",
                "start_period": "2026-01",
                "horizon": 12,
                "assumptions": {
                    "starting_units": "10",
                    "unit_price": "100",
                    "variable_cost_per_unit": "40",
                    "fixed_opex": "100",
                    "payroll": "200",
                    "opening_cash": "1000",
                },
            },
        )
        with self.assertRaises(RequestError):
            create_scenario(self.store, {"name": "Invalid", "overrides": {"not_a_driver": "1"}})
        loaded = get_workspace(self.store)["workspace"]
        self.assertEqual(len(loaded["models"]), 1)

        create_scenario(
            self.store, {"name": "Upside", "overrides": {"monthly_unit_growth": "0.1"}}
        )
        loaded = get_workspace(self.store)["workspace"]
        base = next(model for model in loaded["models"] if model["scenario_name"] == "Base Case")
        upside = next(model for model in loaded["models"] if model["scenario_name"] == "Upside")
        self.assertEqual(base["periods"][1]["revenue"], "1000.00")
        self.assertEqual(upside["periods"][1]["revenue"], "1100.00")


if __name__ == "__main__":
    unittest.main()
