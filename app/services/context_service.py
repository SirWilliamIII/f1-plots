"""
Session Context Service

Manages telemetry context storage and retrieval for user sessions.
"""

import uuid
import time
import logging
import gc
from flask import session as flask_session


# Simple in-memory context storage
session_contexts = {}
SESSION_CONTEXT_TTL = 3600  # 1 hour TTL for session contexts


def cleanup_old_contexts():
    """Remove session contexts older than TTL to prevent memory leaks"""
    global session_contexts
    current_time = time.time()
    expired = [
        sid for sid, ctx in session_contexts.items()
        if current_time - ctx.get('created_at', 0) > SESSION_CONTEXT_TTL
    ]
    for sid in expired:
        del session_contexts[sid]
    if expired:
        logging.info(f"♻️  Cleaned up {len(expired)} expired session contexts")
        gc.collect()


def get_or_create_session_id(request):
    """Get session ID from request or create new one"""
    # Check if session ID exists in Flask session
    if 'telemetry_session_id' not in flask_session:
        flask_session['telemetry_session_id'] = str(uuid.uuid4())
    return flask_session['telemetry_session_id']


def store_telemetry_context(session_id: str, context: dict):
    """Store telemetry context for a session with timestamp"""
    global session_contexts
    context['created_at'] = time.time()
    session_contexts[session_id] = context
    logging.info(f"📊 Stored context for session {session_id[:8]}... (total: {len(session_contexts)})")

    # Clean up old contexts on every store to prevent accumulation
    cleanup_old_contexts()


def retrieve_telemetry_context(session_id: str) -> dict:
    """Retrieve telemetry context for a session"""
    global session_contexts
    return session_contexts.get(session_id, {})
