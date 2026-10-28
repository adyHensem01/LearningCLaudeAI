from fastapi import APIRouter

from app.database import get_database
from app.repositories.faq_repository import FAQRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.ticket_repository import TicketRepository
from app.schemas.workflow import ProcessTicketRequest, ProcessTicketResponse
from app.services.analysis_service import AnalysisService
from app.services.claude_service import ClaudeService
from app.services.response_service import ResponseService
from app.services.ticket_service import TicketService
from app.services.workflow_service import WorkflowService

# The route builds dependencies and returns the result; WorkflowService
# owns the sequence of steps.
router = APIRouter(prefix="/workflows", tags=["workflows"])


# POST /workflows/process-ticket: run the full deterministic ticket workflow.
@router.post(
    "/process-ticket",
    response_model=ProcessTicketResponse,
)
async def process_ticket(
    request: ProcessTicketRequest,
) -> ProcessTicketResponse:
    database = get_database()
    claude_service = ClaudeService()

    service = WorkflowService(
        analysis_service=AnalysisService(claude_service),
        response_service=ResponseService(claude_service),
        ticket_service=TicketService(TicketRepository(database)),
        order_repository=OrderRepository(database),
        faq_repository=FAQRepository(database),
    )

    try:
        return await service.process(request)
    finally:
        # Close the per-request Claude client even if the workflow fails.
        await claude_service.close()
