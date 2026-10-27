from __future__ import annotations

from fastapi import Body, Depends, FastAPI, File, Query, UploadFile

from .schemas import (
    BackendHealthResponse,
    RequirementUploadResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskSummaryResponse,
)
from .security import authenticated_identity, authenticated_owner
from .services import (
    BackendHealthService,
    RequirementUploadService,
    TaskService,
)


def register_routes(
    app: FastAPI,
    task_service: TaskService,
    upload_service: RequirementUploadService,
    backend_health_service: BackendHealthService,
) -> None:
    @app.get("/api/tasks", response_model=list[TaskResponse])
    def list_tasks(
        owner: str | None = Query(default=None),
        identity: dict[str, str] = Depends(authenticated_identity),
    ) -> list[TaskResponse]:
        requested_owner = authenticated_owner(owner or None, identity)
        return task_service.list_tasks(requested_owner)

    @app.post("/api/tasks", status_code=201, response_model=TaskResponse)
    def create_task(
        payload: TaskCreateRequest = Body(...),
        identity: dict[str, str] = Depends(authenticated_identity),
    ) -> TaskResponse:
        requested_owner = (
            str(payload.owner) if "owner" in payload.model_fields_set else None
        )
        owner = authenticated_owner(requested_owner, identity)
        return task_service.create_task(payload, owner)

    @app.get("/api/summary", response_model=TaskSummaryResponse)
    def summary(
        owner: str | None = Query(default=None),
        identity: dict[str, str] = Depends(authenticated_identity),
    ) -> TaskSummaryResponse:
        requested_owner = authenticated_owner(owner or None, identity)
        return task_service.summary(requested_owner)

    @app.post(
        "/api/requirements",
        status_code=201,
        response_model=RequirementUploadResponse,
    )
    async def upload_requirement(
        file: UploadFile = File(...),
        identity: dict[str, str] = Depends(authenticated_identity),
    ) -> RequirementUploadResponse:
        return await upload_service.save(file, identity["username"])

    @app.get("/api/backend-health", response_model=BackendHealthResponse)
    def backend_health(
        identity: dict[str, str] = Depends(authenticated_identity),
    ) -> BackendHealthResponse:
        return backend_health_service.check(identity["username"])
