"""
Tests for Task 30 (subtask 30.3): GA event routing validation.

Validates that both GA event names and preview event names are handled
correctly in the receive_realtime match statement:

1. GA 'response.output_audio.delta' and preview 'response.audio.delta'
   both route to _response_audio_delta
2. GA 'response.output_text.delta' and preview 'response.text.delta'
   both route to _response_text_delta
3. GA 'response.output_audio_transcript.delta' and preview
   'response.audio_transcript.delta' both route to
   _response_audio_transcript_delta
4. New GA events 'conversation.item.added' and 'conversation.item.done'
   have dedicated handlers
5. GA 'done' variants (response.output_audio.done, etc.) are handled

NOTE: These tests use source-code inspection and mock-based dispatch
      to verify routing without hitting real Azure endpoints.
"""

import sys
import os
import inspect
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(is_ga_mode: bool = True, debug: bool = False):
    """Create a RealtimeClient with mocked connections."""
    mock_realtime = AsyncMock()
    mock_ws = MagicMock()
    mock_ws.client_state = "CONNECTED"
    mock_ws.send_json = AsyncMock()

    return RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=debug,
        is_ga_mode=is_ga_mode,
    )


def _get_receive_source():
    """Get the source code of receive_realtime for inspection."""
    client = _make_client()
    return inspect.getsource(client.receive_realtime.__wrapped__)


# ---------------------------------------------------------------------------
# Audio Delta Event Routing
# ---------------------------------------------------------------------------


class TestAudioDeltaEventRouting:
    """Both GA and preview audio delta events should route to _response_audio_delta."""

    def test_preview_audio_delta_in_match(self):
        """'response.audio.delta' (preview) should be a case in receive_realtime."""
        source = _get_receive_source()
        assert "response.audio.delta" in source

    def test_ga_audio_delta_in_match(self):
        """'response.output_audio.delta' (GA) should be a case in receive_realtime."""
        source = _get_receive_source()
        assert "response.output_audio.delta" in source

    def test_both_audio_deltas_call_same_handler(self):
        """Both audio delta cases should call _response_audio_delta."""
        source = _get_receive_source()
        # Find the lines containing the GA and preview audio delta cases
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if '"response.output_audio.delta"' in line:
                # Check that the next non-comment line calls _response_audio_delta
                for j in range(i + 1, min(i + 4, len(lines))):
                    if "_response_audio_delta" in lines[j]:
                        return  # Found it
        pytest.fail(
            "GA audio delta case should call _response_audio_delta"
        )


# ---------------------------------------------------------------------------
# Text Delta Event Routing
# ---------------------------------------------------------------------------


class TestTextDeltaEventRouting:
    """Both GA and preview text delta events should route to _response_text_delta."""

    def test_preview_text_delta_in_match(self):
        """'response.text.delta' (preview) should be a case in receive_realtime."""
        source = _get_receive_source()
        assert "response.text.delta" in source

    def test_ga_text_delta_in_match(self):
        """'response.output_text.delta' (GA) should be a case in receive_realtime."""
        source = _get_receive_source()
        assert "response.output_text.delta" in source

    def test_both_text_deltas_call_same_handler(self):
        """Both text delta cases should call _response_text_delta."""
        source = _get_receive_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if '"response.output_text.delta"' in line:
                for j in range(i + 1, min(i + 4, len(lines))):
                    if "_response_text_delta" in lines[j]:
                        return
        pytest.fail(
            "GA text delta case should call _response_text_delta"
        )


# ---------------------------------------------------------------------------
# Audio Transcript Delta Event Routing
# ---------------------------------------------------------------------------


class TestAudioTranscriptDeltaEventRouting:
    """Both GA and preview transcript delta events should route correctly."""

    def test_preview_transcript_delta_in_match(self):
        """'response.audio_transcript.delta' (preview) should be handled."""
        source = _get_receive_source()
        assert "response.audio_transcript.delta" in source

    def test_ga_transcript_delta_in_match(self):
        """'response.output_audio_transcript.delta' (GA) should be handled."""
        source = _get_receive_source()
        assert "response.output_audio_transcript.delta" in source

    def test_both_transcript_deltas_call_same_handler(self):
        """Both transcript delta cases should call _response_audio_transcript_delta."""
        source = _get_receive_source()
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if '"response.output_audio_transcript.delta"' in line:
                for j in range(i + 1, min(i + 4, len(lines))):
                    if "_response_audio_transcript_delta" in lines[j]:
                        return
        pytest.fail(
            "GA transcript delta case should call _response_audio_transcript_delta"
        )


# ---------------------------------------------------------------------------
# Done Event Variants
# ---------------------------------------------------------------------------


class TestDoneEventRouting:
    """GA 'done' event variants should be handled alongside preview versions."""

    def test_ga_audio_done_in_match(self):
        """'response.output_audio.done' (GA) should be handled."""
        source = _get_receive_source()
        assert "response.output_audio.done" in source

    def test_ga_text_done_in_match(self):
        """'response.output_text.done' (GA) should be handled."""
        source = _get_receive_source()
        assert "response.output_text.done" in source

    def test_ga_transcript_done_in_match(self):
        """'response.output_audio_transcript.done' (GA) should be handled."""
        source = _get_receive_source()
        assert "response.output_audio_transcript.done" in source

    def test_preview_audio_done_still_handled(self):
        """'response.audio.done' (preview) should still be handled."""
        source = _get_receive_source()
        assert "response.audio.done" in source

    def test_preview_text_done_still_handled(self):
        """'response.text.done' (preview) should still be handled."""
        source = _get_receive_source()
        assert "response.text.done" in source

    def test_preview_transcript_done_still_handled(self):
        """'response.audio_transcript.done' (preview) should still be handled."""
        source = _get_receive_source()
        assert "response.audio_transcript.done" in source


# ---------------------------------------------------------------------------
# New GA-only Events
# ---------------------------------------------------------------------------


class TestNewGAEvents:
    """GA introduces conversation.item.added and conversation.item.done events."""

    def test_conversation_item_added_in_match(self):
        """'conversation.item.added' should be a case in receive_realtime."""
        source = _get_receive_source()
        assert "conversation.item.added" in source

    def test_conversation_item_done_in_match(self):
        """'conversation.item.done' should be a case in receive_realtime."""
        source = _get_receive_source()
        assert "conversation.item.done" in source

    def test_conversation_item_added_has_handler(self):
        """RealtimeClient should have a _conversation_item_added method."""
        client = _make_client()
        assert hasattr(client, "_conversation_item_added")
        assert callable(client._conversation_item_added)

    def test_conversation_item_done_has_handler(self):
        """RealtimeClient should have a _conversation_item_done method."""
        client = _make_client()
        assert hasattr(client, "_conversation_item_done")
        assert callable(client._conversation_item_done)

    @pytest.mark.asyncio
    async def test_conversation_item_added_runs_without_error(self):
        """_conversation_item_added should run without raising on a mock event."""
        client = _make_client(debug=True)
        mock_event = MagicMock()
        mock_event.type = "conversation.item.added"
        mock_event.item = {"id": "item_001", "type": "message"}

        # Should not raise
        await client._conversation_item_added(mock_event)

    @pytest.mark.asyncio
    async def test_conversation_item_done_runs_without_error(self):
        """_conversation_item_done should run without raising on a mock event."""
        client = _make_client(debug=True)
        mock_event = MagicMock()
        mock_event.type = "conversation.item.done"
        mock_event.item = {"id": "item_001", "type": "message"}

        # Should not raise
        await client._conversation_item_done(mock_event)


# ---------------------------------------------------------------------------
# Complete Event Coverage Check
# ---------------------------------------------------------------------------


class TestEventCoverageCompleteness:
    """Verify that all three renamed GA event pairs are present."""

    def test_all_three_ga_delta_renames_present(self):
        """All 3 critical GA event renames from the migration must be in the match."""
        source = _get_receive_source()

        ga_events = [
            "response.output_audio.delta",
            "response.output_text.delta",
            "response.output_audio_transcript.delta",
        ]
        for event in ga_events:
            assert event in source, f"Missing GA event handler for: {event}"

    def test_all_three_preview_delta_events_still_present(self):
        """All 3 original preview event names should still be in the match."""
        source = _get_receive_source()

        preview_events = [
            "response.audio.delta",
            "response.text.delta",
            "response.audio_transcript.delta",
        ]
        for event in preview_events:
            assert event in source, f"Missing preview event handler for: {event}"
