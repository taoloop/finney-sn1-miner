"""Apex energy_arbitrage submission: per-node stochastic DP over state of charge.

This single file is what `apex submit` uploads. It must stay self-contained:
the only imports allowed are the standard library and
`competition.energy_arbitrage.python.*` (present in the evaluator image).

Idea
----
* Profit at step t is settled at ``state.rt_prices`` which the policy already
  sees, so the current-step decision is exact; only the future is uncertain.
* Future RT prices are modelled from public data only: day-ahead prices, the
  network PTDF (congestion probability), and the documented RT price model
  (multiplicative Gaussian shock, congestion premium, Pareto jumps).
* At step 0 a backward DP is solved once per battery node on a normalised
  state-of-charge grid. Batteries differ only by a size factor m, so one value
  function per node serves every battery placed on it.
* Each step, every battery picks the action maximising
  ``immediate profit + m * V[t+1](soc')``; the joint action is then softened
  until all line flows are within limits.

Never touch hidden seeds, the evaluator process, the filesystem or future RT
prices: the policy only receives ``view`` (PolicyView) and ``state``.
"""

from __future__ import annotations

import math

try:
    from competition.energy_arbitrage.python import constants as C
except ImportError:  # pragma: no cover - local fallback mirrors upstream values
    C = None

DT = C.DELTA_T if C else 0.25
KAPPA_TX = C.KAPPA_TX if C else 0.25
KAPPA_DEG = C.KAPPA_DEG if C else 1.0
BETA_DEG = C.BETA_DEG if C else 2.0
EPS_FLOW = C.EPS_FLOW if C else 1e-6
LAMBDA_MIN = C.LAMBDA_MIN if C else -200.0
LAMBDA_MAX = C.LAMBDA_MAX if C else 5000.0
GAMMA_PRICE = C.GAMMA_PRICE if C else 20.0
NOMINAL_CAPACITY = C.NOMINAL_CAPACITY if C else 100.0
NOMINAL_POWER = C.NOMINAL_POWER if C else 25.0
ETA_C = C.ETA_CHARGE if C else 0.95
ETA_D = C.ETA_DISCHARGE if C else 0.95
X_MIN = C.E_MIN_FRAC if C else 0.10
X_MAX = C.E_MAX_FRAC if C else 0.90

# Tunables (the obvious knobs for an improvement loop).
GRID_POINTS = 41  # SOC grid resolution for the DP
DP_ACTIONS = (-1.0, -0.5, 0.0, 0.5, 1.0)  # fractions of rated power used in the DP
DECISION_ACTIONS = 21  # actions tried per battery at decision time
# 3-point Gauss-Hermite quadrature for a standard normal shock.
SHOCK_NODES = ((-math.sqrt(3.0), 1.0 / 6.0), (0.0, 2.0 / 3.0), (math.sqrt(3.0), 1.0 / 6.0))
DEFAULT_SIGMA = 0.20
# Public scenario table (scenarios.py): num_nodes -> (sigma, rho_jump, tail_index).
SCENARIO_PRIORS = {
    20: (0.10, 0.01, 4.0),
    40: (0.15, 0.02, 3.5),
    80: (0.20, 0.03, 3.0),
    100: (0.25, 0.04, 2.7),
    150: (0.30, 0.05, 2.5),
}
MAX_SOFTEN_ITERS = 64
SCALE_BSEARCH_ITERS = 32
EPS = 1e-12

_CACHE: dict = {}


# ---------------------------------------------------------------------------
# Price model
# ---------------------------------------------------------------------------


def _line_flows(view, injections: list[float]) -> list[float]:
    n = view.network.num_nodes
    return [sum(row[k] * injections[k] for k in range(n)) for row in view.network.ptdf]


def _congestion_probability(view, exo: list[float]) -> list[float]:
    """P(node flagged congested) given exogenous injections (mirrors network.py)."""
    net = view.network
    inj = list(exo)
    slack = net.slack_bus
    inj[slack] = 0.0
    inj[slack] = -sum(inj)
    flows = _line_flows(view, inj)
    p_free = [1.0] * net.num_nodes
    for l, flow in enumerate(flows):
        denom = net.congestion_threshold * net.flow_limits[l]
        if denom <= 0.0:
            continue
        p = min((abs(flow) / denom) ** 10.0, 1.0)
        a, b = net.lines[l]
        p_free[a] *= 1.0 - p
        p_free[b] *= 1.0 - p
    return [1.0 - q for q in p_free]


def _price_samples(view) -> list[list[list[tuple[float, float]]]]:
    """samples[t][node] = [(price, weight), ...] for future steps."""
    sigma, rho_jump, tail = SCENARIO_PRIORS.get(view.network.num_nodes, (DEFAULT_SIGMA, 0.03, 3.0))
    jump_mult = rho_jump * (tail / (tail - 1.0)) if tail > 1.0 else 0.0
    premium_unit = GAMMA_PRICE / math.sqrt(2.0 * math.pi)  # GAMMA * E[max(z, 0)]
    da = view.market.day_ahead_prices
    samples = []
    for t in range(view.num_steps):
        # Prices at t use congestion drawn from exogenous injections at t-1.
        p_cong = _congestion_probability(view, view.exogenous_injections[max(t - 1, 0)])
        row = []
        for node in range(view.network.num_nodes):
            d = da[t][node]
            extra = premium_unit * p_cong[node] + d * jump_mult
            row.append(
                [(max(LAMBDA_MIN, min(d * (1.0 + sigma * z) + extra, LAMBDA_MAX)), w) for z, w in SHOCK_NODES]
            )
        samples.append(row)
    return samples


# ---------------------------------------------------------------------------
# Dynamic programme (normalised battery: capacity 100 MWh, power 25 MW)
# ---------------------------------------------------------------------------


def _interp(values: list[float], x: float) -> float:
    pos = (x - X_MIN) / (X_MAX - X_MIN) * (GRID_POINTS - 1)
    if pos <= 0.0:
        return values[0]
    if pos >= GRID_POINTS - 1:
        return values[-1]
    i = int(pos)
    f = pos - i
    return values[i] * (1.0 - f) + values[i + 1] * f


def _next_x(x: float, u_frac: float) -> float:
    """Normalised SOC after acting with u_frac of rated power (u<0 charges)."""
    u = u_frac * NOMINAL_POWER
    if u < 0.0:
        x2 = x + ETA_C * (-u) * DT / NOMINAL_CAPACITY
    else:
        x2 = x - u * DT / (ETA_D * NOMINAL_CAPACITY)
    return max(X_MIN, min(x2, X_MAX))


def _solve_node(samples_by_t: list[list[tuple[float, float]]], num_steps: int) -> list[list[float]]:
    grid = [X_MIN + (X_MAX - X_MIN) * g / (GRID_POINTS - 1) for g in range(GRID_POINTS)]
    # Pre-compute feasible transitions once: (x', energy MW, cost) per grid point/action.
    moves = []
    for x in grid:
        opts = []
        for a in DP_ACTIONS:
            u = a * NOMINAL_POWER
            if u < 0.0:
                u = -min(-u, (X_MAX - x) * NOMINAL_CAPACITY / (ETA_C * DT))
            elif u > 0.0:
                u = min(u, (x - X_MIN) * NOMINAL_CAPACITY * ETA_D / DT)
            frac = u / NOMINAL_POWER
            cost = KAPPA_TX * abs(u) * DT + KAPPA_DEG * (abs(u) * DT / NOMINAL_CAPACITY) ** BETA_DEG
            opts.append((_next_x(x, frac), u * DT, cost))
        moves.append(opts)
    values = [[0.0] * GRID_POINTS for _ in range(num_steps + 1)]
    for t in range(num_steps - 1, 0, -1):
        nxt = values[t + 1]
        cont = [[_interp(nxt, x2) for (x2, _, _) in opts] for opts in moves]
        cur = values[t]
        for g in range(GRID_POINTS):
            opts = moves[g]
            c = cont[g]
            ev = 0.0
            for price, w in samples_by_t[t]:
                best = -1e18
                for k, (_, energy, cost) in enumerate(opts):
                    v = energy * price - cost + c[k]
                    if v > best:
                        best = v
                ev += w * best
            cur[g] = ev
    return values


def _plan(view) -> dict:
    samples = _price_samples(view)
    nodes = sorted({b.node for b in view.batteries})
    values = {n: _solve_node([samples[t][n] for t in range(view.num_steps)], view.num_steps) for n in nodes}
    return {"values": values}


# ---------------------------------------------------------------------------
# Flow feasibility
# ---------------------------------------------------------------------------


def _violation(view, state, action):
    flows = _line_flows(view, view.compute_total_injections(state, action))
    worst = None
    for l, flow in enumerate(flows):
        limit = view.network.flow_limits[l]
        excess = abs(flow) - limit
        if excess > EPS_FLOW * limit and (worst is None or excess > worst[2]):
            worst = (l, flow, excess)
    return worst


def _make_feasible(view, state, action: list[float]) -> list[float]:
    action = list(action)
    ptdf = view.network.ptdf
    for _ in range(MAX_SOFTEN_ITERS):
        worst = _violation(view, state, action)
        if worst is None:
            return action
        line, flow, excess = worst
        sign = 1.0 if flow > 0 else -1.0
        idx = [i for i, b in enumerate(view.batteries) if sign * ptdf[line][b.node] * action[i] > EPS]
        strength = sum(sign * ptdf[line][view.batteries[i].node] * action[i] for i in idx)
        if strength <= EPS:
            break
        keep = max(0.0, min(1.0 - excess / strength, 1.0))
        if keep >= 1.0 - EPS:
            break
        for i in idx:
            action[i] *= keep
    if _violation(view, state, action) is None:
        return action
    zero = [0.0] * len(action)
    if _violation(view, state, zero) is not None:
        return zero  # grid infeasible regardless; nothing better is possible
    low, high = 0.0, 1.0
    for _ in range(SCALE_BSEARCH_ITERS):
        mid = 0.5 * (low + high)
        if _violation(view, state, [mid * u for u in action]) is None:
            low = mid
        else:
            high = mid
    return [low * u for u in action]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def policy(view, state) -> list[float]:
    key = id(view)
    if state.time_step == 0 or _CACHE.get("key") != key:
        _CACHE.clear()
        _CACHE["key"] = key
        _CACHE["plan"] = _plan(view)
    values = _CACHE["plan"]["values"]
    t = state.time_step
    action = [0.0] * view.num_batteries
    for i, b in enumerate(view.batteries):
        lo, hi = state.action_bounds[i]
        if hi - lo <= EPS:
            action[i] = max(lo, min(0.0, hi))
            continue
        m = b.capacity_mwh / NOMINAL_CAPACITY
        nxt = values[b.node][t + 1] if t + 1 < len(values[b.node]) else None
        price = state.rt_prices[b.node]
        soc = state.socs[i]
        candidates = {min(hi, max(lo, lo + (hi - lo) * k / (DECISION_ACTIONS - 1))) for k in range(DECISION_ACTIONS)}
        candidates.add(0.0)  # lo <= 0 <= hi always holds
        best_u, best_v = 0.0, -1e18
        for u in sorted(candidates):
            au = abs(u)
            v = u * price * DT - KAPPA_TX * au * DT - KAPPA_DEG * (au * DT / b.capacity_mwh) ** BETA_DEG
            if nxt is not None:
                soc2 = b.apply_action_to_soc(u, soc)
                v += m * _interp(nxt, soc2 / b.capacity_mwh)
            if v > best_v + 1e-9:
                best_u, best_v = u, v
        action[i] = best_u
    return _make_feasible(view, state, action)
