import {useEffect, useState, useCallback} from "react";
import {Network, type ConnectionStatus, type ConnectionType} from "@capacitor/network";
import {Haptics, NotificationType} from "@capacitor/haptics";

export interface NetworkState {
  connected: boolean;
  connectionType: ConnectionType;
  lastChanged: Date;
}

export function useNetworkStatus(onOnline?: () => void, onOffline?: () => void) {
  const [networkState, setNetworkState] = useState<NetworkState>({
    connected: typeof navigator !== "undefined" ? navigator.onLine : true,
    connectionType: "unknown",
    lastChanged: new Date()
  });

  const checkStatus = useCallback(async () => {
    try {
      const status: ConnectionStatus = await Network.getStatus();
      setNetworkState(prev => {
        if (prev.connected !== status.connected) {
          if (status.connected) {
            onOnline?.();
            void Haptics.notification({type: NotificationType.Success}).catch(() => {});
          } else {
            onOffline?.();
            void Haptics.notification({type: NotificationType.Warning}).catch(() => {});
          }
        }
        return {
          connected: status.connected,
          connectionType: status.connectionType,
          lastChanged: new Date()
        };
      });
    } catch {
      // Fallback to browser navigator
      const online = navigator.onLine;
      setNetworkState({
        connected: online,
        connectionType: "unknown",
        lastChanged: new Date()
      });
    }
  }, [onOnline, onOffline]);

  useEffect(() => {
    void checkStatus();

    // 1. Capacitor Network Listener
    let listenerHandle: {remove: () => Promise<void>} | null = null;
    void Network.addListener("networkStatusChange", status => {
      setNetworkState(prev => {
        if (!prev.connected && status.connected) {
          onOnline?.();
          void Haptics.notification({type: NotificationType.Success}).catch(() => {});
        } else if (prev.connected && !status.connected) {
          onOffline?.();
          void Haptics.notification({type: NotificationType.Warning}).catch(() => {});
        }
        return {
          connected: status.connected,
          connectionType: status.connectionType,
          lastChanged: new Date()
        };
      });
    }).then(handle => {
      listenerHandle = handle;
    });

    // 2. Standard Browser Window fallback listeners
    const handleBrowserOnline = () => {
      setNetworkState(prev => ({...prev, connected: true, lastChanged: new Date()}));
      onOnline?.();
    };
    const handleBrowserOffline = () => {
      setNetworkState(prev => ({...prev, connected: false, lastChanged: new Date()}));
      onOffline?.();
    };

    window.addEventListener("online", handleBrowserOnline);
    window.addEventListener("offline", handleBrowserOffline);

    return () => {
      if (listenerHandle) {
        void listenerHandle.remove();
      }
      window.removeEventListener("online", handleBrowserOnline);
      window.removeEventListener("offline", handleBrowserOffline);
    };
  }, [checkStatus, onOnline, onOffline]);

  return {
    ...networkState,
    refreshStatus: checkStatus
  };
}
