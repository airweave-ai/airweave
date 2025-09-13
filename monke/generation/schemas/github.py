"""Pydantic schemas for GitHub artifact generation (shared envelope)."""

from typing import List, Literal, Union
from pydantic import BaseModel


class GitHubCommonSpec(BaseModel):
    title: str
    summary: str
    tags: List[str]
    token: str  # short unique token; used in filename and embedded in body
    created_at: str


class Section(BaseModel):
    heading: str
    body: str


class MarkdownContent(BaseModel):
    sections: List[Section]


class CodeSnippet(BaseModel):
    body: str


class PythonContent(BaseModel):
    functions: List[CodeSnippet]
    classes: List[CodeSnippet]
    example: str


class KVPair(BaseModel):
    key: str
    value: str


class JSONContent(BaseModel):
    attributes: List[KVPair]
    metadata: List[KVPair]


class GitHubArtifact(BaseModel):
    type: Literal["markdown", "python", "json"]
    common: GitHubCommonSpec
    content: Union[MarkdownContent, PythonContent, JSONContent]
