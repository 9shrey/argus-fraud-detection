# Architecture

## Goal

Score transactions for fraud risk in real time, explain every score, and make
the whole thing demoable end to end — not a notebook with a model.pkl at the
end, a running system with a UI.

## Data flow

```
SimulationEngine (asyncio background task, app/engine.py)
  │
  ├─ generate_live_tick()            synthetic transaction(s), "now" timestamp
  │    (app/simulator/generator.py + fraud_patterns.py)
  │
  ├─ fetch_history()                 this user's prior transactions from DB,
  │    (app/engine.py)                ascending by timestamp, strictly before
  │                                   this event — same contract training uses
  │
  ├─ compute_features()              causal feature vector — velocity windows,
  │    (app/features/engineering.py)  amount z-score, geo/device anomaly flags,
  │                                   category frequency, cyclical time encoding
  │
  ├─ FraudScorer.score()             XGBoost probability + Isolation Forest
  │    (app/ml/scorer.py)             anomaly score → hybrid 0-100 risk score,
  │                                   + SHAP reason codes
  │
  ├─ persist (Transaction, Alert)    Postgres/SQLite via SQLAlchemy
  │
  └─ broadcast over WebSocket        every connected dashboard tab gets the
       (app/websocket_manager.py)     scored transaction + alert (if flagged)
```

The frontend never computes anything — it renders what the backend already
decided. The only client-side state is a rolling window of the last ~40
WebSocket events (`lib/useStream.ts`); everything else (`/transactions`,
`/alerts`, `/metrics`, `/explain/:id`) is fetched fresh from the API.

## The five synthetic fraud scenarios

`app/simulator/fraud_patterns.py`. Each is a believable *stimulus* — the
model has to actually learn to recognize the pattern from features, nothing
here hardcodes "if scenario == X, flag it":

| Scenario | What it looks like | What should catch it |
|---|---|---|
| `account_takeover` | One large purchase, brand-new device, city the account has never used | `is_new_device`, `is_new_city_for_user`, `amount_zscore_user` |
| `impossible_travel` | Amount looks normal; city differs from the immediately-prior transaction within a 2-hour window | `impossible_travel_flag` |
| `card_testing_burst` | 4-7 tiny (₹1-99) transactions, seconds apart, new device | `txn_count_1h`, `same_category_burst_count_30m`, `is_small_amount` |
| `structuring_burst` | 3-4 transactions each just under a synthetic reporting threshold, minutes apart | `structuring_threshold_ratio`, `txn_count_24h` |
| `merchant_category_anomaly` | Amount is unremarkable; category is one the user has never touched | `category_freq_user`, `is_high_abuse_category` |

**A bug worth keeping on record:** early on, every scenario's default
merchant category fell back to a small `HIGH_ABUSE_CATEGORIES` list, which
made `is_high_abuse_category` an almost-perfect predictor by construction —
ROC-AUC 0.997 driven mostly by one feature. Fixed by making category
selection an opt-in per scenario (`account_takeover`/`impossible_travel` now
span every category, since a hijacked account can buy anything — the real
tell is the device/geo anomaly, not what got purchased). Re-training after
the fix produced a much more realistic, multi-feature importance spread —
see `/metrics`. The lesson: a suspiciously clean offline metric is worth
checking for a feature that's accidentally encoding the label.

## Feature set

19 features, all computed causally (no access to the transaction's own
label, and `history` never includes anything at or after the current
transaction's timestamp). Full list and rationale in
`app/features/engineering.py`'s `compute_features()` docstring; broad
categories:

- **Amount anomaly** — raw amount, log-amount, z-score against the user's
  own history.
- **Velocity** — transaction count and amount sum in 1h/24h windows, a
  same-category count in a 30-minute window (the card-testing signal).
- **Geography** — new-city flag, impossible-travel flag (different city than
  the immediately-prior transaction within 2 hours).
- **Device** — new-device flag.
- **Category** — how often this user transacts in this category, whether the
  category is one commonly abused for cash-out/resale.
- **Time** — cyclical hour-of-day encoding, an unusual-hour flag.
- **Structuring** — amount as a ratio of a synthetic reporting threshold.

## Model

`app/ml/train.py`, run offline (`uv run python -m app.ml.train`), writes
artifacts consumed by `app/ml/scorer.py` at runtime.

- **XGBoost classifier** (supervised) — `scale_pos_weight` corrects for the
  ~14% synthetic fraud rate (elevated vs. real-world fraud on purpose, so the
  demo has enough positive examples to be interesting; see the README's
  limitations section).
- **Isolation Forest** (unsupervised) — trained on the same (mostly-normal)
  training rows with no labels. The point of adding it: it can flag an
  anomaly shape the supervised model never saw labeled as fraud during
  training, which is a real failure mode a labels-only classifier has no way
  to catch.
- **Hybrid score** — `risk = 100 × (0.75 × xgb_probability + 0.25 ×
  normalized_isolation_score)`. Weights are a simple, documented choice, not
  tuned against a validation set — there isn't a second labeled split to
  tune against without further reducing the training set.
- **Chronological split** — train on the earlier 80% of 45 days of synthetic
  history, test on the later 20%. A random shuffle would let the model see
  "future" transactions from the same user during training, inflating every
  metric in a way that wouldn't hold up against tomorrow's transactions in
  production.
- **SHAP** — `shap.TreeExplainer` wraps the raw XGBoost `Booster` directly
  (not the sklearn wrapper), built once at scorer startup and reused for
  every request (~1-5ms per explanation, negligible next to the ensemble
  scoring itself). Explains the model's raw log-odds output, per SHAP's
  standard convention for tree models — sign and relative magnitude are
  what's meaningful, not an exact sum to the displayed 0-100 score.

## API surface

| Route | Purpose |
|---|---|
| `GET /transactions` | Paginated transaction list, optional `flagged_only` |
| `GET /transactions/{id}` | Single transaction |
| `GET /alerts` | Recent flagged transactions, denormalized with merchant/amount |
| `GET /metrics` | The offline evaluation report (`app/ml/train.py`'s output) |
| `GET /explain/{id}` | Recomputes the full SHAP explanation on demand |
| `GET/POST /stream/*` | Status, start, stop, rate control for the simulation |
| `WS /stream/ws` | Live transaction + alert broadcast |

`/explain` recomputes rather than storing the explanation at ingest time —
a transaction's stored row is just `risk_score`/`is_flagged`; the full
feature vector and SHAP breakdown are cheap enough (tens of milliseconds) to
regenerate from the same history the original scoring call used, so there's
no need to persist and version a larger blob per transaction.

## Design decisions and trade-offs

- **Sync SQLAlchemy, not async.** The simulator does a few DB round-trips a
  second, not thousands — sync SQLAlchemy in a `Depends(get_db)` (regular
  routes) or pushed to a worker thread via `asyncio.to_thread` (the
  simulation engine's background tick) is simpler than an async ORM stack
  and fast enough at this scale. The one subtlety: `WebSocket.send_text` is
  bound to the event loop it was accepted on, so the broadcast itself has to
  happen back on the main loop after `await`ing the worker-thread result —
  not inside the thread.
- **No Alembic.** `Base.metadata.create_all()` on startup. Appropriate for a
  single-service demo with no schema history to preserve across
  environments; a real production system (see career-os, a much larger
  project of mine, for the Alembic version of this decision) would want
  migrations.
- **No auth.** Single-demo-user scope. The simulation controls
  (`/stream/start`, `/stream/stop`) are open on purpose — this is a portfolio
  demo, not a multi-tenant service.
- **Feature parity is enforced by sharing one function, not by convention.**
  `compute_features()` is called from both `app/ml/train.py` (looping over
  historical events) and `app/ml/scorer.py` (one call per live transaction).
  There's no second implementation to drift out of sync with the first.
