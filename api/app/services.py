from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

import urllib3
from fastapi import HTTPException, UploadFile, status

from .repository import TaskRepository
from .schemas import (
    BackendHealthResponse,
    RequirementUploadResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskSummaryResponse,
)

ALLOWED_REQUIREMENT_EXTENSIONS = frozenset({".txt"})
MAX_REQUIREMENT_FILE_SIZE_BYTES = 1_048_576
REQUIREMENT_UPLOAD_CHUNK_SIZE_BYTES = 64 * 1024
HIGH_TASK_PRIORITY = "HIGH"
CLOSED_TASK_STATUSES = frozenset({"DONE", "ARCHIVED"})
DEFAULT_BACKEND_HEALTH_URL = "http://localhost:8080/q/health"
BACKEND_HEALTH_REQUEST_TIMEOUT_SECONDS = 3.0
BACKEND_HEALTH_FAILURE_MESSAGE = "Backend health check failed"
BACKEND_HEALTH_UNAVAILABLE_STATUS = 0

logger = logging.getLogger(__name__)


def safe_requirement_filename(filename: str | None) -> str:
    if not filename or "\x00" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename"
        )

    safe_filename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    if safe_filename in {"", ".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename"
        )
    if Path(safe_filename).suffix.lower() not in ALLOWED_REQUIREMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file extension",
        )
    return safe_filename


async def read_requirement_content(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while chunk := await file.read(REQUIREMENT_UPLOAD_CHUNK_SIZE_BYTES):
        total_size += len(chunk)
        if total_size > MAX_REQUIREMENT_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds maximum size",
            )
        chunks.append(chunk)

    return b"".join(chunks)


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def list_tasks(self, owner: str) -> list[TaskResponse]:
        return [self._as_task(row) for row in self._repository.list_by_owner(owner)]

    def create_task(
        self, payload: TaskCreateRequest, owner: str
    ) -> TaskResponse:
        title = str(payload.title)
        description = str(payload.description)
        task_status = str(payload.status)
        priority = str(payload.priority)
        row = self._repository.create_task(
            title, description, task_status, owner, priority
        )
        return self._as_task(row)

    def summary(self, owner: str) -> TaskSummaryResponse:
        rows = self._repository.summary_by_owner(owner)
        tasks_by_status: dict[str, int] = {}
        high_priority_open = 0
        for row in rows:
            task_status = row["status"]
            tasks_by_status[task_status] = tasks_by_status.get(task_status, 0) + 1
            if (
                row["priority"] == HIGH_TASK_PRIORITY
                and task_status not in CLOSED_TASK_STATUSES
            ):
                high_priority_open += 1
        return TaskSummaryResponse(
            owner=owner,
            total=len(rows),
            by_status=tasks_by_status,
            high_priority_open=high_priority_open,
        )

    @staticmethod
    def _as_task(row: sqlite3.Row) -> TaskResponse:
        return TaskResponse(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            owner=row["owner"],
            priority=row["priority"],
            created_at=row["created_at"],
        )


class RequirementUploadService:
    def __init__(self, upload_directory: str) -> None:
        self._upload_directory = Path(upload_directory)
        self._upload_directory.mkdir(parents=True, exist_ok=True)

    def _store_with_unique_name(self, filename: str, content: bytes) -> Path:
        original_target = self._upload_directory / filename
        target = original_target
        suffix_number = 1

        while True:
            try:
                destination = target.open("xb")
            except FileExistsError:
                target = original_target.with_name(
                    f"{original_target.stem}-{suffix_number}{original_target.suffix}"
                )
                suffix_number += 1
                continue

            with destination:
                destination.write(content)
            return target

    async def save(
        self, file: UploadFile, owner: str
    ) -> RequirementUploadResponse:
        safe_filename = safe_requirement_filename(file.filename)
        original_target = self._upload_directory / safe_filename
        if original_target.resolve().parent != self._upload_directory.resolve():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename"
            )

        content = await read_requirement_content(file)
        target = self._store_with_unique_name(safe_filename, content)
        return RequirementUploadResponse(
            owner=owner,
            file_name=target.name,
            stored_at=str(target),
            size=len(content),
        )


class BackendHealthService:
    def check(self, username: str) -> BackendHealthResponse:
        url = os.getenv("AUTH_HEALTH_URL", DEFAULT_BACKEND_HEALTH_URL)
        try:
            response = urllib3.PoolManager().request(
                "GET", url, timeout=BACKEND_HEALTH_REQUEST_TIMEOUT_SECONDS
            )
        except urllib3.exceptions.HTTPError:
            logger.warning("Backend health request failed", exc_info=True)
            return BackendHealthResponse(
                requested_by=username,
                status=BACKEND_HEALTH_UNAVAILABLE_STATUS,
                body=BACKEND_HEALTH_FAILURE_MESSAGE,
            )
        return BackendHealthResponse(
            requested_by=username,
            status=response.status,
            body=response.data.decode("utf-8"),
        )
