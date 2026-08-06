import type { Alert, Explanation, Metrics, StreamStatus, Transaction } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  transactions: (params: { limit?: number; flaggedOnly?: boolean } = {}) => {
    const qs = new URLSearchParams();
    if (params.limit) qs.set("limit", String(params.limit));
    if (params.flaggedOnly) qs.set("flagged_only", "true");
    return get<Transaction[]>(`/transactions?${qs.toString()}`);
  },
  transaction: (id: string) => get<Transaction>(`/transactions/${id}`),
  alerts: (limit = 25) => get<Alert[]>(`/alerts?limit=${limit}`),
  metrics: () => get<Metrics>("/metrics"),
  explain: (id: string) => get<Explanation>(`/explain/${id}`),
  streamStatus: () => get<StreamStatus>("/stream/status"),
  streamStart: (rateTps?: number) =>
    post<StreamStatus>("/stream/start", rateTps ? { rate_tps: rateTps } : undefined),
  streamStop: () => post<StreamStatus>("/stream/stop"),
  streamRate: (rateTps: number) => post<StreamStatus>("/stream/rate", { rate_tps: rateTps }),
};

export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/stream/ws";
