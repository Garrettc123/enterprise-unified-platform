import pytest
import json
from fastapi.testclient import TestClient
from backend.main import app, ws_manager


@pytest.fixture(autouse=True)
def reset_ws_manager():
    """Reset WebSocket manager state between tests"""
    ws_manager.active_connections.clear()
    ws_manager.client_connections.clear()
    ws_manager.connection_ids.clear()
    ws_manager.rooms.clear()
    yield
    ws_manager.active_connections.clear()
    ws_manager.client_connections.clear()
    ws_manager.connection_ids.clear()
    ws_manager.rooms.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_websocket_connect_and_broadcast(client):
    """Test that a client can connect and broadcast messages"""
    with client.websocket_connect("/ws/user1") as ws:
        ws.send_text(json.dumps({"type": "message", "data": "hello"}))
        response = ws.receive_json()
        # First message is the system connect notification
        if response.get("type") == "system" and response.get("event") == "client_connected":
            response = ws.receive_json()
        assert response["type"] == "message"
        assert response["client_id"] == "user1"
        assert response["data"] == "hello"
        assert "timestamp" in response


def test_websocket_plain_text_fallback(client):
    """Test that plain text is treated as a broadcast message"""
    with client.websocket_connect("/ws/user1") as ws:
        ws.send_text("plain hello")
        response = ws.receive_json()
        if response.get("type") == "system":
            response = ws.receive_json()
        assert response["type"] == "message"
        assert response["data"] == "plain hello"


def test_websocket_ping_pong(client):
    """Test ping/pong heartbeat"""
    with client.websocket_connect("/ws/user1") as ws:
        # Drain the system connect message
        msg = ws.receive_json()
        assert msg["type"] == "system"

        ws.send_text(json.dumps({"type": "ping"}))
        response = ws.receive_json()
        assert response["type"] == "pong"
        assert "timestamp" in response


def test_websocket_disconnect_notification(client):
    """Test that disconnect sends a system notification"""
    with client.websocket_connect("/ws/user_a") as outer_ws:
        # Drain user_a connect notification
        outer_ws.receive_json()

        with client.websocket_connect("/ws/user_b") as inner_ws:
            # Both should get user_b connect notification
            msg_outer = outer_ws.receive_json()
            assert msg_outer["event"] == "client_connected"
            assert msg_outer["client_id"] == "user_b"
            inner_ws.receive_json()  # drain for user_b

        # user_b disconnected — outer should get disconnect notification
        disconnect_msg = outer_ws.receive_json()
        assert disconnect_msg["type"] == "system"
        assert disconnect_msg["event"] == "client_disconnected"
        assert disconnect_msg["client_id"] == "user_b"


def test_websocket_room_join_and_message(client):
    """Test joining a room and sending room messages"""
    with client.websocket_connect("/ws/alice") as ws_alice:
        ws_alice.receive_json()  # drain connect

        with client.websocket_connect("/ws/bob") as ws_bob:
            ws_alice.receive_json()  # drain bob connect
            ws_bob.receive_json()    # drain bob connect broadcast

            # Alice joins room first
            ws_alice.send_text(json.dumps({"type": "join_room", "room_id": "room1"}))
            # Alice sees her own join event
            ws_alice.receive_json()

            # Bob joins room
            ws_bob.send_text(json.dumps({"type": "join_room", "room_id": "room1"}))
            # Alice sees bob join event, bob sees his own join event
            ws_alice.receive_json()
            ws_bob.receive_json()

            # Alice sends a room message
            ws_alice.send_text(
                json.dumps({"type": "room_message", "room_id": "room1", "data": "hello room"})
            )
            # Both alice and bob should receive the room message
            msg_alice = ws_alice.receive_json()
            msg_bob = ws_bob.receive_json()
            assert msg_alice["type"] == "room_message"
            assert msg_alice["room_id"] == "room1"
            assert msg_alice["data"] == "hello room"
            assert msg_bob["type"] == "room_message"
            assert msg_bob["data"] == "hello room"


def test_websocket_direct_message(client):
    """Test sending a direct message to a specific client"""
    with client.websocket_connect("/ws/sender") as ws_sender:
        ws_sender.receive_json()  # drain connect

        with client.websocket_connect("/ws/receiver") as ws_receiver:
            ws_sender.receive_json()    # drain receiver connect
            ws_receiver.receive_json()  # drain receiver connect

            ws_sender.send_text(
                json.dumps({
                    "type": "direct",
                    "target_client_id": "receiver",
                    "data": "secret msg",
                })
            )
            # Receiver should get the direct message
            msg = ws_receiver.receive_json()
            assert msg["type"] == "direct"
            assert msg["client_id"] == "sender"
            assert msg["data"] == "secret msg"

            # Sender should also get echo
            echo = ws_sender.receive_json()
            assert echo["type"] == "direct"
            assert echo["data"] == "secret msg"
