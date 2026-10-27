import base64
import sqlite3
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import repository as api_repository
from app import services as api_services
from app.main import create_app
from app.services import MAX_REQUIREMENT_FILE_SIZE_BYTES, safe_requirement_filename

JWT_ALGORITHM = "RS256"
JWT_ISSUER = "BCP"
JWT_AUDIENCE = "dev"
JWT_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
MAX_UPLOAD_SIZE_BYTES = 1_048_576
JWT_PUBLIC_KEY = JWT_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")


@pytest.fixture(autouse=True)
def configure_jwt_public_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("devpub", JWT_PUBLIC_KEY)


def token(
    username: str | int = "student",
    role: str | int = "STUDENT",
    *,
    expires_at: int | None = None,
    issuer: str = JWT_ISSUER,
    audience: str = JWT_AUDIENCE,
    signing_key: rsa.RSAPrivateKey = JWT_PRIVATE_KEY,
    omitted_claims: tuple[str, ...] = (),
) -> str:
    claims = {
        "username": username,
        "role": role,
        "exp": expires_at or int(time.time()) + 3600,
        "iss": issuer,
        "aud": audience,
    }
    for claim in omitted_claims:
        claims.pop(claim)
    return jwt.encode(claims, signing_key, algorithm=JWT_ALGORITHM)


def legacy_token(username: str = "student", role: str = "STUDENT") -> str:
    raw = f"{username}|{role}|{int(time.time()) + 3600}|WORKSHOP_SECRET_2026"
    return base64.b64encode(raw.encode()).decode()


def headers(username: str = "student", role: str = "STUDENT") -> dict[str, str]:
    return {"Authorization": f"Bearer {token(username, role)}"}


def test_lists_seeded_tasks(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks", headers=headers())
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_lists_tasks_when_owner_query_is_empty(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks?owner=", headers=headers())

    assert response.status_code == 200
    assert {task["owner"] for task in response.json()} == {"student"}


def test_creates_task_and_summary(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        created = client.post(
            "/api/tasks",
            headers=headers(),
            json={"title": "Add tests", "description": "Improve coverage", "status": "TODO", "priority": "HIGH"},
        )
        summary = client.get("/api/summary", headers=headers())
    assert created.status_code == 201
    assert created.json()["owner"] == "student"
    assert summary.json()["total"] == 3


def test_creates_task_from_empty_object_with_documented_defaults(
    tmp_path: Path,
) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.post("/api/tasks", headers=headers(), json={})

    assert response.status_code == 201
    assert {
        key: response.json()[key]
        for key in ("title", "description", "status", "owner", "priority")
    } == {
        "title": "",
        "description": "",
        "status": "TODO",
        "owner": "student",
        "priority": "MEDIUM",
    }


def test_create_task_preserves_defaults_and_string_coercion(
    tmp_path: Path,
) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks",
            headers=headers(),
            json={"title": 42, "unexpected": "ignored"},
        )

    assert response.status_code == 201
    task = response.json()
    assert task.keys() == {
        "id",
        "title",
        "description",
        "status",
        "owner",
        "priority",
        "createdAt",
    }
    assert {
        key: task[key]
        for key in ("title", "description", "status", "owner", "priority")
    } == {
        "title": "42",
        "description": "",
        "status": "TODO",
        "owner": "student",
        "priority": "MEDIUM",
    }
    assert isinstance(task["id"], int)
    assert isinstance(task["createdAt"], str) and task["createdAt"]


def test_summary_preserves_status_counts_and_high_priority_rules(
    tmp_path: Path,
) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        for status_value in ("TODO", "DONE", "ARCHIVED"):
            response = client.post(
                "/api/tasks",
                headers=headers(),
                json={"title": status_value, "status": status_value, "priority": "HIGH"},
            )
            assert response.status_code == 201

        summary = client.get("/api/summary", headers=headers())

    assert summary.status_code == 200
    assert summary.json() == {
        "owner": "student",
        "total": 5,
        "byStatus": {
            "TODO": 2,
            "IN_PROGRESS": 1,
            "DONE": 1,
            "ARCHIVED": 1,
        },
        "highPriorityOpen": 2,
    }


def test_summarizes_empty_result_when_owner_query_is_empty(
    tmp_path: Path,
) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/summary?owner=", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "owner": "student",
        "total": 2,
        "byStatus": {"TODO": 1, "IN_PROGRESS": 1},
        "highPriorityOpen": 1,
    }


def test_uploads_requirement(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    content = b"Login must be accessible"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("requirements.txt", content, "text/plain")},
        )
    assert response.status_code == 201
    assert response.json() == {
        "owner": "student",
        "fileName": "requirements.txt",
        "storedAt": str(upload_dir / "requirements.txt"),
        "size": len(content),
    }
    assert (upload_dir / "requirements.txt").read_bytes() == content


def test_accepts_requirement_with_empty_content(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("empty.txt", b"", "text/plain")},
        )

    assert response.status_code == 201
    assert response.json()["size"] == 0
    assert (upload_dir / "empty.txt").read_bytes() == b""


def test_rejects_requirement_without_extension(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("README", b"text", "text/plain")},
        )

    assert response.status_code == 415
    assert response.json() == {"detail": "Unsupported file extension"}
    assert list(upload_dir.iterdir()) == []


def test_sanitizes_requirement_filename(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("..\\outside.txt", b"safe", "text/plain")},
        )
    assert response.status_code == 201
    assert response.json()["fileName"] == "outside.txt"
    assert response.json()["storedAt"] == str(upload_dir / "outside.txt")
    assert (upload_dir / "outside.txt").read_bytes() == b"safe"
    assert not (tmp_path / "outside.txt").exists()


def test_rejects_requirement_with_unsupported_extension(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("requirements.pdf", b"not allowed", "application/pdf")},
        )
    assert response.status_code == 415
    assert response.json() == {"detail": "Unsupported file extension"}
    assert list(upload_dir.iterdir()) == []


def test_rejects_requirement_over_size_limit(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    content = b"x" * (MAX_UPLOAD_SIZE_BYTES + 1)
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("large.txt", content, "text/plain")},
        )
    assert response.status_code == 413
    assert response.json() == {"detail": "File exceeds maximum size"}
    assert list(upload_dir.iterdir()) == []


def test_accepts_requirement_at_size_limit(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    assert MAX_REQUIREMENT_FILE_SIZE_BYTES == MAX_UPLOAD_SIZE_BYTES
    content = b"x" * MAX_UPLOAD_SIZE_BYTES
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("limit.txt", content, "text/plain")},
        )
    assert response.status_code == 201
    assert response.json()["size"] == MAX_UPLOAD_SIZE_BYTES
    assert (upload_dir / "limit.txt").read_bytes() == content


def test_rejects_requirement_filename_without_basename(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("..\\", b"invalid name", "text/plain")},
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid filename"}


def test_preserves_missing_filename_validation(tmp_path: Path) -> None:
    upload_dir = tmp_path / "uploads"
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("", b"empty name", "text/plain")},
        )
    assert response.status_code == 422


def test_rejects_malformed_multipart_body(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    request_headers = {
        **headers(),
        "Content-Type": "multipart/form-data; boundary=expected-boundary",
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/requirements",
            headers=request_headers,
            content=b"not a multipart body",
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid multipart data."}


def test_returns_422_when_task_body_is_missing(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.post("/api/tasks", headers=headers())

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body"]
    assert response.json()["detail"][0]["type"] == "missing"


@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        ("GET", "/api/tasks", {}),
        ("POST", "/api/tasks", {"json": {}}),
        ("GET", "/api/summary", {}),
        (
            "POST",
            "/api/requirements",
            {"files": {"file": ("valid.txt", b"text", "text/plain")}},
        ),
        ("GET", "/api/backend-health", {}),
    ],
)
@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer malformed-token"],
    ids=["missing-token", "invalid-token"],
)
def test_all_documented_endpoints_require_authentication(
    method: str,
    path: str,
    request_kwargs: dict[str, object],
    authorization: str | None,
    tmp_path: Path,
) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    request_headers = (
        {} if authorization is None else {"Authorization": authorization}
    )
    with TestClient(app) as client:
        response = client.request(
            method,
            path,
            headers=request_headers,
            **request_kwargs,
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        ("GET", "/api/tasks", {}),
        ("POST", "/api/tasks", {"json": {}}),
        ("GET", "/api/summary", {}),
        (
            "POST",
            "/api/requirements",
            {"files": {"file": ("valid.txt", b"text", "text/plain")}},
        ),
        ("GET", "/api/backend-health", {}),
    ],
)
def test_all_documented_endpoints_fail_generically_when_jwt_key_is_missing(
    method: str,
    path: str,
    request_kwargs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("devpub")
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.request(
            method,
            path,
            headers=headers(),
            **request_kwargs,
        )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "JWT public key" not in response.text


def test_returns_500_without_exposing_upload_write_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_write(self: Path, data: bytes) -> int:
        raise OSError("private filesystem detail")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("valid.txt", b"text", "text/plain")},
        )

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "private filesystem detail" not in response.text


@pytest.mark.parametrize("filename", [None, "", "invalid\x00name.txt", "folder/"])
def test_rejects_invalid_requirement_filename_values(
    filename: str | None,
) -> None:
    with pytest.raises(HTTPException) as error:
        safe_requirement_filename(filename)
    assert error.value.status_code == 400
    assert error.value.detail == "Invalid filename"


def test_rejects_requirement_target_resolving_outside_upload_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    upload_dir = tmp_path / "uploads"
    outside_path = tmp_path / "outside.txt"
    original_resolve = Path.resolve

    def resolve_path(path: Path, *args: object, **kwargs: object) -> Path:
        if path == upload_dir / "safe.txt":
            return outside_path
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_path)
    app = create_app(str(tmp_path / "workshop.db"), str(upload_dir))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/requirements",
            headers=headers(),
            files={"file": ("safe.txt", b"safe", "text/plain")},
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid filename"}
    assert not outside_path.exists()


def test_rejects_invalid_token(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_rejects_legacy_token(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {legacy_token()}"},
        )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


@pytest.mark.parametrize(
    "token_value",
    [
        token(expires_at=int(time.time()) - 1),
        token(issuer="unexpected-issuer"),
        token(audience="unexpected-audience"),
        token(omitted_claims=("username",)),
        token(omitted_claims=("role",)),
        token(omitted_claims=("exp",)),
    ],
)
def test_rejects_jwt_with_invalid_claims(tmp_path: Path, token_value: str) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token_value}"},
        )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_rejects_jwt_with_invalid_signature(tmp_path: Path) -> None:
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    invalid_signature_token = token(signing_key=other_private_key)
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {invalid_signature_token}"},
        )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_missing_public_key_configuration_returns_server_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("devpub")
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/tasks", headers=headers())
    assert response.status_code == 500


def test_rejects_missing_bearer_header(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_invalid_public_key_configuration_returns_server_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("devpub", "not a PEM key")
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/tasks", headers=headers())
    assert response.status_code == 500


def test_non_rsa_public_key_configuration_returns_server_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ec_private_key = ec.generate_private_key(ec.SECP256R1())
    ec_public_key = ec_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    monkeypatch.setenv("devpub", ec_public_key)
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/tasks", headers=headers())
    assert response.status_code == 500


@pytest.mark.parametrize(
    "username,role",
    [
        (123, "STUDENT"),
        ("student", 7),
    ],
)
def test_rejects_non_string_identity_claims(
    tmp_path: Path,
    username: str | int,
    role: str | int,
) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get(
            "/api/tasks",
            headers={"Authorization": f"Bearer {token(username=username, role=role)}"},
        )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid token"}


def test_rejects_listing_tasks_for_different_owner(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks?owner=trainer", headers=headers("student"))
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_rejects_summary_for_different_owner(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/summary?owner=trainer", headers=headers("student"))
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_rejects_creating_task_for_different_owner(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks",
            headers=headers("student"),
            json={"title": "Test ownership", "description": "Characterization", "owner": "trainer"},
        )
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def test_allows_listing_tasks_for_authenticated_owner(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/tasks?owner=student", headers=headers("student"))
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {task["owner"] for task in response.json()} == {"student"}


def test_allows_summary_for_authenticated_owner(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/summary?owner=student", headers=headers("student"))
    assert response.status_code == 200
    assert response.json()["owner"] == "student"
    assert response.json()["total"] == 2


def test_allows_creating_task_for_authenticated_owner(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.post(
            "/api/tasks",
            headers=headers("student"),
            json={"title": "Test ownership", "description": "Authenticated owner", "owner": "student"},
        )
    assert response.status_code == 201
    assert response.json()["owner"] == "student"


def test_lists_tasks_for_username_containing_apostrophe(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/tasks", headers=headers("student'"))
    assert response.status_code == 200
    assert response.json() == []


def test_summarizes_tasks_for_username_containing_apostrophe(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/summary", headers=headers("student'"))
    assert response.status_code == 200
    assert response.json()["owner"] == "student'"
    assert response.json()["total"] == 0


def test_creates_task_with_apostrophes_in_text(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/tasks",
            headers=headers(),
            json={
                "title": "Teacher's notes",
                "description": "Student's task",
                "status": "TODO",
                "priority": "MEDIUM",
            },
        )
    assert response.status_code == 201
    assert response.json()["title"] == "Teacher's notes"
    assert response.json()["description"] == "Student's task"


def test_binds_values_in_task_queries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded_calls: list[tuple[str, tuple[object, ...]]] = []
    original_connect = sqlite3.connect
    record_calls = False

    class RecordingConnection:
        def __init__(self, connection: sqlite3.Connection) -> None:
            object.__setattr__(self, "_connection", connection)

        def __getattr__(self, name: str) -> object:
            return getattr(self._connection, name)

        def __setattr__(self, name: str, value: object) -> None:
            setattr(self._connection, name, value)

        def execute(
            self, sql: str, parameters: tuple[object, ...] = ()
        ) -> sqlite3.Cursor:
            if record_calls:
                recorded_calls.append((sql, parameters))
            return self._connection.execute(sql, parameters)

    def recording_connect(
        *args: object, **kwargs: object
    ) -> RecordingConnection:
        return RecordingConnection(original_connect(*args, **kwargs))

    monkeypatch.setattr(api_repository.sqlite3, "connect", recording_connect)
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    record_calls = True
    with TestClient(app) as client:
        client.get("/api/tasks", headers=headers())
        client.post(
            "/api/tasks",
            headers=headers(),
            json={"title": "Bound title", "description": "Bound description"},
        )
        client.get("/api/summary", headers=headers())

    assert recorded_calls == [
        (
            "SELECT id,title,description,status,owner,priority,created_at FROM tasks WHERE owner=? ORDER BY id",
            ("student",),
        ),
        (
            "INSERT INTO tasks(title,description,status,owner,priority,created_at) VALUES (?,?,?,?,?,datetime('now'))",
            ("Bound title", "Bound description", "TODO", "student", "MEDIUM"),
        ),
        (
            "SELECT id,title,description,status,owner,priority,created_at FROM tasks WHERE id=?",
            (4,),
        ),
        (
            "SELECT status,priority FROM tasks WHERE owner=?",
            ("student",),
        ),
    ]


def test_backend_health_returns_mocked_backend_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    backend_url = "http://backend.test/health"
    request_calls: list[tuple[str, str, float]] = []

    class StubResponse:
        status = 202
        data = b"backend ready"

    class StubPoolManager:
        def request(self, method: str, url: str, timeout: float) -> StubResponse:
            request_calls.append((method, url, timeout))
            return StubResponse()

    monkeypatch.setenv("AUTH_HEALTH_URL", backend_url)
    monkeypatch.setattr(api_services.urllib3, "PoolManager", StubPoolManager)
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/backend-health", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "requestedBy": "student",
        "status": 202,
        "body": "backend ready",
    }
    assert request_calls == [("GET", backend_url, 3.0)]


def test_backend_health_returns_observed_failure_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FailingPoolManager:
        def request(self, method: str, url: str, timeout: float) -> None:
            raise api_services.urllib3.exceptions.HTTPError(
                "simulated backend failure"
            )

    monkeypatch.setattr(api_services.urllib3, "PoolManager", FailingPoolManager)
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.get("/api/backend-health", headers=headers())

    assert response.status_code == 200
    assert response.json() == {
        "requestedBy": "student",
        "status": 0,
        "body": "Backend health check failed",
    }


def test_backend_health_does_not_return_unexpected_exception_details(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class FailingPoolManager:
        def request(self, method: str, url: str, timeout: float) -> None:
            raise RuntimeError("internal secret detail")

    monkeypatch.setattr(api_services.urllib3, "PoolManager", FailingPoolManager)
    app = create_app(str(tmp_path / "workshop.db"), str(tmp_path / "uploads"))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/backend-health", headers=headers())

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "internal secret detail" not in response.text
