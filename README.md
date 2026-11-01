# AbhiVestra

AbhiVestra is a local-first financial planning and scenario analysis application. It contains a persistent SQLite workspace, a standalone `Decimal` calculation engine, a versioned JSON API, a browser interface, scenario overrides, cash-flow forecasts, break-even outputs, a capital investment calculator, an explicitly invoked sample-data seed, and CSV export.

> **Readiness:** This is a working local foundation, not a production-ready SaaS. It has no authentication, tenant isolation, approvals, fiscal-calendar support, or production deployment hardening. Do not expose the built-in server to a network or use its outputs as approved financial statements.

## Requirements

- Python 3.9 or newer.
- No third-party Python packages or frontend build tools are required.

The original requested React/FastAPI/PostgreSQL stack could not be used in the available environment (Python 3.9.6; Node.js/npm and FastAPI unavailable). This implementation uses only the Python standard library and ships a self-contained HTML/CSS/JavaScript client. That is a deliberate runtime-compatible deviation, not an assertion that the requested stack has been delivered.

## Run locally

```sh
python3 run.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The server binds to loopback only. Data is stored in `data/abhivestra.sqlite3`; set `ABHIVESTRA_DB` to use another local path. `ABHIVESTRA_PORT` changes the port. The app rejects non-loopback bind addresses.

Create a workspace through the setup form. To load the clearly synthetic, pre-populated Northstar example instead, stop the server and run:

```sh
python3 seed_sample.py
python3 run.py
```

The seed command refuses to overwrite an existing workspace. The sample start month can be changed with `--start-period YYYY-MM`. Back up the SQLite file before moving or replacing it; there is no automated backup or migration framework yet.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile run.py seed_sample.py abhivestra/*.py tests/*.py
```

## Implemented workflows

- Create one local company workspace and a monthly forecast of up to 60 periods.
- Edit base financial assumptions and record a reason for each change.
- Review P&L, cash movements, reserve alerts, and monthly break-even calculations.
- Create isolated what-if scenarios, edit overrides, and compare calculated outputs.
- Save a simple annual cash-flow investment appraisal with NPV, an IRR search, payback, and profitability index.
- Export the base forecast as CSV.
- Review recent changes in the local audit event table.

All workspaces use the same financial calculation functions. See [the calculation conventions](docs/FINANCIAL_MODEL.md), [API reference](docs/API.md), [architecture](docs/ARCHITECTURE.md), and [readiness and limitations](docs/READINESS.md).

## Security and privacy

This application is designed for local evaluation. It has a shared local workspace and no sign-in, authorization, tenant isolation, CSRF token, rate limiting, database encryption, or hardened deployment configuration. Financial data is written in plaintext to the configured SQLite database. Keep the service on a trusted machine, do not port-forward it, and do not treat the local audit table as tamper-resistant.

