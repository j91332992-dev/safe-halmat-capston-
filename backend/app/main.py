from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from .database import init_database
from .routers import ALL_ROUTERS
from .websocket import manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


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

