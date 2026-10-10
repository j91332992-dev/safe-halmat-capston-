import {CapacitorHttp} from "@capacitor/core";
import {isCapacitorNative} from "./config";
import {auth} from "./api";

// Native HTTP avoids loading LAN HTTP images directly from the HTTPS WebView.
export async function loadCameraImage(url: string): Promise<string> {
  if (!isCapacitorNative()) return url;
  const token = auth.getToken();
  const response = await CapacitorHttp.get({url, responseType: "arraybuffer",
    headers: token ? {Authorization: `Bearer ${token}`} : {},
    connectTimeout: 4000, readTimeout: 4000});
  if (response.status !== 200 || typeof response.data !== "string") throw new Error("카메라 이미지 수신 실패");
  const bytes = Uint8Array.from(atob(response.data), value => value.charCodeAt(0));
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) throw new Error("JPEG 형식이 아닙니다");
  return URL.createObjectURL(new Blob([bytes], {type: "image/jpeg"}));
}

export function releaseCameraImage(url: string) {
  if (url.startsWith("blob:")) URL.revokeObjectURL(url);
}
