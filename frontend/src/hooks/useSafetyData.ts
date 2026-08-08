import {useCallback, useEffect, useRef, useState} from "react";
import {api} from "../services/api";
import type {LocationPoint, Snapshot, Worker} from "../types";

export function useSafetyData() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [locationHistory, setLocationHistory] = useState<Record<string, LocationPoint[]>>({});
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      const snapshot = await api.snapshot();
      setData(snapshot);
      const histories = await Promise.all(
        snapshot.workers.map(async worker => {
          try {
            return [worker.worker_id, await api.locationHistory(worker.worker_id)] as const;
          } catch {
            return [worker.worker_id, []] as const;
          }
        })
      );
      setLocationHistory(Object.fromEntries(histories));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "서버 연결에 실패했습니다.");
    }
  }, []);

  useEffect(() => {
    void refresh();
    timer.current = window.setInterval(refresh, 1000);
    const configured = import.meta.env.VITE_WS_URL;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsBase = configured ?? `${protocol}://${window.location.host}`;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let disposed = false;

    const connect = () => {
      socket = new WebSocket(`${wsBase}/ws/dashboard`);
      socket.onopen = () => {
        setConnected(true);
        socket?.send("dashboard-ready");
      };
      socket.onmessage = event => {
        try {
          const message = JSON.parse(event.data) as {
            type: string;
            data?: {worker?: Worker; location?: {x: number; y: number; confidence: number}};
          };
          if (message.type === "location" && message.data?.worker && message.data.location) {
            const worker = message.data.worker;
            const location = message.data.location;
            const receivedAt = new Date().toISOString();
            setData(current => current ? {
              ...current,
              workers: current.workers.map(item => item.worker_id === worker.worker_id ? worker : item),
              devices: current.devices.map(device => device.worker_id === worker.worker_id && device.device_type === "position_device"
                ? {...device, online: true, last_uwb_at: receivedAt, last_seen: receivedAt}
                : device)
            } : current);
            setLocationHistory(current => {
              const points = [...(current[worker.worker_id] ?? []), {
                x: location.x,
                y: location.y,
                confidence: location.confidence,
                created_at: receivedAt
              }].slice(-500);
              return {...current, [worker.worker_id]: points};
            });
            return;
          }
        } catch {
          // 형식을 알 수 없는 메시지는 전체 동기화로 복구합니다.
        }
        void refresh();
      };
      socket.onclose = () => {
        setConnected(false);
        if (!disposed) reconnectTimer = window.setTimeout(connect, 1000);
      };
      socket.onerror = () => {
        setConnected(false);
        socket?.close();
      };
    };

    connect();
    return () => {
      disposed = true;
      window.clearInterval(timer.current);
      window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [refresh]);

  return {data, locationHistory, connected, error, refresh};
}