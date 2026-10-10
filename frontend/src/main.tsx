import {StrictMode} from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter} from "react-router-dom";
import {StatusBar, Style} from "@capacitor/status-bar";
import {Capacitor} from "@capacitor/core";
import App from "./App";
import "./styles.css";
import "./mobile-theme.css";
import "./mobile-operations.css";
import "./contrast.css";
import "./control-room.css";
import "./admin-green-theme.css";

// Let the browser calculate the actual mobile viewport.  Hard-coding a
// visualViewport value here can be stale during iOS Home Screen startup and
// creates an artificial horizontal layout area until device rotation.
document.documentElement.dataset.touchViewport = "";
document.documentElement.style.removeProperty("--app-viewport-width");

// 1. Configure Native Mobile Status Bar for iOS & Android
if (Capacitor.isNativePlatform()) {
  void StatusBar.setStyle({style: Style.Light}).catch(() => {});
  void StatusBar.setBackgroundColor({color: "#06101a"}).catch(() => {});
  void StatusBar.setOverlaysWebView({overlay: false}).catch(() => {});
}

// 2. iOS Safari WebKit Safe Service Worker Handler
// WebKit crashes ("WebKit에 내부 오류 발생") if ServiceWorker is registered on insecure HTTP IP.
// ServiceWorker must ONLY run in HTTPS / secure contexts in production.
if ("serviceWorker" in navigator) {
  if (import.meta.env.PROD && window.isSecureContext && !Capacitor.isNativePlatform()) {
    window.addEventListener("load", () => {
      try {
        navigator.serviceWorker
          .register("/sw.js")
          .catch(err => {
            console.warn("PWA ServiceWorker registration ignored:", err);
          });
      } catch (e) {
        console.warn("ServiceWorker not supported in this context:", e);
      }
    });
  } else {
    // In dev mode or insecure HTTP IP, unregister any dangling service workers that break Safari
    try {
      navigator.serviceWorker.getRegistrations().then(registrations => {
        for (const registration of registrations) {
          void registration.unregister();
        }
      }).catch(() => {});
    } catch {
      // ignore
    }
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
