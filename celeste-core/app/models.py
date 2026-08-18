from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


NoteType = Literal["note", "task", "memory", "project"]


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)
    type: NoteType = "note"
    tags: list[str] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=200_000)
    type: NoteType | None = None
    tags: list[str] | None = None


class Note(BaseModel):
    id: str
    title: str
    content: str
    type: NoteType
    tags: list[str]
    created_at: str
    updated_at: str
    version: int
    deleted: bool = False
