import time
import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from app.models.qa import QAResponse, EvidenceItem
from app.services.safety import SafetyService
from app.services.query_processor import QueryProcessor
from app.services.qa_retrieval import QARetrievalService
from app.services.grounding import ContextBuilder, HiringFitEngine
from app.services.generation import AnswerGenerator
from app.services.observability import ObservabilityService
from app.services.booking_intent import BookingIntentService
from app.services.booking_orchestrator import BookingOrchestrator
from app.core.logging import logger

class QAEngine:
    def __init__(self):
        self.retrieval_service = QARetrievalService()

    async def answer_question(
        self,
        question: str,
        filter_tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        booking_context: Optional[Dict[str, Any]] = None,
        is_voice: bool = False
    ) -> QAResponse:
        """Main orchestrator coordinating intent routing (booking vs QA), safety, retrieval, validation, generation, and observability."""
        start_time = time.time()
        logger.info(f"=== QAEngine Request: '{question}' ===")
        
        # 1. Prompt Injection Defense
        is_safe, refusal_reason = SafetyService.is_safe_query(question)
        if not is_safe:
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question,
                intent="unsafe_block",
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                total_latency_ms=total_latency,
                source_count=0,
                confidence_score=0.0
            )
            return QAResponse(
                answer=refusal_reason,
                citations=[],
                confidence=0.0,
                sources=[],
                session_id=session_id,
                booking_context=booking_context
            )
            
        # 2. Intercept Booking/Scheduling Flows
        is_active_booking = False
        if booking_context and booking_context.get("step") != "none":
            is_active_booking = True
        else:
            # Check backend cache state for this session ID
            _, cached_ctx = BookingOrchestrator.get_or_create_session(session_id)
            if cached_ctx and cached_ctx.get("step") != "none":
                is_active_booking = True
                
        booking_intent_data = await BookingIntentService.classify_booking_intent(question)
        
        if is_active_booking or booking_intent_data:
            intent_str = booking_intent_data["intent"] if booking_intent_data else "booking_continuation"
            resolved_session_id, resolved_context = BookingOrchestrator.get_or_create_session(session_id, booking_context)
            
            # Delegate to BookingOrchestrator
            res = await BookingOrchestrator.process_booking_message(
                question=question,
                session_id=resolved_session_id,
                context=resolved_context,
                intent=intent_str
            )
            
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question,
                intent=intent_str,
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                total_latency_ms=total_latency,
                source_count=len(res.sources) if res.sources else 0,
                confidence_score=res.confidence
            )
            return res

        # 2. Intent Classification
        intent_data = await QueryProcessor.classify_intent(question)
        intent = intent_data["intent"]
        
        retrieval_start = time.time()
        context = ""
        diversity_score = 0.0
        retrieval_results: List[Tuple[Dict[str, Any], float]] = []
        top_score = 999.0
        
        # 3. Router logic
        if intent == "booking_request":
            # Direct static response for scheduling interviews
            booking_answer = (
                "I would be glad to schedule an interview with you! You can book a slot directly on my "
                "Google Calendar using the booking interface in this platform, or view my calendar here: "
                "https://calendar.google.com/calendar (or ask me about my current available times)."
            )
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question,
                intent=intent,
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                total_latency_ms=total_latency,
                source_count=1,
                confidence_score=1.0
            )
            return QAResponse(
                answer=booking_answer,
                citations=["Google Calendar Booking Interface"],
                confidence=1.0,
                sources=[EvidenceItem(source="Booking Agent", snippet="Google Calendar scheduling link integration available.")]
            )
            
        elif intent == "availability_question":
            # Availability response using calendar/persona cached details
            availability_answer = (
                "My current availability for interviews is open on weekday afternoons (Monday to Friday, "
                "2:00 PM to 6:00 PM IST). You can use the calendar booking panel on this website to select "
                "a slot that fits your schedule."
            )
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question,
                intent=intent,
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                total_latency_ms=total_latency,
                source_count=1,
                confidence_score=1.0
            )
            return QAResponse(
                answer=availability_answer,
                citations=["Google Calendar API"],
                confidence=1.0,
                sources=[EvidenceItem(source="Google Calendar API", snippet="Interview availability slots: Mon-Fri 14:00 - 18:00 IST.")]
            )

        elif intent == "hiring_fit_question":
            # Special Case: Hiring Fit Engine loads full career context
            context = HiringFitEngine.compile_hiring_context()
            diversity_score = 1.0
            top_score = 0.1  # Mock highly relevant score
            # Gather stubs for evidence panel
            self.retrieval_service.vector_store.load()
            metadata_map = self.retrieval_service.vector_store.metadata_map
            # Take top 3 unique documents to show in panel
            seen_types = set()
            for item in metadata_map.values():
                stype = item.get("metadata", {}).get("source_type")
                if stype and stype not in seen_types:
                    retrieval_results.append((item, 0.1))
                    seen_types.add(stype)
                    if len(seen_types) >= 4:
                        break
                        
        else:
            # Standard semantic search path
            if is_voice:
                logger.info("Voice call detected. Bypassing LLM query rewriter for latency.")
                rewritten_query = question
            else:
                # Rewrite query
                rewritten_query = await QueryProcessor.rewrite_query(question, intent)
            
            # Fetch relevant diverse chunks
            retrieval_results = self.retrieval_service.retrieve_grounded_chunks(
                rewritten_query=rewritten_query,
                top_k=5,
                relevance_threshold=1.6,
                max_chunks_per_source=2,
                filter_tags=filter_tags
            )
            
            if retrieval_results:
                top_score = retrieval_results[0][1]
                # Build context
                context, diversity_score = ContextBuilder.build_context(retrieval_results)

        retrieval_latency = (time.time() - retrieval_start) * 1000

        # 4. Metric-Based Grounding Validator
        # If no chunks match or the score is too poor (L2 distance > 1.6)
        if (not context or "No matching evidence found" in context or top_score > 1.6) and intent != "hiring_fit_question":
            logger.warning(f"Grounding check failed: score {top_score} exceeds threshold or context is empty.")
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question,
                intent=intent,
                retrieval_latency_ms=retrieval_latency,
                generation_latency_ms=0.0,
                total_latency_ms=total_latency,
                source_count=0,
                confidence_score=0.0
            )
            return QAResponse(
                answer=AnswerGenerator.REFUSAL_MESSAGE,
                citations=[],
                confidence=0.0,
                sources=[],
                session_id=session_id,
                booking_context=booking_context
            )

        # 5. Answer Generation (with verification & regeneration)
        generation_start = time.time()
        answer = await AnswerGenerator.generate_grounded_answer(question, context, intent, is_voice=is_voice)
        generation_latency = (time.time() - generation_start) * 1000

        # 6. Citation & Evidence Panel Builder
        citations, sources = AnswerGenerator.compile_evidence_panel(answer, retrieval_results)

        # 7. Compute Grounding Confidence Score
        if answer == AnswerGenerator.REFUSAL_MESSAGE:
            confidence = 0.0
        elif intent == "hiring_fit_question":
            confidence = 1.0
        else:
            # Map L2 score (roughly 0.0 - 2.0) to confidence score (0.0 - 1.0)
            confidence = max(0.1, min(1.0, 1.0 - (top_score / 2.0)))

        # 8. Observability Logging
        total_latency = (time.time() - start_time) * 1000
        ObservabilityService.log_query_metrics(
            question=question,
            intent=intent,
            retrieval_latency_ms=retrieval_latency,
            generation_latency_ms=generation_latency,
            total_latency_ms=total_latency,
            source_count=len(sources),
            confidence_score=confidence
        )

        return QAResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            sources=sources,
            session_id=session_id,
            booking_context=booking_context
        )

    async def answer_question_stream(
        self,
        question: str,
        filter_tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        booking_context: Optional[Dict[str, Any]] = None
    ):
        """Streams answers using Server-Sent Events, yielding tokens and final metadata."""
        start_time = time.time()
        
        # 1. Prompt Injection Defense
        is_safe, refusal_reason = SafetyService.is_safe_query(question)
        if not is_safe:
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question, intent="unsafe_block",
                retrieval_latency_ms=0.0, generation_latency_ms=0.0,
                total_latency_ms=total_latency, source_count=0, confidence_score=0.0
            )
            yield f"data: {json.dumps({'type': 'token', 'content': refusal_reason})}\n\n"
            yield f"data: {json.dumps({'type': 'metadata', 'answer': refusal_reason, 'citations': [], 'confidence': 0.0, 'sources': [], 'session_id': session_id, 'booking_context': booking_context})}\n\n"
            return

        # 2. Intercept Booking Flows
        is_active_booking = False
        if booking_context and booking_context.get("step") != "none":
            is_active_booking = True
        else:
            _, cached_ctx = BookingOrchestrator.get_or_create_session(session_id)
            if cached_ctx and cached_ctx.get("step") != "none":
                is_active_booking = True
                
        booking_intent_data = await BookingIntentService.classify_booking_intent(question)
        
        if is_active_booking or booking_intent_data:
            intent_str = booking_intent_data["intent"] if booking_intent_data else "booking_continuation"
            resolved_session_id, resolved_context = BookingOrchestrator.get_or_create_session(session_id, booking_context)
            
            response = await BookingOrchestrator.process_booking_message(
                question=question,
                session_id=resolved_session_id,
                context=resolved_context,
                intent=intent_str
            )
            
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question,
                intent=intent_str,
                retrieval_latency_ms=0.0,
                generation_latency_ms=0.0,
                total_latency_ms=total_latency,
                source_count=len(response.sources) if response.sources else 0,
                confidence_score=response.confidence
            )
            
            # Stream booking reply
            yield f"data: {json.dumps({'type': 'token', 'content': response.answer})}\n\n"
            yield f"data: {json.dumps({'type': 'metadata', 'answer': response.answer, 'citations': response.citations, 'confidence': response.confidence, 'sources': [ev.model_dump() for ev in response.sources] if response.sources else [], 'session_id': resolved_session_id, 'booking_context': response.booking_context})}\n\n"
            return

        # 3. Intent Routing for general QA
        intent_data = await QueryProcessor.classify_intent(question)
        intent = intent_data["intent"]
        
        retrieval_start = time.time()
        context = ""
        diversity_score = 0.0
        retrieval_results = []
        top_score = 999.0
        
        if intent == "hiring_fit_question":
            context = HiringFitEngine.compile_hiring_context()
            diversity_score = 1.0
            top_score = 0.1
            
            self.retrieval_service.vector_store.load()
            metadata_map = self.retrieval_service.vector_store.metadata_map
            seen_types = set()
            for item in metadata_map.values():
                stype = item.get("metadata", {}).get("source_type")
                if stype and stype not in seen_types:
                    retrieval_results.append((item, 0.1))
                    seen_types.add(stype)
                    if len(seen_types) >= 4:
                        break
        else:
            rewritten_query = await QueryProcessor.rewrite_query(question, intent)
            retrieval_results = self.retrieval_service.retrieve_grounded_chunks(
                rewritten_query=rewritten_query,
                top_k=5,
                relevance_threshold=1.6,
                max_chunks_per_source=2,
                filter_tags=filter_tags
            )
            if retrieval_results:
                top_score = retrieval_results[0][1]
                context, diversity_score = ContextBuilder.build_context(retrieval_results)

        retrieval_latency = (time.time() - retrieval_start) * 1000

        # 4. Grounding Check
        if (not context or "No matching evidence found" in context or top_score > 1.6) and intent != "hiring_fit_question":
            total_latency = (time.time() - start_time) * 1000
            ObservabilityService.log_query_metrics(
                question=question, intent=intent,
                retrieval_latency_ms=retrieval_latency, generation_latency_ms=0.0,
                total_latency_ms=total_latency, source_count=0, confidence_score=0.0
            )
            refusal = AnswerGenerator.REFUSAL_MESSAGE
            yield f"data: {json.dumps({'type': 'token', 'content': refusal})}\n\n"
            yield f"data: {json.dumps({'type': 'metadata', 'answer': refusal, 'citations': [], 'confidence': 0.0, 'sources': [], 'session_id': session_id, 'booking_context': booking_context})}\n\n"
            return

        # 5. Stream generation
        generation_start = time.time()
        full_text_accum = []
        
        async for token in AnswerGenerator.generate_grounded_answer_stream(question, context, intent):
            full_text_accum.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            
        generation_latency = (time.time() - generation_start) * 1000
        full_answer = "".join(full_text_accum)

        # 6. Citations & Evidence Panel
        citations, sources = AnswerGenerator.compile_evidence_panel(full_answer, retrieval_results)

        # 7. Confidence Score
        if full_answer == AnswerGenerator.REFUSAL_MESSAGE:
            confidence = 0.0
        elif intent == "hiring_fit_question":
            confidence = 1.0
        else:
            confidence = max(0.1, min(1.0, 1.0 - (top_score / 2.0)))

        # 8. Observability Logging
        total_latency = (time.time() - start_time) * 1000
        ObservabilityService.log_query_metrics(
            question=question, intent=intent,
            retrieval_latency_ms=retrieval_latency, generation_latency_ms=generation_latency,
            total_latency_ms=total_latency, source_count=len(sources), confidence_score=confidence
        )

        # 9. Yield Final Metadata (Frontend will catch this to set sources)
        metadata_payload = {
            "type": "metadata",
            "answer": full_answer,
            "citations": citations,
            "confidence": confidence,
            "sources": [ev.model_dump() for ev in sources],
            "session_id": session_id,
            "booking_context": booking_context
        }
        yield f"data: {json.dumps(metadata_payload)}\n\n"
