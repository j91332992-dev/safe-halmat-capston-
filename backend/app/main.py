from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from .database import init_database
from .routers import ALL_ROUTERS
from .routers.camera import start_camera_processor, stop_camera_processor
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
async def dashboard_socket(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/device/{device_id}")
async def device_socket(websocket: WebSocket, device_id: str):
    await manager.connect_device(device_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
@app.post("/api/calls/{device_id}/ticket")
def issue_call_ticket(device_id: str, request: Request):
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(403, "통화 연결은 관제 서버 PC에서만 시작할 수 있습니다.")
    if not call_manager.device_online(device_id):
        raise HTTPException(409, "안전모 통화 채널이 오프라인입니다.")
    return {"device_id": device_id, "ticket": call_manager.issue_ticket(device_id), "expires_in": 30}


@app.websocket("/ws/call/device/{device_id}")
async def call_device_socket(websocket: WebSocket, device_id: str, token: str = ""):
    connected = await call_manager.connect_device(device_id, token, websocket)
    if not connected:
        return
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
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
