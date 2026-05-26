"""L5 — Off-scale gate.

Translates `m_total` into a binary presence signal using a Schmitt trigger
and a minimum-duration filter, then clamps `m_total` to 0 during off-scale frames.

Physical interpretation: when the mouse climbs the cage walls or hangs, no
weight reaches the floor and m_total reads ~ 0; we want downstream code to
see a hard zero instead of noisy near-zero residuals.
"""
from __future__ import annotations
import numpy as np

THETA_ON_G  = 5.0    # m_total must exceed this to declare "loaded"
THETA_OFF_G = 2.0    # m_total must drop below this to declare "off_scale"
MIN_DURATION_MS = 200  # ignore presence flips shorter than this


def schmitt_trigger(x: np.ndarray, theta_on: float = THETA_ON_G, theta_off: float = THETA_OFF_G,
                    start_loaded: bool = False) -> np.ndarray:
    """Return a bool array: True = loaded, False = off-scale.

    A simple state machine. Could be vectorised; the loop is fine at 500k samples.
    """
    n = len(x)
    state = np.empty(n, dtype=bool)
    is_on = start_loaded
    for i in range(n):
        v = x[i]
        if is_on and v < theta_off:
            is_on = False
        elif not is_on and v > theta_on:
            is_on = True
        state[i] = is_on
    return state


def remove_short_runs(state: np.ndarray, t_ms: np.ndarray, min_duration_ms: int = MIN_DURATION_MS) -> np.ndarray:
    """Flip any run of constant state whose duration < min_duration_ms.

    Operates in-place on a copy. Walk through runs; for each short run, flip it
    to merge with the surrounding longer state.
    """
    if len(state) == 0:
        return state.copy()
    out = state.copy()
    # Identify run boundaries via state changes
    change = np.diff(out.astype(np.int8))
    starts = np.concatenate(([0], np.where(change != 0)[0] + 1))
    ends   = np.concatenate((starts[1:], [len(out)]))  # exclusive
    for s, e in zip(starts, ends):
        run_dur = t_ms[e - 1] - t_ms[s] if e > s else 0
        if run_dur < min_duration_ms:
            out[s:e] = ~out[s:e]  # flip the short run
    return out


def apply_off_scale_gate(m_total: np.ndarray, t_ms: np.ndarray,
                         theta_on: float = THETA_ON_G, theta_off: float = THETA_OFF_G,
                         min_duration_ms: int = MIN_DURATION_MS) -> tuple[np.ndarray, np.ndarray]:
    """Return (m_total_gated, is_loaded).

    `m_total_gated` is `m_total` with off-scale frames clamped to 0.
    `is_loaded` is the bool gate after Schmitt + minimum-duration filtering.
    """
    raw_state = schmitt_trigger(m_total, theta_on=theta_on, theta_off=theta_off)
    cleaned   = remove_short_runs(raw_state, t_ms, min_duration_ms=min_duration_ms)
    gated     = np.where(cleaned, m_total, 0.0).astype(np.float32)
    return gated, cleaned
