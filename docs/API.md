# API reference

All API routes are currently unauthed and intended for the local-only server at `http://127.0.0.1:8000`. JSON errors use `{"error":{"code":"...","message":"..."}}`. Request bodies are limited to 64 KB.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Local process health |
| GET | `/api/v1/workspace` | Workspace, assumptions, scenario calculations, investment results, and recent audit events |
| POST | `/api/v1/workspace` | Create the single workspace; required company, currency, start period, and core assumptions |
| PUT | `/api/v1/assumptions/{key}` | Update a base assumption; body: `{"value":"...","reason":"..."}` |
| POST | `/api/v1/scenarios` | Add a scenario; body: `{"name":"Downside","overrides":{"monthly_unit_growth":"-0.01"}}` |
| PUT | `/api/v1/scenarios/{id}/overrides/{key}` | Set a scenario-only assumption override |
| POST | `/api/v1/investment` | Save an investment appraisal and return recalculated outputs |
| GET | `/api/v1/export.csv` | Download the base-scenario monthly P&L and cash forecast |

Workspace creation requires `starting_units`, `unit_price`, `variable_cost_per_unit`, `fixed_opex`, `payroll`, and `opening_cash` inside the `assumptions` object. The remaining explicit model assumptions start from documented zero/neutral defaults.

Supported assumption keys are defined in `abhivestra/storage.py`. All routes operate on one local SQLite workspace; API IDs are not tenant-scoped because authentication and multi-tenancy are not implemented.

