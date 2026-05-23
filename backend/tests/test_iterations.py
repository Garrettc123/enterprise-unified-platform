import pytest
from fastapi.testclient import TestClient
from backend.main import app


def _register_and_login(client):
    """Helper to register a user and get auth token"""
    client.post(
        "/api/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123",
            "full_name": "Test User"
        }
    )
    response = client.post(
        "/api/auth/login",
        data={"username": "testuser", "password": "testpass123"}
    )
    return response.json()["access_token"]


def _create_org_and_project(client, token):
    """Helper to create an organization and project"""
    # Create organization
    org_response = client.post(
        "/api/organizations",
        json={
            "name": "Test Org",
            "slug": "test-org",
            "description": "Test Organization"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    org_id = org_response.json()["id"]

    # Create project
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Test Project",
            "description": "Test Project Description",
            "organization_id": org_id
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    return org_id, project_response.json()["id"]


def test_create_iteration(client):
    """Test creating a new iteration"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    response = client.post(
        "/api/iterations",
        json={
            "name": "Sprint 1",
            "description": "First sprint",
            "project_id": project_id,
            "start_date": "2026-02-10T00:00:00",
            "end_date": "2026-02-24T00:00:00",
            "status": "planning",
            "goal": "Complete initial setup"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Sprint 1"
    assert data["project_id"] == project_id
    assert data["status"] == "planning"
    assert data["goal"] == "Complete initial setup"


def test_create_iteration_invalid_dates(client):
    """Test creating an iteration with end_date before start_date"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    response = client.post(
        "/api/iterations",
        json={
            "name": "Bad Sprint",
            "project_id": project_id,
            "start_date": "2026-02-24T00:00:00",
            "end_date": "2026-02-10T00:00:00",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "End date must be after start date" in response.json()["detail"]


def test_get_iteration(client):
    """Test getting an iteration by ID"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    # Create iteration
    create_response = client.post(
        "/api/iterations",
        json={
            "name": "Sprint 1",
            "project_id": project_id,
            "start_date": "2026-02-10T00:00:00",
            "end_date": "2026-02-24T00:00:00",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    iteration_id = create_response.json()["id"]

    # Get iteration
    response = client.get(
        f"/api/iterations/{iteration_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Sprint 1"


def test_get_iteration_not_found(client):
    """Test getting a non-existent iteration"""
    token = _register_and_login(client)

    response = client.get(
        "/api/iterations/999",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


def test_list_iterations(client):
    """Test listing iterations for a project"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    # Create two iterations
    for i in range(1, 3):
        client.post(
            "/api/iterations",
            json={
                "name": f"Sprint {i}",
                "project_id": project_id,
                "start_date": f"2026-0{i}-01T00:00:00",
                "end_date": f"2026-0{i}-14T00:00:00",
            },
            headers={"Authorization": f"Bearer {token}"}
        )

    response = client.get(
        f"/api/iterations?project_id={project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_update_iteration(client):
    """Test updating an iteration"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    # Create iteration
    create_response = client.post(
        "/api/iterations",
        json={
            "name": "Sprint 1",
            "project_id": project_id,
            "start_date": "2026-02-10T00:00:00",
            "end_date": "2026-02-24T00:00:00",
            "status": "planning",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    iteration_id = create_response.json()["id"]

    # Update iteration
    response = client.patch(
        f"/api/iterations/{iteration_id}",
        json={
            "name": "Sprint 1 - Updated",
            "status": "active"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sprint 1 - Updated"
    assert data["status"] == "active"


def test_update_iteration_invalid_dates(client):
    """Test that updating an iteration with invalid dates is rejected"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    # Create iteration
    create_response = client.post(
        "/api/iterations",
        json={
            "name": "Sprint 1",
            "project_id": project_id,
            "start_date": "2026-02-10T00:00:00",
            "end_date": "2026-02-24T00:00:00",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    iteration_id = create_response.json()["id"]

    # Update with end_date before start_date
    response = client.patch(
        f"/api/iterations/{iteration_id}",
        json={"end_date": "2026-02-05T00:00:00"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "End date must be after start date" in response.json()["detail"]


def test_delete_iteration(client):
    """Test deleting an iteration"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    # Create iteration
    create_response = client.post(
        "/api/iterations",
        json={
            "name": "Sprint 1",
            "project_id": project_id,
            "start_date": "2026-02-10T00:00:00",
            "end_date": "2026-02-24T00:00:00",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    iteration_id = create_response.json()["id"]

    # Delete iteration
    response = client.delete(
        f"/api/iterations/{iteration_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204

    # Verify it's deleted
    get_response = client.get(
        f"/api/iterations/{iteration_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 404


def test_iteration_tasks(client):
    """Test listing tasks assigned to an iteration"""
    token = _register_and_login(client)
    _, project_id = _create_org_and_project(client, token)

    # Create iteration
    iter_response = client.post(
        "/api/iterations",
        json={
            "name": "Sprint 1",
            "project_id": project_id,
            "start_date": "2026-02-10T00:00:00",
            "end_date": "2026-02-24T00:00:00",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    iteration_id = iter_response.json()["id"]

    # Create task in iteration
    client.post(
        "/api/tasks",
        json={
            "title": "Task in Sprint",
            "project_id": project_id,
            "iteration_id": iteration_id,
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Create task without iteration
    client.post(
        "/api/tasks",
        json={
            "title": "Backlog Task",
            "project_id": project_id,
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Get tasks for iteration
    response = client.get(
        f"/api/iterations/{iteration_id}/tasks",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Task in Sprint"
    assert data[0]["iteration_id"] == iteration_id

