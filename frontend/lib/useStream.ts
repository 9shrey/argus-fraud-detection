"use client";

import { useEffect, useRef, useState } from "react";
import { WS_URL } from "./api";
import type { StreamEvent } from "./types";

const MAX_FEED_LENGTH = 40;
const RECONNECT_DELAY_MS = 2000;

/** Connects to /stream/ws and keeps a rolling window of the most recent
 * events client-side — the backend is the source of truth for full history
 * (via /transactions, /alerts), this hook is just the live tail. */
export function useStream() {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(WS_URL);
      socketRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data) as StreamEvent;
          setEvents((prev) => [event, ...prev].slice(0, MAX_FEED_LENGTH));
        } catch {
          // ignore malformed frames
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      socketRef.current?.close();
    };
  }, []);

  return { events, connected };
}
