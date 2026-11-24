"""WebSocket fan-out. Each event carries `user_ids`; admins receive every event."""
from typing import Dict, List, Any
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder


class ConnectionManager:
    def __init__(self):
        self.by_user: Dict[int, List[WebSocket]] = {}
        self.admins: List[WebSocket] = []

    async def connect(self, ws: WebSocket, user_id: int, is_admin: bool):
        await ws.accept()
        self.by_user.setdefault(user_id, []).append(ws)
        if is_admin:
            self.admins.append(ws)

    def disconnect(self, ws: WebSocket, user_id: int):
        conns = self.by_user.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.by_user.pop(user_id, None)
        if ws in self.admins:
            self.admins.remove(ws)

    async def publish(self, event: Dict[str, Any]):
        targets: List[WebSocket] = []
        for uid in event.get("user_ids") or []:
            targets.extend(self.by_user.get(uid, []))
        if event.get("admins", True):  # personal notifications are not copied to the admin feed
            for ws in self.admins:
                if ws not in targets:
                    targets.append(ws)
        payload = jsonable_encoder({k: v for k, v in event.items() if k not in ("user_ids", "admins")})
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception as e:  # a closed socket shouldn't break the request, but log real bugs
                print(f"[realtime] send failed: {type(e).__name__}: {e}")


manager = ConnectionManager()


async def publish_all(events: List[Dict[str, Any]]):
    for e in events:
        await manager.publish(e)
