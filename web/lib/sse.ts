"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { SseEvent } from "./types";

const RECONNECT_DELAY_MS = 1_000;

interface UseSseOptions {
  enabled?: boolean;
  onEvent?: (e: SseEvent) => void;
}

export function useSSE(url: string, options: UseSseOptions = {}) {
  const { enabled = true, onEvent } = options;
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastIdRef = useRef<string>(
    typeof window !== "undefined" ? sessionStorage.getItem(`sse:lastId:${url}`) ?? "" : "",
  );
  const sourceRef = useRef<EventSource | null>(null);
  const cancelledRef = useRef(false);

  const connect = useCallback(() => {
    if (cancelledRef.current) return;
    const sep = url.includes("?") ? "&" : "?";
    const full = lastIdRef.current
      ? `${url}${sep}last_event_id=${encodeURIComponent(lastIdRef.current)}`
      : url;
    const es = new EventSource(full, { withCredentials: true });
    sourceRef.current = es;
    es.onopen = () => {
      setConnected(true);
      setError(null);
    };
    es.onmessage = (raw) => {
      try {
        const parsed = JSON.parse(raw.data) as SseEvent;
        if (raw.lastEventId) {
          lastIdRef.current = raw.lastEventId;
          sessionStorage.setItem(`sse:lastId:${url}`, raw.lastEventId);
        }
        setEvents((prev) => [...prev, parsed]);
        onEvent?.(parsed);
      } catch {
        // malformed — skip
      }
    };
    es.onerror = () => {
      setConnected(false);
      setError("연결이 끊겼습니다. 재시도 중…");
      es.close();
      if (!cancelledRef.current) {
        setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };
  }, [url, onEvent]);

  useEffect(() => {
    if (!enabled) return;
    cancelledRef.current = false;
    connect();
    return () => {
      cancelledRef.current = true;
      sourceRef.current?.close();
    };
  }, [enabled, connect]);

  const reset = useCallback(() => {
    setEvents([]);
    lastIdRef.current = "";
    sessionStorage.removeItem(`sse:lastId:${url}`);
  }, [url]);

  return { events, connected, error, reset };
}
