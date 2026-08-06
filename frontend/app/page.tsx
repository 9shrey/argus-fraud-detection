"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useStream } from "@/lib/useStream";
import type { Alert, StreamStatus } from "@/lib/types";
import { StatTile } from "@/components/StatTile";
import { RiskGauge } from "@/components/RiskGauge";
import { LiveFeed } from "@/components/LiveFeed";
import { AlertPanel } from "@/components/AlertPanel";

const RATE_OPTIONS = [1, 2, 5, 10, 20, 50];
const STATUS_POLL_MS = 2500;

export default function DashboardPage() {
  const { events, connected } = useStream();
  const [status, setStatus] = useState<StreamStatus | null>(null);
  const [initialAlerts, setInitialAlerts] = useState<Alert[]>([]);
  const [rate, setRate] = useState(5);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .alerts(15)
      .then(setInitialAlerts)
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const s = await api.streamStatus();
        if (!cancelled) {
          setStatus(s);
          setError(null);
        }
      } catch {
        if (!cancelled) setError("Can't reach the API — is the backend running?");
      }
    }
    poll();
    const id = setInterval(poll, STATUS_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  async function handleStart() {
    setBusy(true);
    try {
      setStatus(await api.streamStart(rate));
    } catch {
      setError("Failed to start the simulation.");
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    setBusy(true);
    try {
      setStatus(await api.streamStop());
    } finally {
      setBusy(false);
    }
  }

  async function handleRateChange(next: number) {
    setRate(next);
    if (status?.running) {
      setStatus(await api.streamRate(next));
    }
  }

  const liveAlerts: Alert[] = useMemo(
    () =>
      events
        .filter((e) => e.is_flagged && e.alert)
        .map((e) => ({
          id: e.id,
          transaction_id: e.id,
          user_id: e.user_id,
          risk_score: e.risk_score,
          top_reasons: e.alert?.top_reasons ?? [],
          created_at: e.timestamp,
          amount: e.amount,
          currency: e.currency,
          merchant: e.merchant,
          merchant_category: e.merchant_category,
          city: e.city,
          channel: e.channel,
        })),
    [events],
  );

  const combinedAlerts = useMemo(() => {
    const seen = new Set(liveAlerts.map((a) => a.transaction_id));
    return [...liveAlerts, ...initialAlerts.filter((a) => !seen.has(a.transaction_id))].slice(
      0,
      20,
    );
  }, [liveAlerts, initialAlerts]);

  const latestScore = events.length > 0 ? events[0]!.risk_score : null;
  const flagRate =
    status && status.total_generated > 0
      ? ((status.total_flagged / status.total_generated) * 100).toFixed(1) + "%"
      : "—";

  return (
    <>
      {error && (
        <div className="error-banner" style={{ marginBottom: 20 }}>
          {error}
        </div>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-body">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 16,
            }}
          >
            <div>
              <h1 style={{ fontSize: 20, margin: "0 0 4px" }}>Live transaction stream</h1>
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                Synthetic transactions, scored in real time by the XGBoost + Isolation Forest
                ensemble.
              </p>
            </div>
            <div className="btn-row">
              <span className="pill-connected">
                <span className={`pill-dot${connected ? " on" : ""}`} />
                {connected ? "Live" : "Disconnected"}
              </span>
              <select
                className="rate-select"
                value={rate}
                onChange={(e) => handleRateChange(Number(e.target.value))}
              >
                {RATE_OPTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r} txn/s
                  </option>
                ))}
              </select>
              {status?.running ? (
                <button type="button" className="btn btn-danger" disabled={busy} onClick={handleStop}>
                  Stop simulation
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={handleStart}
                >
                  Start simulation
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-stats" style={{ marginBottom: 20 }}>
        <StatTile label="Transactions scored" value={String(status?.total_generated ?? 0)} />
        <StatTile label="Flagged as fraud" value={String(status?.total_flagged ?? 0)} />
        <StatTile label="Flag rate" value={flagRate} />
        <StatTile
          label="Stream rate"
          value={status ? `${status.rate_tps.toFixed(0)} tx/s` : "—"}
          sub={status?.running ? "running" : "stopped"}
        />
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Live feed</h2>
              <p className="card-subtitle">Most recent {events.length} scored transactions</p>
            </div>
          </div>
          <div style={{ maxHeight: 520, overflowY: "auto" }}>
            <LiveFeed events={events} />
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="card">
            <div className="card-body">
              <RiskGauge score={latestScore} />
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Alerts</h2>
                <p className="card-subtitle">Flagged transactions, most recent first</p>
              </div>
            </div>
            <div style={{ maxHeight: 380, overflowY: "auto" }}>
              <AlertPanel alerts={combinedAlerts} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
