from typing import List
from pydantic import BaseModel, Field
from typing_extensions import Literal


class LinearIssueSpec(BaseModel):
    title: str = Field(description="Issue title. MUST start with the token.")
    token: str
    priority: Literal["none", "low", "medium", "high", "urgent"] = "none"
    labels: List[str] = []


class LinearIssueContent(BaseModel):
    description: str = Field(description="Markdown description; include context and steps.")
    comments: List[str] = Field(default_factory=list, description="Seed comments")


class LinearIssue(BaseModel):
    spec: LinearIssueSpec
    content: LinearIssueContent
