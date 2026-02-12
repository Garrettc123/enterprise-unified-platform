import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app, raise_server_exceptions=False)


def test_openapi_json_available(client):
    """Test that the OpenAPI JSON schema is accessible"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["openapi"].startswith("3.")
    assert data["info"]["title"] == "Enterprise Unified Platform"
    assert data["info"]["version"] == "1.0.0"


def test_openapi_info_metadata(client):
    """Test that the OpenAPI info section contains contact and license"""
    response = client.get("/openapi.json")
    data = response.json()
    info = data["info"]
    assert "contact" in info
    assert info["contact"]["name"] == "Enterprise Platform Support"
    assert "license" in info
    assert info["license"]["name"] == "MIT"
    assert "description" in info
    assert "Authentication" in info["description"]


def test_openapi_tags_present(client):
    """Test that all API tag groups are documented"""
    response = client.get("/openapi.json")
    data = response.json()
    tag_names = [t["name"] for t in data.get("tags", [])]
    expected_tags = [
        "auth", "projects", "tasks", "organizations", "analytics",
        "notifications", "files", "search", "export", "audit",
    ]
    for tag in expected_tags:
        assert tag in tag_names, f"Tag '{tag}' missing from OpenAPI tags"
    # Each tag should have a description
    for tag in data["tags"]:
        assert tag.get("description"), f"Tag '{tag['name']}' has no description"


def test_openapi_endpoints_have_summaries(client):
    """Test that all endpoints have a summary for Swagger UI"""
    response = client.get("/openapi.json")
    data = response.json()
    for path, methods in data["paths"].items():
        for method, details in methods.items():
            assert "summary" in details, (
                f"{method.upper()} {path} is missing a summary"
            )


def test_openapi_schema_descriptions(client):
    """Test that Pydantic schemas have field descriptions"""
    response = client.get("/openapi.json")
    schemas = response.json()["components"]["schemas"]

    # Check a representative set of schemas have field descriptions
    for schema_name in ["UserCreate", "ProjectCreate", "TaskCreate", "Token"]:
        schema = schemas[schema_name]
        for field_name, field_info in schema.get("properties", {}).items():
            assert "description" in field_info, (
                f"{schema_name}.{field_name} is missing a description"
            )


def test_swagger_ui_available(client):
    """Test that Swagger UI page is served"""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_redoc_available(client):
    """Test that ReDoc page is served"""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "redoc" in response.text.lower()
