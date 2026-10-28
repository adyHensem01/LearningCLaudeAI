from dataclasses import dataclass

from app.prompts.response_generation import (
    RESPONSE_GENERATION_SYSTEM_PROMPT,
)
from app.repositories.order_repository import OrderRepository
from app.schemas.order import OrderContext
from app.services.claude_service import (
    ClaudeService,
    ClaudeTextResult,
)


# route -> ResponseService -> OrderRepository -> MongoDB
#                          -> ClaudeService   -> Anthropic SDK
# This service holds the "draft a customer reply" use case: it decides
# whether to look up an order, builds the trusted context, chooses the
# instructions and limits, and delegates the API call to ClaudeService.
# ClaudeService never sees the database; it only receives text.


@dataclass(frozen=True)
class GeneratedResponse:
    # The Claude result plus the trusted order the app actually supplied
    # (None when no authorized order was used).
    result: ClaudeTextResult
    order_context: OrderContext | None


class ResponseService:
    def __init__(
        self,
        claude_service: ClaudeService,
        order_repository: OrderRepository,
    ) -> None:
        # Dependencies are passed in so the route controls their lifecycle
        # (including close()) and tests can swap in fakes.
        self.claude_service = claude_service
        self.order_repository = order_repository

    async def generate(
        self,
        customer_message: str,
        customer_id: str | None = None,
        order_id: str | None = None,
    ) -> GeneratedResponse:
        order_context: OrderContext | None = None

        # Application code, not Claude, decides whether to look up an order,
        # and the lookup is always scoped to the customer.
        if customer_id and order_id:
            order_context = await self.order_repository.get_order_for_customer(
                customer_id,
                order_id,
            )

        # Trusted context goes in the system prompt, separate from the
        # untrusted customer message, so the customer cannot fake it.
        system = RESPONSE_GENERATION_SYSTEM_PROMPT
        if order_context is not None:
            system += (
                "\n\n<trusted_order_context>\n"
                f"{order_context.model_dump_json()}\n"
                "</trusted_order_context>"
            )
        elif order_id:
            # An order was requested but no authorized record matched:
            # say so explicitly rather than letting Claude guess a status.
            system += (
                "\n\n<trusted_order_context>\n"
                "No authorized order record was found for this request. "
                "Do not state any order status or delivery details.\n"
                "</trusted_order_context>"
            )

        # max_tokens caps the draft length (and therefore the cost).
        result = await self.claude_service.generate_text(
            customer_message,
            system=system,
            max_tokens=300,
        )

        return GeneratedResponse(
            result=result,
            order_context=order_context,
        )
