"""Request and response models: the API contract, and the validation of everything that comes in."""

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=4000, description="What to ask the assistant")


class AskResponse(BaseModel):
    answer: str
    model: str
