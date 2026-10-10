from contextlib import asynccontextmanager
import json
from time import monotonic

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from .database import get_db
from .models.entities import Device
from .routers.auth import require_site
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from .database import init_database, SessionLocal
from .models.entities import Device
from .services.orientation_service import record_orientation
from .routers import ALL_ROUTERS
from .routers.camera import start_camera_processor, stop_camera_processor
from .routers.auth import session_identity
from .websocket import call_manager, manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    await start_camera_processor()
    try:
        yield
    finally:
        await stop_camera_processor()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def restrict_worker_routes(request: Request, call_next):
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer ") and request.url.path.startswith("/api/"):
        try:
            identity = session_identity(authorization)
        except HTTPException:
            return await call_next(request)
        if identity.get("role") == "worker" and not request.url.path.startswith(("/api/worker-app/", "/api/auth/")):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "관리자 권한이 필요합니다."})
    return await call_next(request)


for router in ALL_ROUTERS:
    app.include_router(router)
app.mount("/captures", StaticFiles(directory=BASE_DIR / "captures"), name="captures")
app.mount("/tts", StaticFiles(directory=BASE_DIR / "tts_output"), name="tts")


@app.get("/")
def root():
    return {"name": settings.app_name, "status": "online", "mode": settings.operation_mode, "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": settings.operation_mode}


@app.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket, token: str = ""):
    try:
        identity = session_identity(f"Bearer {token}")
        if identity.get("role") == "worker":
            raise HTTPException(403, "관리자 권한이 필요합니다.")
    except HTTPException:
        await websocket.close(code=4401)
        return
    await manager.connect_dashboard(str(identity["site_id"]), websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/worker")
async def worker_socket(websocket: WebSocket, token: str = ""):
    try:
        identity = session_identity(f"Bearer {token}")
        if identity.get("role") != "worker" or not identity.get("worker_id"):
            raise HTTPException(403, "근로자 권한이 필요합니다.")
    except HTTPException:
        await websocket.close(code=4401)
        return
    await manager.connect_worker(str(identity["site_id"]), str(identity["worker_id"]), websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@app.websocket("/ws/device/{device_id}")
async def device_socket(websocket: WebSocket, device_id: str):
    await manager.connect_device(device_id, websocket)
    known_device = False
    device_site_id = None
    device_worker_id = None
    checked_at = -10.0
    try:
        while True:
            text = await websocket.receive_text()
            if len(text) > 512:
                continue
            try:
                message = json.loads(text)
            except (ValueError, TypeError):
                continue
            if not isinstance(message, dict) or message.get("type") != "orientation":
                continue
            if not known_device and monotonic() - checked_at >= 5:
                checked_at = monotonic()
                with SessionLocal() as db:
                    device = db.get(Device, device_id)
                    known_device = bool(device and device.device_type == "assistant_device")
                    device_site_id = device.site_id if known_device else None
                    device_worker_id = device.worker_id if known_device else None
            if known_device:
                sample = record_orientation(device_id, message)
                if sample:
                    sample["worker_id"] = device_worker_id
                    sample["site_id"] = device_site_id
                    await manager.broadcast("orientation", sample, site_id=device_site_id)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
@app.post("/api/calls/{device_id}/ticket")
def issue_call_ticket(device_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device or device.site_id != site_id:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    if not call_manager.device_online(device_id):
        raise HTTPException(409, "안전모 통화 채널이 오프라인입니다.")
    return {"device_id": device_id, "ticket": call_manager.issue_ticket(device_id), "expires_in": 30}


@app.get("/api/calls/{device_id}/status")
def call_status(device_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device or device.site_id != site_id:
        raise HTTPException(404, "장치를 찾을 수 없습니다.")
    return {"device_id": device_id, "channel_online": call_manager.device_online(device_id),
            "operator_connected": bool(call_manager.operators.get(device_id)),
            "traffic": call_manager.traffic.get(device_id, {})}


@app.websocket("/ws/call/device/{device_id}")
async def call_device_socket(websocket: WebSocket, device_id: str, token: str = ""):
    authorization = websocket.headers.get("authorization", "")
    if not token and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    connected = await call_manager.connect_device(device_id, token, websocket)
    if not connected:
        return
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") == '{"type":"call_stop"}':
                await call_manager.end_call(device_id)
            if message.get("bytes") is not None:
                await call_manager.relay_device_bytes(device_id, message["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        await call_manager.disconnect_device(device_id, websocket)


@app.websocket("/ws/call/operator/{device_id}")
async def call_operator_socket(websocket: WebSocket, device_id: str, ticket: str = ""):
    connected = await call_manager.connect_operator(device_id, ticket, websocket)
    if not connected:
        return
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") == '{"type":"call_stop"}':
                break
            if message.get("text") is not None:
                continue
            if message.get("bytes") is not None:
                await call_manager.relay_operator_bytes(device_id, message["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        await call_manager.disconnect_operator(device_id, websocket)
