from fastapi import WebSocket
from typing import Dict, List, Optional, Set
import logging
import json

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time messaging"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.client_connections: Dict[str, WebSocket] = {}
        self.connection_ids: Set[str] = set()
        self.rooms: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None):
        """Accept and register new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        if client_id:
            self.client_connections[client_id] = websocket
        connection_id = str(id(websocket))
        self.connection_ids.add(connection_id)
        logger.info(
            f"✅ New WebSocket connection: {client_id or connection_id}. "
            f"Total: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket, client_id: Optional[str] = None):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            connection_id = str(id(websocket))
            self.connection_ids.discard(connection_id)
            if client_id and client_id in self.client_connections:
                del self.client_connections[client_id]
                # Remove from all rooms
                for room_id in list(self.rooms.keys()):
                    self.rooms[room_id].discard(client_id)
                    if not self.rooms[room_id]:
                        del self.rooms[room_id]
            logger.info(
                f"❌ WebSocket disconnected: {client_id or connection_id}. "
                f"Total: {len(self.active_connections)}"
            )

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def send_to_client(self, client_id: str, data: dict):
        """Send JSON message to a specific client by client_id"""
        websocket = self.client_connections.get(client_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps(data))
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                self.disconnect(websocket, client_id)

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_json(self, data: dict):
        """Broadcast JSON data to all connected clients"""
        await self.broadcast(json.dumps(data))

    def join_room(self, room_id: str, client_id: str):
        """Add a client to a room"""
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(client_id)
        logger.info(f"Client {client_id} joined room {room_id}")

    def leave_room(self, room_id: str, client_id: str):
        """Remove a client from a room"""
        if room_id in self.rooms:
            self.rooms[room_id].discard(client_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        logger.info(f"Client {client_id} left room {room_id}")

    async def broadcast_to_room(self, room_id: str, data: dict, exclude_client: Optional[str] = None):
        """Broadcast JSON message to all clients in a room"""
        if room_id not in self.rooms:
            return
        message = json.dumps(data)
        for client_id in list(self.rooms[room_id]):
            if client_id == exclude_client:
                continue
            websocket = self.client_connections.get(client_id)
            if websocket:
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending to {client_id} in room {room_id}: {e}")
                    self.disconnect(websocket, client_id)

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)

    def get_room_members(self, room_id: str) -> Set[str]:
        """Get client IDs of all members in a room"""
        return self.rooms.get(room_id, set()).copy()

    def get_client_ids(self) -> Set[str]:
        """Get all connected client IDs"""
        return set(self.client_connections.keys())