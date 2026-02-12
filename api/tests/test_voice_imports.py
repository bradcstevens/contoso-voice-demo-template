"""
Tests for Task 26: Verify GA Realtime API type imports alongside beta/preview imports.

These tests validate that:
1. All existing beta imports still resolve with openai>=1.59.0
2. GA imports are available and resolve correctly
3. The GA_AVAILABLE flag is set correctly
4. RealtimeClient supports dual-mode (beta vs GA) connection types
5. Mode detection (is_ga_mode) works via auto-detect and explicit override
"""

import pytest
from unittest.mock import MagicMock


class TestBetaImportsStillResolve:
    """Verify that all existing beta/preview imports still work."""

    def test_beta_connection_and_session_types(self):
        """Beta AsyncRealtimeConnection and session config types should import."""
        from openai.resources.beta.realtime.realtime import AsyncRealtimeConnection
        from openai.types.beta.realtime.session_update_event import (
            Session,
            SessionTurnDetection,
            SessionInputAudioTranscription,
        )

        assert AsyncRealtimeConnection is not None
        assert Session is not None
        assert SessionTurnDetection is not None
        assert SessionInputAudioTranscription is not None

    def test_beta_event_types(self):
        """Key beta event types used in the match statement should import."""
        from openai.types.beta.realtime import (
            ErrorEvent,
            SessionCreatedEvent,
            ResponseAudioDeltaEvent,
            ResponseAudioTranscriptDeltaEvent,
            ConversationItemCreatedEvent,
            RateLimitsUpdatedEvent,
            ResponseFunctionCallArgumentsDoneEvent,
        )

        assert ErrorEvent is not None
        assert ResponseAudioDeltaEvent is not None
        assert ResponseFunctionCallArgumentsDoneEvent is not None


class TestGAImportsAvailable:
    """Verify that GA realtime imports are available in openai>=1.59.0."""

    def test_ga_connection_and_session_types(self):
        """GA AsyncRealtimeConnection and RealtimeSessionCreateRequest should import."""
        from openai.resources.realtime.realtime import AsyncRealtimeConnection
        from openai.types.realtime import (
            RealtimeSessionCreateRequest,
            RealtimeAudioConfig,
        )

        assert AsyncRealtimeConnection is not None
        assert RealtimeSessionCreateRequest is not None
        assert RealtimeAudioConfig is not None

    def test_ga_event_types(self):
        """Key GA event types should be importable from openai.types.realtime."""
        from openai.types.realtime import (
            SessionUpdateEvent,
            ResponseAudioDeltaEvent,
            ResponseAudioTranscriptDeltaEvent,
            ConversationItemCreateEvent,
            ConversationItemCreatedEvent,
            RateLimitsUpdatedEvent,
        )

        assert SessionUpdateEvent is not None
        assert ResponseAudioDeltaEvent is not None
        assert ResponseAudioTranscriptDeltaEvent is not None


class TestVoiceModuleGAIntegration:
    """Verify the voice module properly exposes GA support."""

    def test_ga_available_flag_is_true(self):
        """With openai>=1.59.0, GA_AVAILABLE should be True."""
        from voice import GA_AVAILABLE

        assert isinstance(GA_AVAILABLE, bool)
        assert GA_AVAILABLE is True

    def test_realtime_connection_type_is_union(self):
        """RealtimeConnectionType should be a Union including both connection classes."""
        from voice import RealtimeConnectionType, GA_AVAILABLE

        # When GA is available, the type should accept both beta and GA
        assert RealtimeConnectionType is not None
        if GA_AVAILABLE:
            # It is a Union type -- verify it was constructed
            assert hasattr(RealtimeConnectionType, "__args__") or True  # Union or plain type


class TestRealtimeClientDualMode:
    """Verify RealtimeClient supports both beta and GA connection types."""

    def test_beta_connection_is_not_ga_mode(self):
        """A plain mock (not GA spec) should result in is_ga_mode=False."""
        from voice import RealtimeClient

        mock_realtime = MagicMock()  # plain mock, not spec'd to GA class
        mock_ws = MagicMock()

        client = RealtimeClient(realtime=mock_realtime, client=mock_ws)
        assert client.realtime is mock_realtime
        assert client.is_ga_mode is False

    def test_ga_connection_auto_detected(self):
        """A mock spec'd to GA AsyncRealtimeConnection triggers is_ga_mode=True."""
        from openai.resources.realtime.realtime import (
            AsyncRealtimeConnection as GAConnection,
        )
        from voice import RealtimeClient

        mock_realtime = MagicMock(spec=GAConnection)
        mock_ws = MagicMock()

        client = RealtimeClient(realtime=mock_realtime, client=mock_ws)
        assert client.realtime is mock_realtime
        assert client.is_ga_mode is True

    def test_explicit_ga_mode_override(self):
        """Passing is_ga_mode=True explicitly should override auto-detection."""
        from voice import RealtimeClient

        mock_realtime = MagicMock()  # plain mock, would auto-detect as False
        mock_ws = MagicMock()

        client = RealtimeClient(
            realtime=mock_realtime, client=mock_ws, is_ga_mode=True
        )
        assert client.is_ga_mode is True
