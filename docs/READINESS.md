# Readiness and remaining work

## Verified in this implementation

- [x] Local application has a setup flow and server-rendered static assets.
- [x] SQLite workspace, assumptions, scenarios, overrides, and investment data persist.
- [x] Decimal-based monthly P&L, cash flow, break-even, NPV, IRR search, and payback calculations.
- [x] Scenario overrides are kept separate from base assumptions.
- [x] CSV export uses the shared calculation service.
- [x] Explicit synthetic sample seed command refuses duplicate workspace creation.
- [x] Unit and persistence tests run using Python `unittest`.
- [x] Local run and test commands documented.

## Not implemented or not verified

- [ ] React/Vite frontend, FastAPI, PostgreSQL, Alembic migrations, Docker, or CI.
- [ ] Authentication, secure sessions, role permissions, tenant isolation, or email workflows.
- [ ] Actuals imports, budget-versus-actual, plan approvals, concurrency controls, and financial audit approval.
- [ ] Working-capital timing, collections/payment schedules, headcount plans, fiscal calendars, debt schedules, or multi-currency conversion.
- [ ] Excel/PDF reports and the requested portfolio workbook/document set.
- [ ] Browser end-to-end testing, load testing, dependency scanning, production deployment, backups, or restore verification.
- [ ] Security review of a production configuration.

## Readiness assessment

**Local prototype foundation only. Not production-ready.** The app stores financial inputs in plaintext SQLite and has no authentication or tenant boundary. The HTTP server is deliberately restricted to loopback but is not a substitute for a hardened deployment. Forecast and appraisal outputs are illustrative and should be independently reviewed before business use.

