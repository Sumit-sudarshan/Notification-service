from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    limit: int
    offset: int

class Envelope(BaseModel, Generic[T]):
    data: T
