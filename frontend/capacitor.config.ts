import type {CapacitorConfig} from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.hanmir.safesmarthelmet",
  appName: "한미르 안전관제",
  webDir: "dist",
  server: {androidScheme: "https", cleartext: true, allowNavigation: ["*"]},
  plugins: {
    StatusBar: {style: "LIGHT", backgroundColor: "#06101a", overlaysWebView: false},
    CapacitorCookies: {enabled: true},
    CapacitorHttp: {enabled: true}
  },
  android: {allowMixedContent: true, webContentsDebuggingEnabled: true},
  ios: {contentInset: "never", allowsLinkPreview: false, scrollEnabled: true}
};

export default config;
