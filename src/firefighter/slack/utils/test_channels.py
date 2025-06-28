"""Utilities for handling test channels."""

from __future__ import annotations

import logging
import os

from firefighter.slack.models.conversation import Conversation

logger = logging.getLogger(__name__)


def get_or_create_test_conversation(tag: str) -> Conversation | None:
    """Get conversation by tag, or use test environment variable if in test mode.
    
    Args:
        tag: The conversation tag to look up
        
    Returns:
        Conversation object if found, None otherwise
    """
    test_mode = os.getenv("TEST_MODE", "False").lower() == "true"
    
    if not test_mode:
        # Production mode: get from database
        return Conversation.objects.get_or_none(tag=tag)
    
    # Test mode: try to get test channel ID from environment
    env_var_name = f"TEST_{tag.upper()}_CHANNEL_ID"
    test_channel_id = os.getenv(env_var_name)
    
    if test_channel_id:
        logger.info(f"Test mode: Using channel ID {test_channel_id} for {tag}")
        # Try to find existing conversation or create a temporary one
        conversation = Conversation.objects.filter(channel_id=test_channel_id).first()
        if conversation:
            return conversation
        else:
            # Create a temporary conversation object for the test channel
            conversation = Conversation(
                channel_id=test_channel_id,
                name=f"test-{tag}",
                tag=tag
            )
            try:
                conversation.save()
                logger.info(f"Test mode: Created conversation for {tag} with channel ID {test_channel_id}")
                return conversation
            except Exception as e:
                logger.warning(f"Test mode: Could not save conversation for {tag}: {e}")
                return conversation  # Return unsaved object for immediate use
    else:
        logger.warning(f"Test mode: No test channel ID found in {env_var_name} environment variable")
        # Fallback to database lookup
        return Conversation.objects.get_or_none(tag=tag)