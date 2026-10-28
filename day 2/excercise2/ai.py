from fastapi import APIRouter
from app.prompts.summarise import (SUMMARISE_SYSTEM_PROMPT,)

from app.services.claude_service import ClaudeService
from app.schemas.ai import (
    AnalyseRequest,
    AnalyseResponse,
    GenerateResponseRequest,
    GenerateResponseResponse,
    ResponseContextUsed,
    SummariseRequest,
    SummariseResponse,
)
from app.database import get_database
from app.repositories.order_repository import OrderRepository
from app.services.response_service import ResponseService
from app.schemas.usage import AIUsage
from app.services.analysis_service import AnalysisService


# Routes only accept the request and shape the response. FastAPI/Pydantic
# validate the incoming body; the Claude work happens in the services.
# tags=["ai"] groups these endpoints together in the /docs page.
router = APIRouter(tags=["ai"])

# POST /summarise: send some text, get a short summary back.
@router.post(
    "/summarise",
    response_model=SummariseResponse
)
async def summarise_text(
    request: SummariseRequest,
) -> SummariseResponse:
    # request is already validated by SummariseRequest at this point.
    claude_service = ClaudeService()

    try:
        # The user's text is the message; the app's own instructions go in
        # the separate system prompt. max_tokens keeps summaries short/cheap.
        result = await claude_service.generate_text(
            request.text,
            system=SUMMARISE_SYSTEM_PROMPT,
            max_tokens=150,
        )
    finally:
        # Always release the HTTP connections, even if the call failed.
        await claude_service.close()

    # Map the service result onto the public response model.
    return SummariseResponse(
        summary=result.text,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

# POST /analyse: send a support message, get a structured TicketAnalysis
# plus token usage back.
@router.post(
    "/analyse",
    response_model=AnalyseResponse,
)
async def analyse_ticket(
    request: AnalyseRequest,
) -> AnalyseResponse:
    # The route builds the services; AnalysisService holds the use-case
    # logic and uses ClaudeService for the API call.
    claude_service = ClaudeService()
    analysis_service = AnalysisService(
        claude_service
    )

    try:
        result = await analysis_service.analyse(
            request.message
        )
    finally:
        # Always release the HTTP connections, even if the call failed.
        await claude_service.close()

    # result.data is the validated TicketAnalysis; usage is grouped in
    # its own AIUsage object so token counts stay separate from the answer.
    return AnalyseResponse(
        analysis=result.data,
        usage=AIUsage(
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        ),
    )


# POST /generate-response: send a customer message, get a draft reply back.
# The draft is plain text for a human to review, not a final answer.
@router.post(
    "/generate-response",
    response_model=GenerateResponseResponse,
)
async def generate_response(
    request: GenerateResponseRequest,
) -> GenerateResponseResponse:
    # Same pattern as /analyse: the route builds the services and
    # ResponseService holds the use-case logic. The repository gets the
    # shared database; ClaudeService never does.
    claude_service = ClaudeService()
    response_service = ResponseService(
        claude_service,
        OrderRepository(get_database()),
    )

    try:
        generated = await response_service.generate(
            request.customer_message,
            customer_id=request.customer_id,
            order_id=request.order_id,
        )
    finally:
        # Always release the HTTP connections, even if the call failed.
        await claude_service.close()

    result = generated.result

    # The draft is plain text (result.text), so there is no schema to
    # unpack here; usage is grouped in AIUsage as in /analyse.
    # context_used.order_id is only set when a customer-scoped order was
    # found and supplied to Claude; null means no trusted order was used.
    return GenerateResponseResponse(
        draft_response=result.text,
        context_used=ResponseContextUsed(
            order_id=(
                generated.order_context.order_id
                if generated.order_context
                else None
            ),
        ),
        usage=AIUsage(
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        ),
    )
