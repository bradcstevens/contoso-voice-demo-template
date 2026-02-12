"""
Tests for RealtimeClient GA/preview mode configuration flag (Task 29).

Verifies that RealtimeClient accepts, stores, and defaults the is_ga_mode
parameter correctly, enabling downstream tasks (27, 28) to branch on
session format and event names.

Updated for Task 26: is_ga_mode now auto-detects based on connection type
(isinstance check against AsyncRealtimeConnectionGA). A plain mock that is
not spec'd to the GA class will auto-detect as False (preview mode).
"""
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Ensure the api directory is on the path so we can import voice module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from voice import RealtimeClient


def _make_realtime_client(is_ga_mode=None, debug=False, use_ga_connection=False):
    """Helper to construct a RealtimeClient with mocked dependencies.

    Args:
        is_ga_mode: Explicit override for GA mode. None means auto-detect.
        debug: Debug flag.
        use_ga_connection: If True, spec the mock to GA AsyncRealtimeConnection
            so auto-detection identifies it as GA mode.
    """
    if use_ga_connection:
        from openai.resources.realtime.realtime import (
            AsyncRealtimeConnection as GAConnection,
        )
        mock_realtime = MagicMock(spec=GAConnection)
    else:
        mock_realtime = AsyncMock()
    mock_websocket = MagicMock()
    mock_websocket.client_state = "CONNECTED"

    kwargs = {
        "realtime": mock_realtime,
        "client": mock_websocket,
        "debug": debug,
    }
    if is_ga_mode is not None:
        kwargs["is_ga_mode"] = is_ga_mode

    return RealtimeClient(**kwargs)


class TestRealtimeClientModeFlag:
    """Core tests for the is_ga_mode configuration flag."""

    def test_default_mode_auto_detects_preview(self):
        """When is_ga_mode is not provided and connection is not GA, auto-detect as False."""
        client = _make_realtime_client()
        assert client.is_ga_mode is False

    def test_default_mode_auto_detects_ga(self):
        """When is_ga_mode is not provided and connection IS GA, auto-detect as True."""
        client = _make_realtime_client(use_ga_connection=True)
        assert client.is_ga_mode is True

    def test_explicit_ga_mode(self):
        """When is_ga_mode=True is passed, it should be stored as True."""
        client = _make_realtime_client(is_ga_mode=True)
        assert client.is_ga_mode is True

    def test_explicit_preview_mode(self):
        """When is_ga_mode=False is passed, it should be stored as False (preview mode)."""
        client = _make_realtime_client(is_ga_mode=False)
        assert client.is_ga_mode is False

    def test_mode_does_not_affect_other_attributes(self):
        """Setting is_ga_mode should not interfere with existing attributes."""
        client = _make_realtime_client(is_ga_mode=False, debug=True)
        assert client.is_ga_mode is False
        assert client.debug is True
        assert client.active is True
        assert client.realtime is not None
        assert client.client is not None

    def test_mode_flag_is_boolean_type(self):
        """The is_ga_mode attribute should be a boolean."""
        client_ga = _make_realtime_client(is_ga_mode=True)
        client_preview = _make_realtime_client(is_ga_mode=False)
        assert isinstance(client_ga.is_ga_mode, bool)
        assert isinstance(client_preview.is_ga_mode, bool)
