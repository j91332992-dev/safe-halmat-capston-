import {useCallback, useEffect, useRef, useState} from "react";
import {api} from "../services/api";
import type {Snapshot} from "../types";

export function useSafetyData() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      setData(await api.snapshot());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "서버 연결에 실패했습니다.");
    }
  }, []);

  useEffect(() => {
    void refresh();
    timer.current = window.setInterval(refresh, 5000);
    const configured = import.meta.env.VITE_WS_URL;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsBase = configured ?? `${protocol}://${window.location.host}`;
    const socket = new WebSocket(`${wsBase}/ws/dashboard`);
    socket.onopen = () => {
      setConnected(true);
      socket.send("dashboard-ready");
    };
    socket.onmessage = () => void refresh();
    socket.onclose = () => setConnected(false);
    socket.onerror = () => setConnected(false);
    return () => {
      window.clearInterval(timer.current);
      socket.close();
    };
  }, [refresh]);

  return {data, connected, error, refresh};
}

