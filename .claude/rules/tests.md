---
paths:
  - "**/tests/**"
  - "**/*test*.py"
  - "**/*.{test,spec}.{ts,tsx,js,jsx}"
---
# Tests

- The test name states the behavior it protects.
- Assert on what the code sent or returned, not only on "no exception". A new test must fail without the change.
- No real network, no real sleeping, no dependence on test order. Inject the clock.
- Do not delete or weaken a failing test to get green. Do not hide collection or plugin errors.
