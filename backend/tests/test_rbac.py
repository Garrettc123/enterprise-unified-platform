"""Tests for role-based access control (RBAC) system."""

import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.main import app
from backend.database import get_db
from backend.models import Base, User, Organization, Project, Task, user_organization, project_team
from backend.security import get_password_hash
from backend.rbac import (
    OrganizationRole,
    ProjectRole,
    ORG_ROLE_HIERARCHY,
    PROJECT_ROLE_HIERARCHY,
    get_user_org_role,
    get_user_project_role,
    require_superuser,
    require_org_role,
    require_project_role,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _run(coro):
    """Helper to run async code in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


async def _setup_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


async def _create_session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory


@pytest.fixture(autouse=True)
def setup_db():
    """Set up in-memory SQLite database for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    engine = loop.run_until_complete(_setup_engine())
    factory = loop.run_until_complete(_create_session(engine))

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Clear rate limiter state between tests
    obj = app.middleware_stack
    while obj:
        if hasattr(obj, 'requests') and hasattr(obj, 'requests_per_minute'):
            obj.requests.clear()
            break
        obj = getattr(obj, 'app', None)

    yield {"engine": engine, "factory": factory, "loop": loop}
    loop.run_until_complete(engine.dispose())
    app.dependency_overrides.clear()
    loop.close()


@pytest.fixture
def client():
    return TestClient(app)


def _register_user(client, username="testuser", email="test@example.com", password="testpass123"):
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "full_name": f"Test {username}",
        },
    )


def _login_user(client, username="testuser", password="testpass123"):
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    return resp.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unit tests for role enums and hierarchy
# ---------------------------------------------------------------------------

class TestRoleEnums:
    def test_org_role_values(self):
        assert OrganizationRole.OWNER.value == "owner"
        assert OrganizationRole.ADMIN.value == "admin"
        assert OrganizationRole.MEMBER.value == "member"
        assert OrganizationRole.VIEWER.value == "viewer"

    def test_project_role_values(self):
        assert ProjectRole.ADMIN.value == "admin"
        assert ProjectRole.CONTRIBUTOR.value == "contributor"
        assert ProjectRole.VIEWER.value == "viewer"

    def test_org_role_hierarchy_order(self):
        assert ORG_ROLE_HIERARCHY[OrganizationRole.OWNER] > ORG_ROLE_HIERARCHY[OrganizationRole.ADMIN]
        assert ORG_ROLE_HIERARCHY[OrganizationRole.ADMIN] > ORG_ROLE_HIERARCHY[OrganizationRole.MEMBER]
        assert ORG_ROLE_HIERARCHY[OrganizationRole.MEMBER] > ORG_ROLE_HIERARCHY[OrganizationRole.VIEWER]

    def test_project_role_hierarchy_order(self):
        assert PROJECT_ROLE_HIERARCHY[ProjectRole.ADMIN] > PROJECT_ROLE_HIERARCHY[ProjectRole.CONTRIBUTOR]
        assert PROJECT_ROLE_HIERARCHY[ProjectRole.CONTRIBUTOR] > PROJECT_ROLE_HIERARCHY[ProjectRole.VIEWER]

    def test_org_roles_are_strings(self):
        for role in OrganizationRole:
            assert isinstance(role.value, str)

    def test_project_roles_are_strings(self):
        for role in ProjectRole:
            assert isinstance(role.value, str)


# ---------------------------------------------------------------------------
# Integration tests: Organization RBAC
# ---------------------------------------------------------------------------

class TestOrganizationRBAC:
    def test_create_org_assigns_owner_role(self, client, setup_db):
        """Creating an org should assign the creator the 'owner' role."""
        _register_user(client)
        token = _login_user(client)

        resp = client.post(
            "/api/organizations",
            json={"name": "Test Org", "slug": "test-org"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        org_id = resp.json()["id"]

        # Verify the role in the DB
        loop = setup_db["loop"]
        factory = setup_db["factory"]

        async def check_role():
            async with factory() as session:
                result = await session.execute(
                    select(user_organization.c.role).where(
                        user_organization.c.organization_id == org_id,
                    )
                )
                return result.scalar_one_or_none()

        role = loop.run_until_complete(check_role())
        assert role == "owner"

    def test_add_member_requires_admin_role(self, client, setup_db):
        """A regular member should not be able to add new members."""
        # Register owner and create org
        _register_user(client, "owner", "owner@example.com")
        owner_token = _login_user(client, "owner")

        resp = client.post(
            "/api/organizations",
            json={"name": "Org1", "slug": "org1"},
            headers=_auth_header(owner_token),
        )
        org_id = resp.json()["id"]

        # Register a second user
        _register_user(client, "member1", "member1@example.com")
        member1_token = _login_user(client, "member1")

        # Get member1's user id
        me_resp = client.get("/api/auth/me", headers=_auth_header(member1_token))
        member1_id = me_resp.json()["id"]

        # Owner adds member1 as a regular member
        resp = client.post(
            f"/api/organizations/{org_id}/members/{member1_id}?role=member",
            headers=_auth_header(owner_token),
        )
        assert resp.status_code == 204

        # Register a third user
        _register_user(client, "member2", "member2@example.com")
        me_resp2 = client.get(
            "/api/auth/me",
            headers=_auth_header(_login_user(client, "member2")),
        )
        member2_id = me_resp2.json()["id"]

        # member1 (regular member) tries to add member2 -> should fail
        resp = client.post(
            f"/api/organizations/{org_id}/members/{member2_id}?role=member",
            headers=_auth_header(member1_token),
        )
        assert resp.status_code == 403

    def test_add_member_with_invalid_role(self, client):
        """Adding a member with an invalid role should return 400."""
        _register_user(client)
        token = _login_user(client)

        resp = client.post(
            "/api/organizations",
            json={"name": "Org2", "slug": "org2"},
            headers=_auth_header(token),
        )
        org_id = resp.json()["id"]

        # Register another user
        _register_user(client, "user2", "user2@example.com")
        me_resp = client.get(
            "/api/auth/me",
            headers=_auth_header(_login_user(client, "user2")),
        )
        user2_id = me_resp.json()["id"]

        # Try adding with invalid role
        resp = client.post(
            f"/api/organizations/{org_id}/members/{user2_id}?role=superadmin",
            headers=_auth_header(token),
        )
        assert resp.status_code == 400
        assert "Invalid role" in resp.json()["detail"]

    def test_update_member_role(self, client):
        """Owner should be able to update a member's role."""
        _register_user(client, "owner", "owner@example.com")
        owner_token = _login_user(client, "owner")

        resp = client.post(
            "/api/organizations",
            json={"name": "Org3", "slug": "org3"},
            headers=_auth_header(owner_token),
        )
        org_id = resp.json()["id"]

        # Add a member
        _register_user(client, "user3", "user3@example.com")
        me_resp = client.get(
            "/api/auth/me",
            headers=_auth_header(_login_user(client, "user3")),
        )
        user3_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{user3_id}?role=member",
            headers=_auth_header(owner_token),
        )

        # Update role to admin
        resp = client.put(
            f"/api/organizations/{org_id}/members/{user3_id}/role",
            json={"role": "admin"},
            headers=_auth_header(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_remove_last_owner_prevented(self, client):
        """Should not be able to remove the last owner of an organization."""
        _register_user(client, "soleowner", "soleowner@example.com")
        owner_token = _login_user(client, "soleowner")

        resp = client.post(
            "/api/organizations",
            json={"name": "Org4", "slug": "org4"},
            headers=_auth_header(owner_token),
        )
        org_id = resp.json()["id"]

        me_resp = client.get("/api/auth/me", headers=_auth_header(owner_token))
        owner_id = me_resp.json()["id"]

        # Try to remove the sole owner
        resp = client.delete(
            f"/api/organizations/{org_id}/members/{owner_id}",
            headers=_auth_header(owner_token),
        )
        assert resp.status_code == 400
        assert "last owner" in resp.json()["detail"].lower()

    def test_viewer_cannot_add_members(self, client, setup_db):
        """A viewer should not be able to add members."""
        _register_user(client, "owner", "owner@example.com")
        owner_token = _login_user(client, "owner")

        resp = client.post(
            "/api/organizations",
            json={"name": "Org5", "slug": "org5"},
            headers=_auth_header(owner_token),
        )
        org_id = resp.json()["id"]

        # Add viewer
        _register_user(client, "viewer1", "viewer1@example.com")
        viewer_token = _login_user(client, "viewer1")
        me_resp = client.get("/api/auth/me", headers=_auth_header(viewer_token))
        viewer_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{viewer_id}?role=viewer",
            headers=_auth_header(owner_token),
        )

        # Viewer tries to add another user
        _register_user(client, "user4", "user4@example.com")
        me_resp2 = client.get(
            "/api/auth/me",
            headers=_auth_header(_login_user(client, "user4")),
        )
        user4_id = me_resp2.json()["id"]

        resp = client.post(
            f"/api/organizations/{org_id}/members/{user4_id}?role=member",
            headers=_auth_header(viewer_token),
        )
        assert resp.status_code == 403

    def test_non_member_cannot_view_org(self, client):
        """A user who is not a member should not be able to view the org."""
        _register_user(client, "owner", "owner@example.com")
        owner_token = _login_user(client, "owner")

        resp = client.post(
            "/api/organizations",
            json={"name": "Org6", "slug": "org6"},
            headers=_auth_header(owner_token),
        )
        org_id = resp.json()["id"]

        # Register non-member
        _register_user(client, "outsider", "outsider@example.com")
        outsider_token = _login_user(client, "outsider")

        resp = client.get(
            f"/api/organizations/{org_id}",
            headers=_auth_header(outsider_token),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Integration tests: Project RBAC
# ---------------------------------------------------------------------------

class TestProjectRBAC:
    def _setup_org(self, client):
        """Helper: register a user, log in, create an org, and return details."""
        _register_user(client, "projowner", "projowner@example.com")
        token = _login_user(client, "projowner")
        resp = client.post(
            "/api/organizations",
            json={"name": "ProjOrg", "slug": "proj-org"},
            headers=_auth_header(token),
        )
        return token, resp.json()["id"]

    def test_org_member_can_create_project(self, client):
        """A member of the org should be able to create a project."""
        owner_token, org_id = self._setup_org(client)

        # Add a member to the org
        _register_user(client, "devuser", "devuser@example.com")
        dev_token = _login_user(client, "devuser")
        me_resp = client.get("/api/auth/me", headers=_auth_header(dev_token))
        dev_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{dev_id}?role=member",
            headers=_auth_header(owner_token),
        )

        # Member creates a project
        resp = client.post(
            "/api/projects",
            json={"name": "Dev Project", "organization_id": org_id},
            headers=_auth_header(dev_token),
        )
        assert resp.status_code == 201

    def test_non_member_cannot_create_project(self, client):
        """A non-member should not be able to create a project in an org."""
        owner_token, org_id = self._setup_org(client)

        # Register a non-member
        _register_user(client, "outsider", "outsider@example.com")
        outsider_token = _login_user(client, "outsider")

        resp = client.post(
            "/api/projects",
            json={"name": "Unauthorized Project", "organization_id": org_id},
            headers=_auth_header(outsider_token),
        )
        assert resp.status_code == 403

    def test_viewer_cannot_create_project(self, client):
        """A viewer should not be able to create projects."""
        owner_token, org_id = self._setup_org(client)

        _register_user(client, "vieweruser", "vieweruser@example.com")
        viewer_token = _login_user(client, "vieweruser")
        me_resp = client.get("/api/auth/me", headers=_auth_header(viewer_token))
        viewer_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{viewer_id}?role=viewer",
            headers=_auth_header(owner_token),
        )

        resp = client.post(
            "/api/projects",
            json={"name": "Viewer Project", "organization_id": org_id},
            headers=_auth_header(viewer_token),
        )
        assert resp.status_code == 403

    def test_member_cannot_delete_project(self, client):
        """A regular member should not be able to delete (archive) a project."""
        owner_token, org_id = self._setup_org(client)

        # Owner creates project
        resp = client.post(
            "/api/projects",
            json={"name": "Test Project", "organization_id": org_id},
            headers=_auth_header(owner_token),
        )
        project_id = resp.json()["id"]

        # Add a member
        _register_user(client, "memberuser", "memberuser@example.com")
        member_token = _login_user(client, "memberuser")
        me_resp = client.get("/api/auth/me", headers=_auth_header(member_token))
        member_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{member_id}?role=member",
            headers=_auth_header(owner_token),
        )

        # Member tries to delete
        resp = client.delete(
            f"/api/projects/{project_id}",
            headers=_auth_header(member_token),
        )
        assert resp.status_code == 403

    def test_admin_can_delete_project(self, client):
        """An admin of the org should be able to delete a project."""
        owner_token, org_id = self._setup_org(client)

        # Owner creates project
        resp = client.post(
            "/api/projects",
            json={"name": "Admin Project", "organization_id": org_id},
            headers=_auth_header(owner_token),
        )
        project_id = resp.json()["id"]

        # Add an admin
        _register_user(client, "adminuser", "adminuser@example.com")
        admin_token = _login_user(client, "adminuser")
        me_resp = client.get("/api/auth/me", headers=_auth_header(admin_token))
        admin_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{admin_id}?role=admin",
            headers=_auth_header(owner_token),
        )

        # Admin deletes project
        resp = client.delete(
            f"/api/projects/{project_id}",
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Integration tests: Task RBAC (via org roles fallback)
# ---------------------------------------------------------------------------

class TestTaskRBAC:
    def _setup_project(self, client):
        """Helper: create user, org, and project."""
        _register_user(client, "taskowner", "taskowner@example.com")
        token = _login_user(client, "taskowner")
        org_resp = client.post(
            "/api/organizations",
            json={"name": "TaskOrg", "slug": "task-org"},
            headers=_auth_header(token),
        )
        org_id = org_resp.json()["id"]
        proj_resp = client.post(
            "/api/projects",
            json={"name": "Task Project", "organization_id": org_id},
            headers=_auth_header(token),
        )
        return token, org_id, proj_resp.json()["id"]

    def test_org_member_can_create_task(self, client):
        """An org member should be able to create tasks (contributor via org fallback)."""
        owner_token, org_id, project_id = self._setup_project(client)

        # Add member to org
        _register_user(client, "taskmember", "taskmember@example.com")
        member_token = _login_user(client, "taskmember")
        me_resp = client.get("/api/auth/me", headers=_auth_header(member_token))
        member_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{member_id}?role=member",
            headers=_auth_header(owner_token),
        )

        # Member creates task
        resp = client.post(
            "/api/tasks",
            json={"title": "New Task", "project_id": project_id},
            headers=_auth_header(member_token),
        )
        assert resp.status_code == 201

    def test_viewer_cannot_create_task(self, client):
        """An org viewer should not be able to create tasks."""
        owner_token, org_id, project_id = self._setup_project(client)

        _register_user(client, "taskviewer", "taskviewer@example.com")
        viewer_token = _login_user(client, "taskviewer")
        me_resp = client.get("/api/auth/me", headers=_auth_header(viewer_token))
        viewer_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{viewer_id}?role=viewer",
            headers=_auth_header(owner_token),
        )

        resp = client.post(
            "/api/tasks",
            json={"title": "Viewer Task", "project_id": project_id},
            headers=_auth_header(viewer_token),
        )
        assert resp.status_code == 403

    def test_non_member_cannot_create_task(self, client):
        """A non-member should not be able to create tasks."""
        _, _, project_id = self._setup_project(client)

        _register_user(client, "outsider", "outsider@example.com")
        outsider_token = _login_user(client, "outsider")

        resp = client.post(
            "/api/tasks",
            json={"title": "Outsider Task", "project_id": project_id},
            headers=_auth_header(outsider_token),
        )
        assert resp.status_code == 403

    def test_member_cannot_delete_task(self, client):
        """A regular org member should not be able to delete tasks (requires admin)."""
        owner_token, org_id, project_id = self._setup_project(client)

        # Owner creates a task
        resp = client.post(
            "/api/tasks",
            json={"title": "Delete Me", "project_id": project_id},
            headers=_auth_header(owner_token),
        )
        task_id = resp.json()["id"]

        # Add member
        _register_user(client, "delmember", "delmember@example.com")
        member_token = _login_user(client, "delmember")
        me_resp = client.get("/api/auth/me", headers=_auth_header(member_token))
        member_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{member_id}?role=member",
            headers=_auth_header(owner_token),
        )

        # Member tries to delete -> should fail (requires admin)
        resp = client.delete(
            f"/api/tasks/{task_id}",
            headers=_auth_header(member_token),
        )
        assert resp.status_code == 403

    def test_admin_can_delete_task(self, client):
        """An org admin should be able to delete tasks."""
        owner_token, org_id, project_id = self._setup_project(client)

        resp = client.post(
            "/api/tasks",
            json={"title": "Admin Delete", "project_id": project_id},
            headers=_auth_header(owner_token),
        )
        task_id = resp.json()["id"]

        # Add admin
        _register_user(client, "deladmin", "deladmin@example.com")
        admin_token = _login_user(client, "deladmin")
        me_resp = client.get("/api/auth/me", headers=_auth_header(admin_token))
        admin_id = me_resp.json()["id"]

        client.post(
            f"/api/organizations/{org_id}/members/{admin_id}?role=admin",
            headers=_auth_header(owner_token),
        )

        resp = client.delete(
            f"/api/tasks/{task_id}",
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 204
