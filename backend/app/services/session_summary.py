"""
Session Summary Service — lightweight conversation memory using summaries
instead of full message history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.persistence.models import Session as SessionModel


class SessionSummaryService:
    """Manages conversation summaries for lightweight memory.
    
    Instead of storing every message (which grows unbounded),
    we keep a running summary of the conversation context.
    """
    
    MAX_SUMMARY_LENGTH = 2000  # Characters
    
    def __init__(self, db: Session):
        self.db = db
    
    def update_summary(
        self,
        session: SessionModel,
        user_message: str,
        assistant_response: str,
    ) -> str:
        """Update session summary with new exchange.
        
        For simplicity, we append key points. In production,
        this could use an LLM to condense the conversation.
        """
        # Truncate messages if too long
        user_short = user_message[:200] + "..." if len(user_message) > 200 else user_message
        assistant_short = assistant_response[:300] + "..." if len(assistant_response) > 300 else assistant_response
        
        # Create entry for this exchange
        exchange = f"User: {user_short}\nAssistant: {assistant_short}\n\n"
        
        # Append to existing summary
        current_summary = session.summary or ""
        new_summary = current_summary + exchange
        
        # Keep only last N characters to prevent unbounded growth
        if len(new_summary) > self.MAX_SUMMARY_LENGTH:
            # Keep the end (most recent context)
            new_summary = "..." + new_summary[-(self.MAX_SUMMARY_LENGTH - 3):]
        
        session.summary = new_summary
        session.summary_updated_at = datetime.now(timezone.utc)
        self.db.commit()
        
        return new_summary
    
    def get_summary(self, session: SessionModel) -> str:
        """Get current summary for context injection."""
        return session.summary or "No previous context."
    
    def clear_summary(self, session: SessionModel) -> None:
        """Clear summary (e.g., on /new command)."""
        session.summary = ""
        session.summary_updated_at = None
        self.db.commit()
