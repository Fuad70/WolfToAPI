from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"
    image_model: str | None = None


class EditRequest(BaseModel):
    image_url: str
    prompt: str
    aspect_ratio: str = "16:9"
    image_model: str | None = None


class OpenAIImageRequest(BaseModel):
    prompt: str
    model: str = Field(default="flow-nano-banana-pro")
    size: str = Field(default="1536x1024")
    n: int = Field(default=1, ge=1, le=1)
    response_format: str = Field(default="url")
