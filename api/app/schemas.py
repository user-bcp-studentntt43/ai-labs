from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, JsonValue

DEFAULT_TASK_STATUS = "TODO"
DEFAULT_TASK_PRIORITY = "MEDIUM"


class TaskCreateRequest(BaseModel):
    title: JsonValue = ""
    description: JsonValue = ""
    status: JsonValue = DEFAULT_TASK_STATUS
    priority: JsonValue = DEFAULT_TASK_PRIORITY
    owner: JsonValue = None


class ApiResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class TaskResponse(ApiResponse):
    id: int
    title: str
    description: str
    status: str
    owner: str
    priority: str
    created_at: str = Field(alias="createdAt")


class TaskSummaryResponse(ApiResponse):
    owner: str
    total: int
    by_status: dict[str, int] = Field(alias="byStatus")
    high_priority_open: int = Field(alias="highPriorityOpen")


class RequirementUploadResponse(ApiResponse):
    owner: str
    file_name: str = Field(alias="fileName")
    stored_at: str = Field(alias="storedAt")
    size: int


class BackendHealthResponse(ApiResponse):
    requested_by: str = Field(alias="requestedBy")
    status: int
    body: str
