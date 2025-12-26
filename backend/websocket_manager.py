from fastapi import WebSocket
from typing import List, Set
import logging
import json

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_ids: Set[str] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept and register new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        connection_id = id(websocket)
        self.connection_ids.add(str(connection_id))
        logger.info(f"✅ New WebSocket connection: {connection_id}. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            connection_id = id(websocket)
            self.connection_ids.discard(str(connection_id))
            logger.info(f"❌ WebSocket disconnected: {connection_id}. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
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
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)