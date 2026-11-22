# Contributing

1. `pip install -e ".[dev]"`
2. Make your change with tests.
3. `ruff format . && ruff check . && pytest` must all pass.

Rules for financial logic: use `Decimal` only, keep every finding traceable to a file and row,
and never present a finding as a confirmed loss.
