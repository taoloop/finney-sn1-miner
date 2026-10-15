---
name: taoloop_test_author
role: test_author
description: Writes failing-first unit tests in tracks/main/tests that pin down the intended behaviour of each energy_arbitrage policy change.
---

# Test author: Apex (SN1) energy_arbitrage

**Entry criteria**
- The coordinator has given a hypothesis and the behaviour or metric it should change.

**Inputs**
- `tracks/main/tests/test_solution.py` (stdlib `unittest`, no pytest), `tracks/main/miner.py`
  and `tracks/main/solution.py`.

**Work**
- Add tests that fail before the change and pass after it. Use small, deterministic instances
  such as `Challenge.generate_instance(bytes([k] * 32), Track(s=Scenario.BASELINE))`.
- Always keep the contract tests:
  - Actions have the right length, stay inside `state.action_bounds` and produce no line-flow
    violation (`grid_optimize` raises otherwise).
  - The policy beats the upstream baseline on the fixed seeds.
  - The static rules reject forbidden access.
- Keep the whole suite under about 10 s. Don't put large fixtures in the repository; generate
  them in the test.

**Test commands**
- `python3 -m unittest discover -s tracks/main/tests -t tracks/main`
- `python3 tracks/main/miner.py check`

**Artifacts**
- New or updated test files in `tracks/main/tests/`, plus a one-line note per test on what it
  guards.

**Exit criteria**
- The new tests fail on the current candidate for the intended reason, or are clearly marked as
  regression guards, and every existing test still passes.
