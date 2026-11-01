# Financial model specification

## Scope and conventions

The engine in `abhivestra/financial.py` is independent of the HTTP layer and persistence. Monetary inputs and calculations use Python `Decimal`; reported monetary values are rounded to two decimal places using the Decimal context's default half-even rounding. Assumptions are stored as decimal strings in SQLite. Currency is stored once on the workspace; no foreign-exchange conversion is performed.

The model forecasts monthly units, revenue, operating costs, and cash for a user-selected horizon. Monthly volume growth compounds from the second forecast period. Fractional unit volume is allowed. All periods use `YYYY-MM`.

## Inputs

The assumption register is persisted in the `assumption` table. Principal drivers are starting unit volume, monthly unit growth, selling price, variable unit cost, fixed operating expenses, payroll, depreciation, interest, tax rate, opening and reserve cash, same-period collection and payment proportions, capex, and debt/equity cash movements.

## Profit and loss

For each month:

- Revenue = forecast units × selling price per unit.
- COGS = forecast units × variable cost per unit.
- Gross profit = revenue − COGS.
- Operating expenses = fixed operating expenses + payroll and benefits.
- EBITDA = gross profit − operating expenses.
- EBIT = EBITDA − depreciation and amortization.
- Profit before tax = EBIT − interest expense.
- Tax = max(0, profit before tax × tax rate).
- Net income = profit before tax − tax.

Gross margin and EBITDA margin are `N/M` when revenue is zero.

## Cash flow and liquidity

- Cash collections = recognized revenue × same-period collection proportion.
- Operating payments = (COGS + operating expenses) × same-period payment proportion.
- Cash inflows = collections + debt proceeds + equity contributions.
- Cash outflows = operating payments + tax + interest + capex + debt principal repayment.
- Net cash movement = inflows − outflows.
- Closing cash = opening cash + net cash movement.
- The next month's opening cash equals the previous month's closing cash.

The calculation intentionally separates cash from net income. However, collection and payment proportions are same-period approximations. The model does not roll forward accounts receivable/payable, inventory, accrued expenses, tax balances, or deferred revenue, and it does not model transaction-level collection/payment dates.

## Break-even

- Contribution per unit = selling price − variable cost per unit.
- Monthly break-even units = (fixed operating expenses + payroll) / contribution per unit.
- Monthly break-even revenue = break-even units × selling price.
- Margin of safety = forecast revenue − break-even revenue.

If contribution per unit is zero or negative, break-even outputs are undefined (`null`) rather than infinite.

## Investment analysis

The investment screen models one initial outflow at time zero and a constant annual incremental cash flow at each year-end. Net terminal value (which can be negative for closure costs) is added to the final period. NPV discounts all cash flows at the selected annual rate. IRR uses a decimal bisection search over sign-changing intervals from -99.9% through 1000%; no solution in that search range and multiple detected solutions are reported explicitly. This numerical search can miss tangential roots or roots outside its range; IRR is not definitive for non-conventional cash flows.

Simple and discounted payback use linear interpolation within the year in which the initial investment is recovered. If it is not recovered inside the modeled term, payback is `null`. Profitability index is the present value of future inflows divided by the initial investment.

## Limitations

No actual-vs-budget model, fiscal year logic, multiple products, subscriptions, headcount schedules, revenue recognition, debt amortization schedules, working-capital ledger, opening receivables/payables, tax jurisdictions, multiple currencies, or approval workflow is implemented. Outputs are decision-support estimates and require finance review.
