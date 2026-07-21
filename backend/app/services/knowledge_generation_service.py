import logging
import json
import os
from sqlalchemy.orm import Session
from app.database.models.ticket import Ticket
from app.database.models.workflow_models import TicketComment, KnowledgeDraft

logger = logging.getLogger("it-agent-backend")

class KnowledgeGenerationService:
    @staticmethod
    def generate_kb_summary(ticket_details: dict) -> dict:
        """
        Uses Gemini to generate structured knowledge article contents from a resolved ticket.
        """

        from app.services.ai_provider import get_ai_provider
        provider = get_ai_provider()
        
        prompt = f"""
        You are an IT Knowledge Base Expert. Analyze this resolved IT ticket and draft a Knowledge Base Article.
        Return ONLY a raw JSON object (without markdown code blocks, ```json wrapper, or extra text) with the following fields:
        {{
            "title": "Clear and search-friendly title",
            "problem": "Brief description of the problem",
            "environment": "Environment details, e.g. OS, client application",
            "symptoms": "Symptoms described by user",
            "root_cause": "The root cause of the issue",
            "resolution": "Step-by-step resolution details",
            "workaround": "Any temporary workaround if applicable",
            "tags": "comma, separated, tags",
            "category": "Main IT category",
            "affected_systems": "systems, tools, apps affected"
        }}

        Ticket details to analyze:
        Category: {ticket_details.get('category')}
        Description: {ticket_details.get('description')}
        Resolution Context: {ticket_details.get('previous_resolution') or ''}
        Comments History:
        {ticket_details.get('comments_str')}
        """
        
        try:
            response = provider.generate_response(prompt)
            if response:
                raw_text = response.strip()
                # Clean markdown wrapper if Gemini added it
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_text = "\n".join(lines).strip()
                
                parsed = json.loads(raw_text)
                return parsed
        except Exception as e:
            logger.error("Knowledge Generation: AI provider request failed or parsing failed: %s", e)
            
        return KnowledgeGenerationService._fallback_draft(ticket_details)

    @staticmethod
    def _fallback_draft(ticket_details: dict) -> dict:
        """
        Generates a basic draft if Gemini fails or is unconfigured.
        """
        return {
            "title": f"KB Draft - {ticket_details.get('ticket_id')} - {ticket_details.get('category')}",
            "problem": ticket_details.get('description') or "No description provided.",
            "environment": "Bridgestone IT Environment",
            "symptoms": ticket_details.get('description') or "No symptoms specified.",
            "root_cause": "Under investigation.",
            "resolution": ticket_details.get('previous_resolution') or "Resolved by IT Support.",
            "workaround": "None available.",
            "tags": f"{ticket_details.get('category') or 'general'}, auto-generated",
            "category": ticket_details.get('category') or "General",
            "affected_systems": ticket_details.get('category') or "General"
        }

    @classmethod
    def generate_draft_for_ticket(cls, db: Session, ticket_id: str) -> KnowledgeDraft:
        """
        Fetches ticket and comments context, calls generator, and commits new KnowledgeDraft.
        """
        ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if not ticket:
            logger.error("Knowledge Generation: Ticket %s not found.", ticket_id)
            return None
            
        # Get ticket comments for troubleshooting context
        comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).all()
        comments_str = "\n".join(
            f"[{c.author} ({'Internal' if c.is_internal else 'Customer'})]: {c.text}"
            for c in comments
        )
        
        ticket_details = {
            "ticket_id": ticket_id,
            "category": ticket.category,
            "description": ticket.description or ticket.issue_description,
            "previous_resolution": ticket.previous_resolution,
            "comments_str": comments_str
        }
        
        draft_content = cls.generate_kb_summary(ticket_details)
        
        draft = KnowledgeDraft(
            title=draft_content.get("title", f"KB - {ticket_id}"),
            problem=draft_content.get("problem"),
            environment=draft_content.get("environment"),
            symptoms=draft_content.get("symptoms"),
            root_cause=draft_content.get("root_cause"),
            resolution=draft_content.get("resolution"),
            workaround=draft_content.get("workaround"),
            tags=draft_content.get("tags"),
            category=draft_content.get("category"),
            affected_systems=draft_content.get("affected_systems"),
            confidence=1.0 if os.getenv("GEMINI_API_KEY") else 0.5,
            source_ticket_id=ticket_id
        )
        
        db.add(draft)
        # We flush so it has an ID, outer transaction handles commit
        db.flush()
        logger.info("Knowledge Generation: Generated KB draft for ticket %s", ticket_id)
        
        # Log timeline event
        from app.services.timeline_service import TimelineService
        TimelineService.log_event(
            db=db,
            ticket_id=ticket_id,
            event_type="KNOWLEDGE_DRAFTED",
            actor="system",
            action="kb draft generation",
            description=f"Knowledge Base draft article titled '{draft.title}' automatically compiled.",
            correlation_id=None
        )
        
        return draft
