from datetime import datetime, timezone

from app.repositories.faq_repository import FAQRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.common import TicketStatus
from app.schemas.faq import FAQSource
from app.schemas.order import OrderContext
from app.schemas.ticket import TicketCreateRequest
from app.schemas.usage import AIUsage
from app.schemas.workflow import (
    ProcessTicketRequest,
    ProcessTicketResponse,
    WorkflowStep,
)
from app.services.analysis_service import AnalysisService
from app.services.claude_service import ClaudeErrorResponse
from app.services.response_service import ResponseService
from app.services.ticket_service import TicketService


class WorkflowService:
    def __init__(
        self,
        *,
        analysis_service: AnalysisService,
        response_service: ResponseService,
        ticket_service: TicketService,
        order_repository: OrderRepository,
        faq_repository: FAQRepository,
    ) -> None:
        # Inject existing capabilities; the workflow coordinates them.
        self.analysis_service = analysis_service
        self.response_service = response_service
        self.ticket_service = ticket_service
        self.order_repository = order_repository
        self.faq_repository = faq_repository

    async def process(
        self,
        request: ProcessTicketRequest,
    ) -> ProcessTicketResponse:
        # Python code fixes the order of steps; Claude only fills in data.
        executed_steps: list[WorkflowStep] = []

        # 1. Analysis (Claude). Nothing else can be decided before this.
        analysis_result = await self.analysis_service.analyse(request.message)
        analysis = analysis_result.data
        executed_steps.append(WorkflowStep.ANALYSIS)

        missing_context: list[str] = []

        # 2. Order lookup, only when the analysis says it is required.
        order_context: OrderContext | None = None
        if analysis.needs_order_lookup:
            if request.order_id:
                order_context = await self.order_repository.get_order_for_customer(
                    request.customer_id,
                    request.order_id,
                )
                executed_steps.append(WorkflowStep.ORDER_LOOKUP)

            # No order ID, or no order for this customer: never invent one.
            if order_context is None:
                missing_context.append("order")

        # 3. FAQ lookup, only when the analysis says it is required.
        faq_context: list[FAQSource] = []
        if analysis.needs_faq_lookup:
            faq_context = await self.faq_repository.search(analysis.faq_query)
            executed_steps.append(WorkflowStep.FAQ_LOOKUP)

            # No approved FAQ found: Claude must not make up a policy.
            if not faq_context:
                missing_context.append("faq")

        # 4. Persist the ticket so every request leaves a record.
        ticket = await self.ticket_service.create(
            TicketCreateRequest(
                customer_id=request.customer_id,
                order_id=request.order_id,
                message=request.message,
            ),
            analysis,
        )
        executed_steps.append(WorkflowStep.DATABASE_INSERT)

        # 5. Response generation (Claude), only with complete trusted context.
        draft_response: str | None = None
        response_usage: AIUsage | None = None
        processing_error: str | None = None

        if not missing_context:
            try:
                draft_result = await self.response_service.generate_draft(
                    request.message,
                    order_context=order_context,
                    faq_context=faq_context,
                )
                draft_response = draft_result.text
                response_usage = AIUsage(
                    model=draft_result.model,
                    input_tokens=draft_result.input_tokens,
                    output_tokens=draft_result.output_tokens,
                )
                executed_steps.append(WorkflowStep.RESPONSE_GENERATION)
            except ClaudeErrorResponse as exc:
                # The ticket already exists, so record the failure on it.
                processing_error = str(exc)

        # 6. The application decides the final status, then saves the ticket.
        status = self.ticket_service.determine_final_status(
            analysis,
            missing_context=missing_context,
            response_generated=draft_response is not None,
        )

        escalation_reason: str | None = None
        if missing_context:
            escalation_reason = (
                "Missing required trusted context: "
                + ", ".join(missing_context)
            )
        elif analysis.needs_human_review:
            escalation_reason = analysis.human_review_reason
        elif status == TicketStatus.NEEDS_HUMAN_REVIEW:
            escalation_reason = "Urgent priority"

        ticket = await self.ticket_service.save(
            ticket.model_copy(
                update={
                    "order_context": order_context,
                    "faq_context": faq_context,
                    "draft_response": draft_response,
                    "status": status,
                    "escalation_reason": escalation_reason,
                    "processing_error": processing_error,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        )
        executed_steps.append(WorkflowStep.DATABASE_UPDATE)

        return ProcessTicketResponse(
            ticket=ticket,
            executed_steps=executed_steps,
            analysis_usage=AIUsage(
                model=analysis_result.model,
                input_tokens=analysis_result.input_tokens,
                output_tokens=analysis_result.output_tokens,
            ),
            response_usage=response_usage,
        )
