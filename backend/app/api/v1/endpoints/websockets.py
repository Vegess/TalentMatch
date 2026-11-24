from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models import User
from app.services.realtime import manager

router = APIRouter()


@router.websocket("/ws")
async def ws(websocket: WebSocket, token: str = Query("")):
    """Live notifications. Connect with ?token=<access token>."""
    data = decode_access_token(token)
    if not data:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    try:
        user = db.get(User, int(data["sub"]))
        ok = bool(user and user.is_active)
        uid, is_admin = (user.id, user.role == "admin") if ok else (0, False)
    finally:
        db.close()
    if not ok:
        await websocket.close(code=4401)
        return
    await manager.connect(websocket, uid, is_admin)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, uid)
