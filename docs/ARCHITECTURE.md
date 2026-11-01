# Architecture

## Runtime shape

```text
Browser (static HTML/CSS/JavaScript)
              │ same-origin JSON/CSV
              ▼
Python standard-library HTTP server (127.0.0.1 only)
       ├── service.py: validation and use cases
       ├── financial.py: Decimal calculation engine
       └── storage.py: SQLite schema and persistence
```

The browser does not calculate financial outputs: it requests the model from the API and formats returned values for display. The CSV exporter also calls the same workspace service and engine.

## Persistence

SQLite tables are initialized idempotently at application startup. Tables represent the single workspace, named assumptions, scenarios, scenario overrides, an optional capital investment, and change events. Financial assumptions are stored as text to preserve their decimal representation; every calculation converts and validates them as `Decimal`. API writes use SQL parameters and database transactions.

The service restricts user-editable keys to the known assumption register. Static serving allows only the bundled `index.html`, `styles.css`, and `app.js`. The local server caps JSON payload size and emits basic browser security headers.

## Deliberate deviations

The requested React, FastAPI, PostgreSQL, Alembic, Docker, Redis, CI, and third-party charting stack is not present and could not be run in the available environment. This implementation uses browser-native SVG and a standard-library server to provide a usable vertical slice without installing packages. It is not a substitute for an authenticated multi-tenant production architecture.

