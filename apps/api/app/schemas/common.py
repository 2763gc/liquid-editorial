from typing import Generic, TypeVar, List, Any
from pydantic import BaseModel, Field

T = TypeVar("T")

class PaginationResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

class ErrorResponse(BaseModel):
    error: ErrorDetail
