import {useCallback, useEffect, useRef, useState} from "react";
import {App} from "@capacitor/app";
import {Network} from "@capacitor/network";
import {api} from "../services/api";
import {getWsBaseUrl} from "../services/config";
import type {LocationPoint, Snapshot, Worker} from "../types";

export type ConnectionState = "connected" | "connecting" | "reconnecting" | "offline" | "error";

export function useSafetyData() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [locationHistory, setLocationHistory] = useState<Record<string, LocationPoint[]>>({});
  const [connected, setConnected] = useState(false);
  const [serverReachable, setServerReachable] = useState(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const pollTimerRef = useRef<number | undefined>(undefined);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | undefined>(undefined);
  const heartbeatTimerRef = useRef<number | undefined>(undefined);
  const backoffRef = useRef<number>(2000);
  const attemptsRef = useRef<number>(0);
  const disposedRef = useRef<boolean>(false);
  const isConnectingRef = useRef<boolean>(false);

  const refresh = useCallback(async () => {
    try {
      const snapshot = await api.snapshot();
      setData(snapshot);
      setServerReachable(true);
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
      const msg = cause instanceof Error ? cause.message : "서버 연결에 실패했습니다.";
      setServerReachable(false);
      setError(msg);
    }
  }, []);

  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;

  const connectWebSocket = useCallback(() => {
    if (disposedRef.current || isConnectingRef.current) return;

    if (socketRef.current) {
      try {
        socketRef.current.onclose = null;
        socketRef.current.onerror = null;
        socketRef.current.close();
      } catch {
        // ignore
      }
      socketRef.current = null;
    }

    const wsBase = getWsBaseUrl();
    isConnectingRef.current = true;
    setConnectionState(attemptsRef.current > 0 ? "reconnecting" : "connecting");

    try {
      const socket = new WebSocket(`${wsBase}/ws/dashboard`);
      socketRef.current = socket;

      socket.onopen = () => {
        isConnectingRef.current = false;
        if (disposedRef.current) {
          socket.close();
          return;
        }
        setConnected(true);
        setConnectionState("connected");
        attemptsRef.current = 0;
        setReconnectAttempts(0);
        backoffRef.current = 2000;
        socket.send("dashboard-ready");

        // Start heartbeat ping
        if (heartbeatTimerRef.current) window.clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            try {
              socket.send(JSON.stringify({type: "ping", timestamp: Date.now()}));
            } catch {
              // ignore
            }
          }
        }, 15000);
      };

      socket.onmessage = event => {
        if (disposedRef.current) return;
        try {
          const message = JSON.parse(event.data) as {
            type: string;
            data?: {worker?: Worker; location?: {x: number; y: number; confidence: number}};
          };
          if (message.type === "pong") {
            return;
          }
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
          // ignore parse errors
        }
        void refreshRef.current();
      };

      socket.onclose = () => {
        isConnectingRef.current = false;
        if (heartbeatTimerRef.current) window.clearInterval(heartbeatTimerRef.current);
        setConnected(false);
        if (disposedRef.current) return;

        attemptsRef.current += 1;
        setReconnectAttempts(attemptsRef.current);
        setConnectionState("reconnecting");

        // Stable exponential backoff (min 3000ms, max 20000ms) to prevent socket flooding
        const delay = Math.min(backoffRef.current, 20000);
        backoffRef.current = Math.min(backoffRef.current * 1.5, 20000);

        if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = window.setTimeout(() => {
          connectWebSocket();
        }, delay);
      };

      socket.onerror = () => {
        isConnectingRef.current = false;
        setConnected(false);
        setConnectionState("error");

        // iOS Safari can keep a failed socket in CONNECTING/CLOSING state after
        // Wi-Fi returns and delay its close event.  Do not wait indefinitely for
        // that event: replace the stale socket shortly afterwards.
        window.setTimeout(() => {
          if (disposedRef.current || socketRef.current !== socket || socket.readyState === WebSocket.OPEN) return;
          connectWebSocket();
        }, 800);
      };
    } catch {
      isConnectingRef.current = false;
      setConnected(false);
      setConnectionState("error");
    }
  }, []);

  const forceReconnect = useCallback(() => {
    backoffRef.current = 2000;
    attemptsRef.current = 0;
    setReconnectAttempts(0);
    setConnectionState("connecting");
    if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current);
    void refresh();
    connectWebSocket();
  }, [connectWebSocket, refresh]);

  useEffect(() => {
    disposedRef.current = false;
    void refresh();
    pollTimerRef.current = window.setInterval(refresh, 3000);

    connectWebSocket();

    // 1. Mobile App lifecycle handler (Background -> Foreground)
    let appStateHandle: {remove: () => Promise<void>} | null = null;
    void App.addListener("appStateChange", state => {
      if (state.isActive) {
        void refresh();
        if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
          forceReconnect();
        }
      }
    }).then(h => {
      appStateHandle = h;
    }).catch(() => {});

    // 2. Mobile Network state change (Offline -> Online)
    let networkHandle: {remove: () => Promise<void>} | null = null;
    void Network.addListener("networkStatusChange", status => {
      if (status.connected) {
        void refresh();
        if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
          forceReconnect();
        }
      } else {
        setConnected(false);
        setConnectionState("offline");
      }
    }).then(h => {
      networkHandle = h;
    }).catch(() => {});

    // 3. Fallback window online/offline listeners
    const handleOnline = () => {
      void refresh();
      forceReconnect();
    };
    const handleOffline = () => {
      setConnected(false);
      setConnectionState("offline");
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      disposedRef.current = true;
      isConnectingRef.current = false;
      window.clearInterval(pollTimerRef.current);
      window.clearTimeout(reconnectTimerRef.current);
      window.clearInterval(heartbeatTimerRef.current);
      if (socketRef.current) {
        try {
          socketRef.current.onopen = null;
          socketRef.current.onmessage = null;
          socketRef.current.onclose = null;
          socketRef.current.onerror = null;
          socketRef.current.close();
        } catch {
          // ignore
        }
        socketRef.current = null;
      }
      if (appStateHandle) void appStateHandle.remove();
      if (networkHandle) void networkHandle.remove();
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []); // Only mount once!

  return {
    data,
    locationHistory,
    connected,
    serverReachable,
    connectionState,
    reconnectAttempts,
    error,
    refresh,
    forceReconnect
  };
}
