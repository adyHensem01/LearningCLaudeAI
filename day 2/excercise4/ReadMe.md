Pseudocode


process(request):
    steps = []

    # 1. ANALYSIS (Claude call #1)
    analysis = analysis_service.analyse(request.message)        -> steps += analysis
    # If this fails, stop. There's no ticket yet because TicketResponse needs an analysis.

    # 2. ORDER_LOOKUP, only if analysis.needs_order_lookup
    missing = []
    if analysis.needs_order_lookup:
        if request.order_id:
            order_context = order_repository.get_order_for_customer(customer_id, order_id)
                                                                -> steps += order_lookup
        if order_context is None: missing += "order"           # no ID, or not this customer's order

    # 3. FAQ_LOOKUP, only if analysis.needs_faq_lookup
    if analysis.needs_faq_lookup:
        faq_context = faq_repository.search(analysis.faq_query) -> steps += faq_lookup
        if faq_context == []: missing += "faq"

    # 4. DATABASE_INSERT: always runs, so every request leaves a record
    ticket = ticket_service.create(...)   # status comes from determine_status(analysis)
                                                                -> steps += database_insert

    # 5. RESPONSE_GENERATION (Claude call #2), only if nothing required is missing
    if not missing:
        draft = response_service.generate_draft(message, order_context, faq_context)
                                                                -> steps += response_generation
        # If this fails, set PROCESSING_FAILED and processing_error. The ticket already exists.

    # 6. DATABASE_UPDATE: always runs
    final status = decided by TicketService (Python), never by Claude:
        missing context              -> NEEDS_HUMAN_REVIEW + escalation_reason
        urgent / needs_human_review  -> NEEDS_HUMAN_REVIEW (the draft is kept for the reviewer)
        otherwise                    -> PROCESSED
    ticket_service.save(ticket + contexts + draft + status)     -> steps += database_update

    return ProcessTicketResponse(ticket, steps, usages)
