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
  const terminatedRef = useRef(false);

  const connect = useCallback(() => {
    if (cancelledRef.current || terminatedRef.current) return;
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
        // 서버는 재연결 시 id=0의 synthetic started 이벤트를 흘려보낸다.
        // 새 id가 기존 stored 보다 클 때만 갱신해 lastId 0 회귀 → 중복 replay 방지.
        if (raw.lastEventId) {
          const newId = parseInt(raw.lastEventId, 10);
          const oldId = parseInt(lastIdRef.current || "0", 10);
          if (Number.isFinite(newId) && newId > oldId) {
            lastIdRef.current = raw.lastEventId;
            sessionStorage.setItem(`sse:lastId:${url}`, raw.lastEventId);
          }
        }
        setEvents((prev) => [...prev, parsed]);
        onEvent?.(parsed);
        if (parsed.type === "completed" || parsed.type === "error") {
          // terminal 이벤트 후 서버가 stream을 닫으면 브라우저는 onerror로 보고함.
          // 재연결 루프에 빠지지 않도록 flag set + close.
          terminatedRef.current = true;
          es.close();
          sourceRef.current = null;
          setConnected(false);
        }
      } catch {
        // malformed — skip
      }
    };
    es.onerror = () => {
      setConnected(false);
      if (terminatedRef.current) return;
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
    terminatedRef.current = false;
    sessionStorage.removeItem(`sse:lastId:${url}`);
  }, [url]);

  return { events, connected, error, reset };
}
