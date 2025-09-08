"""Pydantic schemas for GitHub artifact generation (shared envelope)."""

from typing import Dict, List, Literal, Union
from pydantic import BaseModel, Field


class GitHubCommonSpec(BaseModel):
    title: str
    summary: str
    tags: List[str] = Field(default_factory=list)
    token: str  # short unique token; used in filename and embedded in body
    created_at: str


class MarkdownContent(BaseModel):
    sections: List[Dict[str, str]] = Field(default_factory=list)


class PythonContent(BaseModel):
    functions: List[Dict[str, str]] = Field(default_factory=list)
    classes: List[Dict[str, str]] = Field(default_factory=list)
    example: str = ""


class JSONContent(BaseModel):
    attributes: Dict[str, str] = Field(default_factory=dict)
    metadata: Dict[str, str] = Field(default_factory=dict)


class GitHubArtifact(BaseModel):
    type: Literal["markdown", "python", "json"]
    common: GitHubCommonSpec
    content: Union[MarkdownContent, PythonContent, JSONContent]
