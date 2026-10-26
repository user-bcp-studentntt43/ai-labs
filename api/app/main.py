from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .repository import TaskRepository
from .routes import register_routes
from .services import (
    BackendHealthService,
    RequirementUploadService,
    TaskService,
)


def create_app(db_path: str | None = None, upload_dir: str | None = None) -> FastAPI:
    selected_db = db_path or os.getenv("WORKSHOP_DB_PATH", "./data/workshop.db")
    selected_uploads = upload_dir or os.getenv("WORKSHOP_UPLOAD_DIR", "./uploads")

    repository = TaskRepository(selected_db)
    task_service = TaskService(repository)
    upload_service = RequirementUploadService(selected_uploads)
    backend_health_service = BackendHealthService()

    app = FastAPI(title="Workshop Requirements API", version="0.1.0")
    app.state.connection = repository.connection
    app.state.upload_dir = selected_uploads
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_routes(app, task_service, upload_service, backend_health_service)

    @app.on_event("shutdown")
    def close_connection() -> None:
        repository.close()

    return app


app = create_app()
