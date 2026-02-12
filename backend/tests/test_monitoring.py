import json
import logging
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.logging_config import (
    setup_logging,
    set_correlation_id,
    get_correlation_id,
    JSONFormatter,
    correlation_id_var,
)
from backend.monitoring import ApplicationMetrics, app_metrics


# ---------------------------------------------------------------------------
# Logging config tests
# ---------------------------------------------------------------------------

class TestCorrelationId:
    """Tests for correlation ID context management."""

    def test_set_and_get_correlation_id(self):
        cid = set_correlation_id("test-id-123")
        assert cid == "test-id-123"
        assert get_correlation_id() == "test-id-123"

    def test_auto_generate_correlation_id(self):
        cid = set_correlation_id()
        assert cid is not None
        assert len(cid) > 0
        assert get_correlation_id() == cid

    def test_get_default_is_none(self):
        correlation_id_var.set(None)
        assert get_correlation_id() is None


class TestJSONFormatter:
    """Tests for JSON structured log formatter."""

    def test_format_basic_record(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["message"] == "hello world"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_format_includes_correlation_id(self):
        set_correlation_id("fmt-test-id")
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="with cid",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["correlation_id"] == "fmt-test-id"

    def test_format_includes_extra_fields(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="extra",
            args=(),
            exc_info=None,
        )
        record.status_code = 200
        record.method = "GET"
        record.path = "/health"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["status_code"] == 200
        assert data["method"] == "GET"
        assert data["path"] == "/health"


class TestSetupLogging:
    """Tests for logging setup function."""

    def test_setup_default(self):
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) > 0

    def test_setup_json_format(self):
        setup_logging(json_format=True)
        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_setup_custom_level(self):
        setup_logging(log_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        # Restore default
        setup_logging(log_level="INFO")


# ---------------------------------------------------------------------------
# ApplicationMetrics tests
# ---------------------------------------------------------------------------

class TestApplicationMetrics:
    """Tests for the ApplicationMetrics collector."""

    def setup_method(self):
        self.metrics = ApplicationMetrics()

    def test_initial_state(self):
        m = self.metrics.get_metrics()
        assert m["total_requests"] == 0
        assert m["total_errors"] == 0
        assert m["error_rate_percent"] == 0.0
        assert m["active_requests"] == 0

    def test_record_request(self):
        self.metrics.record_request("GET", "/health", 200, 15.0)
        m = self.metrics.get_metrics()
        assert m["total_requests"] == 1
        assert m["total_errors"] == 0
        assert m["status_codes"] == {200: 1}
        assert "GET /health" in m["endpoints"]
        ep = m["endpoints"]["GET /health"]
        assert ep["count"] == 1
        assert ep["avg_duration_ms"] == 15.0

    def test_record_error(self):
        self.metrics.record_request("POST", "/api/data", 500, 100.0)
        m = self.metrics.get_metrics()
        assert m["total_errors"] == 1
        assert m["error_rate_percent"] == 100.0

    def test_active_request_tracking(self):
        self.metrics.increment_active()
        self.metrics.increment_active()
        assert self.metrics.get_metrics()["active_requests"] == 2
        self.metrics.decrement_active()
        assert self.metrics.get_metrics()["active_requests"] == 1

    def test_decrement_does_not_go_negative(self):
        self.metrics.decrement_active()
        assert self.metrics.get_metrics()["active_requests"] == 0

    def test_health_status_healthy(self):
        self.metrics.record_request("GET", "/ok", 200, 10.0)
        h = self.metrics.get_health()
        assert h["status"] == "healthy"

    def test_health_status_degraded(self):
        for _ in range(9):
            self.metrics.record_request("GET", "/ok", 200, 10.0)
        for _ in range(2):
            self.metrics.record_request("GET", "/err", 500, 10.0)
        h = self.metrics.get_health()
        assert h["status"] == "degraded"

    def test_health_status_unhealthy(self):
        self.metrics.record_request("GET", "/ok", 200, 10.0)
        for _ in range(3):
            self.metrics.record_request("GET", "/err", 500, 10.0)
        h = self.metrics.get_health()
        assert h["status"] == "unhealthy"

    def test_recent_errors_tracking(self):
        self.metrics.record_request("GET", "/fail", 404, 5.0)
        errors = self.metrics.get_recent_errors()
        assert len(errors) == 1
        assert errors[0]["status_code"] == 404
        assert errors[0]["path"] == "/fail"

    def test_recent_errors_capped(self):
        for i in range(60):
            self.metrics.record_request("GET", f"/err/{i}", 500, 1.0)
        errors = self.metrics.get_recent_errors()
        assert len(errors) == 50

    def test_reset(self):
        self.metrics.record_request("GET", "/test", 200, 10.0)
        self.metrics.reset()
        m = self.metrics.get_metrics()
        assert m["total_requests"] == 0

    def test_endpoint_min_max_duration(self):
        self.metrics.record_request("GET", "/ep", 200, 5.0)
        self.metrics.record_request("GET", "/ep", 200, 20.0)
        self.metrics.record_request("GET", "/ep", 200, 10.0)
        ep = self.metrics.get_metrics()["endpoints"]["GET /ep"]
        assert ep["min_duration_ms"] == 5.0
        assert ep["max_duration_ms"] == 20.0


# ---------------------------------------------------------------------------
# Monitoring API endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create test client, reset global metrics before each test."""
    app_metrics.reset()
    return TestClient(app)


class TestMonitoringEndpoints:
    """Tests for the /api/monitoring/* API endpoints."""

    def test_get_metrics(self, client):
        response = client.get("/api/monitoring/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "uptime_seconds" in data
        assert "endpoints" in data

    def test_get_health(self, client):
        response = client.get("/api/monitoring/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data

    def test_get_recent_errors(self, client):
        response = client.get("/api/monitoring/errors")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_health_check_includes_monitoring(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "error_rate_percent" in data

    def test_correlation_id_in_response(self, client):
        response = client.get("/health")
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) > 0

    def test_correlation_id_passthrough(self, client):
        response = client.get(
            "/health", headers={"X-Correlation-ID": "my-trace-id"}
        )
        assert response.headers["X-Correlation-ID"] == "my-trace-id"

    def test_metrics_record_requests(self, client):
        # Make several requests
        client.get("/health")
        client.get("/")
        client.get("/api/monitoring/metrics")

        response = client.get("/api/monitoring/metrics")
        data = response.json()
        # At least the requests above should be counted
        assert data["total_requests"] >= 3
