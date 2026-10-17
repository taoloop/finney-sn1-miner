"""Unit tests for the energy_arbitrage candidate (stdlib unittest; run via miner.py check)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

TRACK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (TRACK_DIR, os.path.join(TRACK_DIR, "vendor")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import miner  # noqa: E402
import solution  # noqa: E402
from competition.energy_arbitrage.python.challenge import Challenge, Track  # noqa: E402
from competition.energy_arbitrage.python.scenarios import Scenario  # noqa: E402


def _instance(seed_byte: int = 0, scenario: Scenario = Scenario.BASELINE) -> Challenge:
    return Challenge.generate_instance(bytes([seed_byte] * 32), Track(s=scenario))


class PolicyContract(unittest.TestCase):
    def test_actions_are_valid_every_step(self):
        challenge = _instance(1)
        seen = []

        def checked(view, state):
            action = solution.policy(view, state)
            self.assertEqual(len(action), view.num_batteries)
            for a, (lo, hi) in zip(action, state.action_bounds):
                self.assertGreaterEqual(a, lo)
                self.assertLessEqual(a, hi)
            seen.append(state.time_step)
            return action

        # take_step raises on out-of-bounds actions or line-flow violations.
        challenge.grid_optimize(checked)
        self.assertEqual(seen, list(range(challenge.num_steps)))

    def test_policy_only_gets_public_view(self):
        view = _instance(2).to_policy_view()
        self.assertFalse(hasattr(view, "_hidden_seed"))
        self.assertFalse(hasattr(view.market, "generate_rt_prices"))

    def test_beats_upstream_baseline_on_fixed_seeds(self):
        for seed_byte in (0, 3):
            challenge = _instance(seed_byte)
            profit = challenge.evaluate_total_profit(challenge.grid_optimize(solution.policy))
            _, baseline = challenge.compute_baseline()
            self.assertGreater(profit, baseline, f"seed {seed_byte}")

    def test_replan_on_new_instance(self):
        a, b = _instance(4), _instance(5)
        pa = a.evaluate_total_profit(a.grid_optimize(solution.policy))
        b.evaluate_total_profit(b.grid_optimize(solution.policy))
        self.assertEqual(pa, a.evaluate_total_profit(a.grid_optimize(solution.policy)))


class StaticRules(unittest.TestCase):
    def test_candidate_passes(self):
        self.assertEqual(miner.static_problems(), [])

    def test_rejects_forbidden_access(self):
        bad = "import os\n\ndef policy(view, state):\n    return view._hidden_seed\n"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(bad)
        try:
            problems = miner.static_problems(f.name)
        finally:
            os.unlink(f.name)
        self.assertTrue(any("'os'" in p for p in problems))
        self.assertTrue(any("_hidden_seed" in p for p in problems))

    def test_summary_matches_upstream_floor_average(self):
        rows = [
            {"scenario": "BASELINE", "quality": 3, "profit": 1.0, "baseline_profit": 1.0, "policy_seconds": 0.1},
            {"scenario": "DENSE", "quality": -4, "profit": 1.0, "baseline_profit": 1.0, "policy_seconds": 0.1},
        ]
        self.assertEqual(miner.summarise(rows)["metrics"]["avg_quality"], -1)


if __name__ == "__main__":
    unittest.main()
