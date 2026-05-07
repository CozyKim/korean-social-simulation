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
  // 새 mount 시에는 항상 fresh start. lastId 는 같은 hook instance 의 reconnect (network drop)
  // 동안에만 유지된다. 페이지 새로고침/재방문 시 sessionStorage 잔존으로 완료된 run 의 replay
  // 가 N 이전 persona 이벤트를 skip 하던 버그 회피.
  const lastIdRef = useRef<string>("");
  const sourceRef = useRef<EventSource | null>(null);
  const cancelledRef = useRef(false);
  const terminatedRef = useRef(false);

  const connect = useCallback(() => {
    if (cancelledRef.current || terminatedRef.current) return;
    const sep = url.includes("?") ? "&" : "?";
    const withId = lastIdRef.current
      ? `${url}${sep}last_event_id=${encodeURIComponent(lastIdRef.current)}`
      : url;
    // BASE 가 빈 문자열이면 raw path 그대로 (dev: Next rewrites 사용).
    // BASE 가 설정된 경우 cross-origin 절대 URL — apiFetch 와 동일 패턴.
    // 그렇지 않으면 SSE 가 Next origin 에 붙어 쿠키 미포함 → 권한 거부.
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
    const full = `${base}${withId}`;
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
          // 서버는 재연결 시 id=0 의 synthetic started 이벤트를 흘려보낸다.
          // 새 id 가 기존 stored 보다 클 때만 갱신해 lastId 0 회귀 → 중복 replay 방지.
          if (Number.isFinite(newId) && newId > oldId) {
            lastIdRef.current = raw.lastEventId;
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
  }, []);

  return { events, connected, error, reset };
}
