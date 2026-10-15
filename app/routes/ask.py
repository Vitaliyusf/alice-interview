from fastapi import APIRouter

from app import agent
from app.deps import ClientDep, SettingsDep
from app.schemas import AskRequest, AskResponse

router = APIRouter(tags=["agent"])


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, client: ClientDep, settings: SettingsDep) -> AskResponse:
    """The route validates, delegates and shapes the reply. No model logic here."""
    text = await agent.answer(client, settings.openai_model, body.question)
    return AskResponse(answer=text, model=settings.openai_model)
