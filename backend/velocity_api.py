"""
Garcar Enterprise — Velocity API endpoints
Mount onto app.py: app.register_blueprint(velocity_bp)

Endpoints:
  GET  /velocity          — full quantitative speed dashboard
  GET  /velocity/score    — single throughput score (QUANTUM/HYPERSONIC/etc)
  POST /velocity/emit     — inject event directly into priority bus
  GET  /velocity/hash     — holographic speed fingerprint
"""
from flask import Blueprint, jsonify, request
from backend.speed_engine import speed, Priority

velocity_bp = Blueprint('velocity', __name__)


@velocity_bp.route('/velocity', methods=['GET'])
def velocity_dashboard():
    return jsonify(speed.full_velocity_report())


@velocity_bp.route('/velocity/score', methods=['GET'])
def velocity_score():
    report = speed.bus.velocity_report()
    return jsonify({
        "score": report["throughput_score"],
        "ops_per_sec": report["ops_per_sec"],
        "p99_ms": report["p99_ms"],
        "queue_depth": report["queue_depth"],
    })


@velocity_bp.route('/velocity/emit', methods=['POST'])
def emit_event():
    data = request.get_json() or {}
    system = data.get('system', 'notion_sync')
    payload = data.get('payload', {})
    priority_str = data.get('priority', 'HIGH').upper()
    priority_map = {
        'CRITICAL': Priority.CRITICAL,
        'HIGH': Priority.HIGH,
        'MEDIUM': Priority.MEDIUM,
        'LOW': Priority.LOW,
        'BACKGROUND': Priority.BACKGROUND,
    }
    priority = priority_map.get(priority_str, Priority.HIGH)
    speed.emit_event(system, payload, priority)
    return jsonify({"queued": True, "system": system, "priority": priority_str})


@velocity_bp.route('/velocity/hash', methods=['GET'])
def velocity_hash():
    return jsonify({
        "holographic_speed_hash": speed.bus.holographic_speed_hash(),
        "timestamp": __import__('time').time(),
    })
