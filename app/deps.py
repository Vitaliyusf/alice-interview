"""Dependencies the routes ask for. Tests replace them with app.dependency_overrides."""

from typing import Annotated

from fastapi import Depends, Request
from openai import AsyncOpenAI

from app.config import Settings


def get_client(request: Request) -> AsyncOpenAI:
    return request.app.state.openai  # one client for the whole app, created in the lifespan


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


ClientDep = Annotated[AsyncOpenAI, Depends(get_client)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
