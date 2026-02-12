"""
Suggestions Pipeline - Backend Tests

Task 62/63/64: Validates the suggestion detection and generation pipeline on the
backend side. Tests the /api/request and /api/suggestion endpoints, the
suggestion_requested() and create_suggestion() functions, and the voice
script template's "suggestions ready" handler.

Task 63 additions: Validates POST /api/request endpoint receives SimpleMessage[]
and returns {requested: boolean}, tests error handling path, validates writeup
prompty detection phrases and examples, and tests suggestion_requested() parsing
edge cases (empty/whitespace responses, single-message lists, prompty identity).

Task 64 additions: Validates /api/suggestion endpoint returns StreamingResponse
with text/event-stream, verifies prompty uses plain-text Image URL (not markdown
image syntax), and validates product/purchase data files.

Tests are split into two groups:
  - Template/file validation tests (no Azure deps needed, always run)
  - Function-level tests (require prompty + Azure SDK, skipped if unavailable)
"""
import json
import re
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import sys
# Ensure the api directory is on the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Conditionally import suggestions module -- it requires prompty.azure which
# depends on the azure SDK. Tests that exercise the actual functions are
# skipped when the SDK is unavailable.
try:
    from suggestions import SimpleMessage, suggestion_requested, create_suggestion
    SUGGESTIONS_AVAILABLE = True
except Exception:
    SUGGESTIONS_AVAILABLE = False

# Conditionally import pydantic for SimpleMessage model tests when the
# suggestions module is not available.
try:
    from pydantic import BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

requires_suggestions = pytest.mark.skipif(
    not SUGGESTIONS_AVAILABLE,
    reason="suggestions module unavailable (azure SDK not installed)"
)

# Conditionally import the FastAPI app -- it requires session -> chat ->
# prompty.azure which depends on the Azure SDK. Endpoint-level tests are
# skipped when the SDK is unavailable.
try:
    from main import app as _fastapi_app
    from fastapi.testclient import TestClient
    APP_AVAILABLE = True
except Exception:
    _fastapi_app = None
    APP_AVAILABLE = False

requires_app = pytest.mark.skipif(
    not APP_AVAILABLE,
    reason="FastAPI app unavailable (azure SDK not installed)"
)

# Import voice module for RealtimeClient and Message tests (Task 67)
from voice import RealtimeClient, Message


def _make_realtime_client(is_ga_mode=False):
    """Create a RealtimeClient with mocked dependencies for testing."""
    mock_realtime = AsyncMock()
    mock_realtime.send = AsyncMock()
    mock_realtime.session = MagicMock()
    mock_realtime.session.update = AsyncMock()
    mock_realtime.response = MagicMock()
    mock_realtime.response.create = AsyncMock()
    mock_ws = MagicMock()
    mock_ws.client_state = "CONNECTED"
    mock_ws.send_json = AsyncMock()
    mock_ws.receive_text = AsyncMock()
    mock_ws.close = AsyncMock()

    return RealtimeClient(
        realtime=mock_realtime,
        client=mock_ws,
        debug=False,
        is_ga_mode=is_ga_mode,
    )


# ---------------------------------------------------------------------------
# 1. suggestion_requested() detection logic
# ---------------------------------------------------------------------------

@requires_suggestions
class TestSuggestionRequested:
    """Tests for the suggestion_requested() function.

    This function uses writeup.prompty to determine if the conversation
    contains a request for visual product suggestions. It requires BOTH
    the user to ask AND the assistant to echo/acknowledge the request.
    """

    @pytest.mark.asyncio
    async def test_returns_true_when_llm_says_yes(self):
        """suggestion_requested() returns True when LLM responds 'YES'."""
        messages = [
            SimpleMessage(name="user", text="Can you show me those visually?"),
            SimpleMessage(name="assistant", text="Sure, I can prepare a visual writeup!"),
        ]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "YES"
            result = await suggestion_requested(messages)

        assert result is True
        mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_llm_says_no(self):
        """suggestion_requested() returns False when LLM responds 'NO'."""
        messages = [
            SimpleMessage(name="user", text="Tell me about your resistors"),
            SimpleMessage(name="assistant", text="We have a wide selection of resistors."),
        ]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "NO"
            result = await suggestion_requested(messages)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_yes_case_insensitive(self):
        """suggestion_requested() handles case-insensitive 'yes' responses."""
        messages = [
            SimpleMessage(name="user", text="Show me products"),
            SimpleMessage(name="assistant", text="I'll prepare that for you."),
        ]

        for response in ["yes", "Yes", "YES", "yes, the user wants a writeup"]:
            with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = response
                result = await suggestion_requested(messages)
            assert result is True, f"Should be True for response: {response!r}"

    @pytest.mark.asyncio
    async def test_returns_false_for_no_variants(self):
        """suggestion_requested() returns False for 'NO' and other negative responses."""
        messages = [
            SimpleMessage(name="user", text="Hello"),
            SimpleMessage(name="assistant", text="Hi there!"),
        ]

        for response in ["NO", "no", "No", "not sure", "nope"]:
            with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = response
                result = await suggestion_requested(messages)
            assert result is False, f"Should be False for response: {response!r}"

    @pytest.mark.asyncio
    async def test_passes_messages_as_context_to_prompty(self):
        """suggestion_requested() formats messages correctly for the prompty template."""
        messages = [
            SimpleMessage(name="user", text="Show me visually"),
            SimpleMessage(name="assistant", text="Sure!"),
        ]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "NO"
            await suggestion_requested(messages)

        call_kwargs = mock_exec.call_args
        inputs = call_kwargs.kwargs.get("inputs") or call_kwargs[1].get("inputs")
        assert "context" in inputs
        assert len(inputs["context"]) == 2
        assert inputs["context"][0] == {"name": "user", "text": "Show me visually"}
        assert inputs["context"][1] == {"name": "assistant", "text": "Sure!"}


# ---------------------------------------------------------------------------
# 2. create_suggestion() streaming generation
# ---------------------------------------------------------------------------

@requires_suggestions
class TestCreateSuggestion:
    """Tests for the create_suggestion() async generator.

    This function uses suggestions.prompty to generate a streaming markdown
    response with product recommendations.
    """

    @pytest.mark.asyncio
    async def test_yields_chunks_from_llm_stream(self):
        """create_suggestion() yields markdown chunks from the LLM stream."""
        messages = [
            SimpleMessage(name="user", text="Show me oscilloscopes"),
            SimpleMessage(name="assistant", text="Here are some options."),
        ]

        async def mock_stream():
            for chunk in ["# Recommendations\n", "\n## DSO138 Oscilloscope", "\nGreat for beginners"]:
                yield chunk

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_stream()

            chunks = []
            async for chunk in create_suggestion("Brad", messages):
                chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0] == "# Recommendations\n"
        assert "".join(chunks) == "# Recommendations\n\n## DSO138 Oscilloscope\nGreat for beginners"

    @pytest.mark.asyncio
    async def test_passes_customer_name_and_messages(self):
        """create_suggestion() passes customer name and formatted messages to prompty."""
        messages = [
            SimpleMessage(name="user", text="I need capacitors"),
            SimpleMessage(name="assistant", text="I can help with that."),
        ]

        async def mock_stream():
            yield "content"

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_stream()

            async for _ in create_suggestion("Alice", messages):
                pass

        call_kwargs = mock_exec.call_args
        inputs = call_kwargs.kwargs.get("inputs") or call_kwargs[1].get("inputs")
        assert inputs["customer"] == "Alice"
        assert len(inputs["context"]) == 2

    @pytest.mark.asyncio
    async def test_requests_streaming_mode(self):
        """create_suggestion() passes stream=True parameter to prompty."""
        messages = [SimpleMessage(name="user", text="test")]

        async def mock_stream():
            yield "content"

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_stream()

            async for _ in create_suggestion("Brad", messages):
                pass

        call_kwargs = mock_exec.call_args
        params = call_kwargs.kwargs.get("parameters") or call_kwargs[1].get("parameters")
        assert params == {"stream": True}


# ---------------------------------------------------------------------------
# 3. SimpleMessage model validation (uses Pydantic directly if suggestions
#    module is not available)
# ---------------------------------------------------------------------------

class TestSimpleMessage:
    """Tests for the SimpleMessage Pydantic model."""

    @pytest.mark.skipif(
        not SUGGESTIONS_AVAILABLE and not PYDANTIC_AVAILABLE,
        reason="neither suggestions module nor pydantic available"
    )
    def test_valid_message_creation(self):
        if SUGGESTIONS_AVAILABLE:
            msg = SimpleMessage(name="user", text="Hello")
        else:
            # Recreate the model locally for testing
            class _SimpleMessage(BaseModel):
                name: str
                text: str
            msg = _SimpleMessage(name="user", text="Hello")
        assert msg.name == "user"
        assert msg.text == "Hello"

    @pytest.mark.skipif(
        not SUGGESTIONS_AVAILABLE and not PYDANTIC_AVAILABLE,
        reason="neither suggestions module nor pydantic available"
    )
    def test_assistant_message_creation(self):
        if SUGGESTIONS_AVAILABLE:
            msg = SimpleMessage(name="assistant", text="Hi there!")
        else:
            class _SimpleMessage(BaseModel):
                name: str
                text: str
            msg = _SimpleMessage(name="assistant", text="Hi there!")
        assert msg.name == "assistant"
        assert msg.text == "Hi there!"

    @pytest.mark.skipif(
        not SUGGESTIONS_AVAILABLE and not PYDANTIC_AVAILABLE,
        reason="neither suggestions module nor pydantic available"
    )
    def test_message_serialization(self):
        if SUGGESTIONS_AVAILABLE:
            msg = SimpleMessage(name="user", text="Show me products")
        else:
            class _SimpleMessage(BaseModel):
                name: str
                text: str
            msg = _SimpleMessage(name="user", text="Show me products")
        data = msg.model_dump()
        assert data == {"name": "user", "text": "Show me products"}

    @pytest.mark.skipif(
        not SUGGESTIONS_AVAILABLE and not PYDANTIC_AVAILABLE,
        reason="neither suggestions module nor pydantic available"
    )
    def test_message_from_dict(self):
        if SUGGESTIONS_AVAILABLE:
            msg = SimpleMessage(**{"name": "assistant", "text": "Here you go"})
        else:
            class _SimpleMessage(BaseModel):
                name: str
                text: str
            msg = _SimpleMessage(**{"name": "assistant", "text": "Here you go"})
        assert msg.name == "assistant"
        assert msg.text == "Here you go"


# ---------------------------------------------------------------------------
# 4. Voice script template - "suggestions ready" handler
# ---------------------------------------------------------------------------

class TestVoiceScriptTemplate:
    """Tests that the voice script template (script.jinja2) contains the
    correct handler for the synthetic 'The visual suggestions are ready'
    message that chat.tsx sends after streaming suggestions.
    """

    def test_script_contains_suggestions_ready_phrase(self):
        """The voice script template must contain the exact synthetic phrase."""
        script_path = Path(__file__).parent.parent / "voice" / "script.jinja2"
        assert script_path.exists(), f"script.jinja2 not found at {script_path}"

        content = script_path.read_text()
        assert 'The visual suggestions are ready' in content

    def test_script_explains_machine_generated_message(self):
        """The template must explain this is a machine-generated message."""
        script_path = Path(__file__).parent.parent / "voice" / "script.jinja2"
        content = script_path.read_text()
        assert "machine generated message" in content

    def test_script_instructs_to_tell_user_suggestions_visible(self):
        """The template must instruct the model to tell the user suggestions are visible."""
        script_path = Path(__file__).parent.parent / "voice" / "script.jinja2"
        content = script_path.read_text()
        assert "see them on their screen" in content

    def test_script_uses_customer_variable(self):
        """The template must use the {{customer}} Jinja2 variable."""
        script_path = Path(__file__).parent.parent / "voice" / "script.jinja2"
        content = script_path.read_text()
        assert "{{customer}}" in content

    def test_script_renders_with_jinja2(self):
        """The template should render without errors when given required context."""
        from jinja2 import Environment, FileSystemLoader

        voice_dir = Path(__file__).parent.parent / "voice"
        env = Environment(loader=FileSystemLoader(str(voice_dir)))
        template = env.get_template("script.jinja2")

        rendered = template.render(
            customer="Brad",
            purchases=[],
            context=[],
            products=[],
        )

        assert "Brad" in rendered
        assert "The visual suggestions are ready" in rendered
        assert len(rendered) > 100  # Sanity check - not empty


# ---------------------------------------------------------------------------
# 5. Writeup prompty template validation
# ---------------------------------------------------------------------------

class TestWriteupPrompty:
    """Tests that the writeup.prompty detection template exists and contains
    the expected rubric elements.
    """

    def test_writeup_prompty_exists(self):
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        assert prompty_path.exists()

    def test_writeup_contains_detection_phrases(self):
        """The prompt must look for visual request phrases."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        assert "write up" in content.lower()
        assert "visual description" in content.lower()
        assert "show me" in content.lower()

    def test_writeup_requires_both_user_and_assistant(self):
        """The prompt must require both user request AND assistant acknowledgment."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        assert "assistant echoes that back" in content or "assistant echo" in content

    def test_writeup_returns_yes_or_no(self):
        """The prompt must instruct the LLM to respond with YES or NO."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        assert '"YES"' in content
        assert '"NO"' in content


# ---------------------------------------------------------------------------
# 6. Suggestions prompty template validation
# ---------------------------------------------------------------------------

class TestSuggestionsPrompty:
    """Tests that the suggestions.prompty generation template exists and
    contains the expected elements for product recommendation generation.
    """

    def test_suggestions_prompty_exists(self):
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        assert prompty_path.exists()

    def test_suggestions_uses_photo_url(self):
        """The prompt must reference PhotoUrl for product images."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        content = prompty_path.read_text()
        assert "PhotoUrl" in content

    def test_suggestions_instructs_exact_image_urls(self):
        """The prompt must instruct to use exact image URLs, not invented domains."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        content = prompty_path.read_text()
        assert "DO NOT ALTER THE IMAGE URL" in content or "exact URL" in content.lower()

    def test_suggestions_includes_product_template(self):
        """The prompt must include a template for product information."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        content = prompty_path.read_text()
        assert "ManufacturerProductNumber" in content
        assert "Description" in content
        assert "UnitPrice" in content

    def test_suggestions_includes_purchases_section(self):
        """The prompt must include customer purchase history."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        content = prompty_path.read_text()
        assert "purchases" in content.lower()
        assert "{{customer}}" in content


# ---------------------------------------------------------------------------
# 7. Backend notification routing - "text" type processes suggestions-ready
#    message correctly (Task 67)
# ---------------------------------------------------------------------------

class TestSuggestionsReadyNotificationRouting:
    """Tests that the exact synthetic notification message from the frontend
    ('The visual suggestions are ready') is correctly routed through the
    backend's receive_client() 'text' case.

    The notification loop is:
      1. Frontend sends: {type: "text", payload: "The visual suggestions are ready"}
      2. Backend receive_client case "text" creates conversation.item.create + response.create
      3. Backend reads script.jinja2 instruction and responds to the user
      4. response.text.done forwards {type: "assistant", payload: ...} back to frontend

    These tests validate step 2 specifically.
    """

    @pytest.mark.asyncio
    async def test_suggestions_ready_message_creates_conversation_item(self):
        """The exact 'suggestions ready' notification should create a
        conversation item with the notification text as input_text content."""
        client = _make_realtime_client()

        # This is the exact message the frontend sends (chat.tsx:114-117)
        notification_msg = json.dumps({
            "type": "text",
            "payload": "The visual suggestions are ready"
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[notification_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        # Should have sent two events via realtime.send:
        # 1) conversation.item.create  2) response.create
        send_calls = client.realtime.send.call_args_list
        assert len(send_calls) == 2

        # First: conversation.item.create with the exact notification text
        first_event = send_calls[0][0][0]
        assert first_event.type == "conversation.item.create"
        assert first_event.item.role == "user"
        assert first_event.item.content[0].type == "input_text"
        assert first_event.item.content[0].text == "The visual suggestions are ready"

    @pytest.mark.asyncio
    async def test_suggestions_ready_triggers_text_only_response(self):
        """The notification triggers a response.create with modalities=['text'],
        ensuring the model responds with text (not audio) to the machine-generated
        notification."""
        client = _make_realtime_client()

        notification_msg = json.dumps({
            "type": "text",
            "payload": "The visual suggestions are ready"
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[notification_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        send_calls = client.realtime.send.call_args_list
        # Second call should be response.create with text-only modalities
        second_event = send_calls[1][0][0]
        assert second_event.type == "response.create"
        # The response should specify text-only modalities.
        # The SDK wraps the dict as a Response object with a modalities field.
        assert second_event.response.modalities == ["text"]

    @pytest.mark.asyncio
    async def test_suggestions_ready_sets_microphone_inactive(self):
        """The 'text' message type sets microphone_active to False, which
        ensures subsequent function call responses also use text-only mode."""
        client = _make_realtime_client()
        client.microphone_active = True  # Simulate mic was active

        notification_msg = json.dumps({
            "type": "text",
            "payload": "The visual suggestions are ready"
        })

        from fastapi import WebSocketDisconnect
        client.client.receive_text = AsyncMock(
            side_effect=[notification_msg, WebSocketDisconnect()]
        )

        await client.receive_client()

        # The "text" case in receive_client sets self.microphone_active = False
        assert client.microphone_active is False

    def test_frontend_backend_notification_phrase_agreement(self):
        """Verify that the frontend notification phrase exactly matches
        what the backend script.jinja2 template expects to handle.

        Frontend (chat.tsx:116): "The visual suggestions are ready"
        Backend (script.jinja2:83): "The visual suggestions are ready"
        """
        script_path = Path(__file__).parent.parent / "voice" / "script.jinja2"
        content = script_path.read_text()

        # The exact phrase the frontend sends (no trailing period)
        frontend_phrase = "The visual suggestions are ready"

        # The script must contain this exact phrase for the model to handle it
        assert frontend_phrase in content, (
            f"script.jinja2 does not contain the exact frontend phrase: "
            f"{frontend_phrase!r}"
        )

    def test_text_type_is_valid_in_backend_message_model(self):
        """The 'text' type must be a valid literal in the backend Message model."""
        msg = Message(type="text", payload="The visual suggestions are ready")
        assert msg.type == "text"
        assert msg.payload == "The visual suggestions are ready"


# ---------------------------------------------------------------------------
# 8. /api/suggestion endpoint - StreamingResponse validation (Task 64)
# ---------------------------------------------------------------------------

@requires_app
class TestSuggestionEndpoint:
    """Tests that the /api/suggestion endpoint is correctly wired:
    - Accepts POST with {customer: str, messages: SimpleMessage[]}
    - Returns StreamingResponse with text/event-stream media type
    - Streams chunks produced by create_suggestion()

    These tests require the Azure SDK since main.py imports session -> chat
    -> prompty.azure. They are skipped when the SDK is absent.
    """

    def test_endpoint_returns_streaming_response_with_event_stream(self):
        """POST /api/suggestion returns 200 with text/event-stream content type."""
        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            async def mock_stream():
                yield "chunk1"
                yield "chunk2"

            mock_exec.return_value = mock_stream()

            client = TestClient(_fastapi_app)
            response = client.post(
                "/api/suggestion",
                json={
                    "customer": "Brad",
                    "messages": [
                        {"name": "user", "text": "Show me those products"},
                        {"name": "assistant", "text": "Sure, here is a visual writeup!"},
                    ],
                },
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

    def test_endpoint_streams_chunks_from_create_suggestion(self):
        """POST /api/suggestion response body contains the chunks yielded by
        create_suggestion()."""
        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            async def mock_stream():
                for chunk in ["# Title\n", "Body text", "\n**bold**"]:
                    yield chunk

            mock_exec.return_value = mock_stream()

            client = TestClient(_fastapi_app)
            response = client.post(
                "/api/suggestion",
                json={
                    "customer": "TestUser",
                    "messages": [{"name": "user", "text": "Show products"}],
                },
            )

            assert response.status_code == 200
            body = response.text
            assert "# Title\n" in body
            assert "Body text" in body
            assert "**bold**" in body

    def test_endpoint_rejects_missing_customer_field(self):
        """POST /api/suggestion without 'customer' returns 422 validation error."""
        client = TestClient(_fastapi_app)
        response = client.post(
            "/api/suggestion",
            json={
                "messages": [{"name": "user", "text": "test"}],
            },
        )

        assert response.status_code == 422

    def test_endpoint_rejects_missing_messages_field(self):
        """POST /api/suggestion without 'messages' returns 422 validation error."""
        client = TestClient(_fastapi_app)
        response = client.post(
            "/api/suggestion",
            json={
                "customer": "Brad",
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 9. Suggestions prompty - plain text image URL format (Task 64)
#    Azure OpenAI has a 50-image limit per request. Using markdown image
#    syntax ![](url) in the prompt template causes the model to count each
#    product image as a vision input image, quickly hitting the limit.
#    The template MUST use plain text "Image URL: <url>" instead.
# ---------------------------------------------------------------------------

class TestSuggestionsPromptyImageFormat:
    """Validates that suggestions.prompty uses plain text Image URL references
    rather than markdown image syntax, which would hit Azure's 50-image limit.
    """

    def test_uses_plain_text_image_url_format(self):
        """The template must use 'Image URL: {{product.PhotoUrl}}' (plain text),
        not markdown image syntax like '![]({{product.PhotoUrl}})'."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        content = prompty_path.read_text()

        # Must contain the plain text format
        assert "Image URL: {{product.PhotoUrl}}" in content, (
            "suggestions.prompty must use 'Image URL: {{product.PhotoUrl}}' format"
        )

    def test_does_not_use_markdown_image_syntax(self):
        """The template must NOT contain markdown image syntax ![...](...)
        which causes Azure to count each product photo as a vision image."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        content = prompty_path.read_text()

        # Regex matches markdown image syntax: ![alt text](url)
        markdown_images = re.findall(r'!\[.*?\]\(.*?\)', content)
        assert len(markdown_images) == 0, (
            f"suggestions.prompty must NOT use markdown image syntax. "
            f"Found: {markdown_images}. Use plain text 'Image URL: ...' instead "
            f"to avoid Azure's 50-image-per-request limit."
        )

    def test_photo_url_is_conditional(self):
        """The PhotoUrl template should be inside an {% if %} block so products
        without images do not produce empty Image URL lines."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "suggestions.prompty"
        content = prompty_path.read_text()

        assert "{% if product.PhotoUrl %}" in content, (
            "PhotoUrl rendering should be conditional with {% if product.PhotoUrl %}"
        )


# ---------------------------------------------------------------------------
# 10. Product and purchase data file validation (Task 64)
# ---------------------------------------------------------------------------

class TestProductDataFiles:
    """Validates that the product and purchase JSON data files used by the
    suggestions pipeline exist and contain valid, well-structured data.
    """

    def test_api_products_json_exists_and_is_valid(self):
        """api/products.json must exist and be valid JSON."""
        products_path = Path(__file__).parent.parent / "products.json"
        assert products_path.exists(), "api/products.json not found"

        data = json.loads(products_path.read_text())
        assert isinstance(data, list)
        assert len(data) > 0, "products.json must contain at least one product"

    def test_api_purchases_json_exists_and_is_valid(self):
        """api/purchases.json must exist and be valid JSON."""
        purchases_path = Path(__file__).parent.parent / "purchases.json"
        assert purchases_path.exists(), "api/purchases.json not found"

        data = json.loads(purchases_path.read_text())
        assert isinstance(data, list)
        assert len(data) > 0, "purchases.json must contain at least one purchase"

    def test_suggestions_products_json_exists_and_is_valid(self):
        """api/suggestions/products.json must exist and be valid JSON."""
        products_path = Path(__file__).parent.parent / "suggestions" / "products.json"
        assert products_path.exists(), "suggestions/products.json not found"

        data = json.loads(products_path.read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_suggestions_purchases_json_exists_and_is_valid(self):
        """api/suggestions/purchases.json must exist and be valid JSON."""
        purchases_path = Path(__file__).parent.parent / "suggestions" / "purchases.json"
        assert purchases_path.exists(), "suggestions/purchases.json not found"

        data = json.loads(purchases_path.read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_products_have_expected_fields(self):
        """Each product must have the core fields used by suggestions.prompty."""
        products_path = Path(__file__).parent.parent / "products.json"
        data = json.loads(products_path.read_text())

        required_fields = [
            "ManufacturerProductNumber",
            "Description",
            "Manufacturer",
            "UnitPrice",
        ]

        for i, product in enumerate(data):
            for field in required_fields:
                assert field in product, (
                    f"Product at index {i} missing required field '{field}'"
                )
            # Description must have nested fields
            assert "ProductDescription" in product["Description"], (
                f"Product at index {i} missing Description.ProductDescription"
            )
            # Manufacturer must have Name
            assert "Name" in product["Manufacturer"], (
                f"Product at index {i} missing Manufacturer.Name"
            )

    def test_products_have_photo_urls(self):
        """At least some products should have PhotoUrl for image rendering."""
        products_path = Path(__file__).parent.parent / "products.json"
        data = json.loads(products_path.read_text())

        products_with_photos = [p for p in data if p.get("PhotoUrl")]
        assert len(products_with_photos) > 0, (
            "At least one product must have a PhotoUrl for image rendering"
        )


# ---------------------------------------------------------------------------
# 11. POST /api/request endpoint tests (Task 63)
# ---------------------------------------------------------------------------

@requires_app
class TestApiRequestEndpoint:
    """Tests for the POST /api/request endpoint.

    This endpoint accepts a JSON array of SimpleMessage objects and returns
    {"requested": bool} indicating whether the user is asking for visual
    product suggestions.  It delegates to suggestion_requested() and catches
    exceptions to return {"requested": false} on error.
    """

    def test_returns_requested_true_when_suggestion_detected(self):
        """POST /api/request returns {"requested": true} when
        suggestion_requested() determines a visual request is present."""
        with patch("main.suggestion_requested", new_callable=AsyncMock) as mock_sr:
            mock_sr.return_value = True
            client = TestClient(_fastapi_app)
            response = client.post("/api/request", json=[
                {"name": "user", "text": "Can you show this to me visually?"},
                {"name": "assistant", "text": "Sure, I can prepare a visual writeup!"},
            ])

        assert response.status_code == 200
        body = response.json()
        assert body == {"requested": True}

    def test_returns_requested_false_for_general_conversation(self):
        """POST /api/request returns {"requested": false} for ordinary
        conversation that does not include a visual request."""
        with patch("main.suggestion_requested", new_callable=AsyncMock) as mock_sr:
            mock_sr.return_value = False
            client = TestClient(_fastapi_app)
            response = client.post("/api/request", json=[
                {"name": "user", "text": "What resistors do you carry?"},
                {"name": "assistant", "text": "We carry a wide range of resistors."},
            ])

        assert response.status_code == 200
        body = response.json()
        assert body == {"requested": False}

    def test_accepts_simple_message_list_body(self):
        """POST /api/request accepts a JSON array of {name, text} objects
        and passes parsed SimpleMessage instances to suggestion_requested()."""
        with patch("main.suggestion_requested", new_callable=AsyncMock) as mock_sr:
            mock_sr.return_value = False
            client = TestClient(_fastapi_app)
            response = client.post("/api/request", json=[
                {"name": "user", "text": "Hello"},
            ])

        assert response.status_code == 200
        # Verify the function was called with parsed SimpleMessage objects
        mock_sr.assert_called_once()
        call_args = mock_sr.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0].name == "user"
        assert call_args[0].text == "Hello"

    def test_returns_false_on_exception(self):
        """POST /api/request returns {"requested": false} when
        suggestion_requested() raises an exception, ensuring the suggestion
        panel does not appear on backend errors."""
        with patch("main.suggestion_requested", new_callable=AsyncMock) as mock_sr:
            mock_sr.side_effect = RuntimeError("Azure connection failed")
            client = TestClient(_fastapi_app)
            response = client.post("/api/request", json=[
                {"name": "user", "text": "Show me products"},
                {"name": "assistant", "text": "Sure!"},
            ])

        assert response.status_code == 200
        body = response.json()
        assert body == {"requested": False}

    def test_rejects_invalid_body(self):
        """POST /api/request returns 422 for an invalid request body
        (object instead of array)."""
        client = TestClient(_fastapi_app)
        response = client.post("/api/request", json={"invalid": "body"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# 12. Writeup prompty - additional detection phrase validation (Task 63)
# ---------------------------------------------------------------------------

class TestWriteupPromptyDetectionPhrases:
    """Additional validation of the writeup.prompty detection template,
    focusing on the specific trigger phrase, examples, and Jinja2 structure.
    """

    def test_writeup_contains_show_visually_trigger(self):
        """The prompt must contain the exact trigger phrase
        'can you show this to me visually'."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        assert "can you show this to me visually" in content.lower()

    def test_writeup_contains_yes_example(self):
        """The prompt must include at least one example where the correct
        answer is YES (user asks AND assistant echoes)."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        # Example 2 shows a YES case
        assert "Example 2" in content
        assert 'The correct response would be "YES"' in content

    def test_writeup_contains_no_example_user_only(self):
        """The prompt must include an example where the user asks but the
        assistant does NOT echo, resulting in NO."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        # Example 3 shows this case
        assert "Example 3" in content
        assert "the assistant does not" in content.lower()

    def test_writeup_uses_jinja2_context_loop(self):
        """The prompt must iterate over context messages using Jinja2 syntax."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        assert "{% for item in context %}" in content
        assert "{{item.name}}" in content
        assert "{{item.text}}" in content

    def test_writeup_instructs_100_percent_certainty(self):
        """The prompt must instruct the LLM to be 100% sure before answering YES."""
        prompty_path = Path(__file__).parent.parent / "suggestions" / "writeup.prompty"
        content = prompty_path.read_text()
        assert "100%" in content


# ---------------------------------------------------------------------------
# 13. suggestion_requested() parsing edge cases (Task 63)
# ---------------------------------------------------------------------------

@requires_suggestions
class TestSuggestionRequestedParsingEdgeCases:
    """Edge-case tests for the result.lower().startswith('y') parsing logic
    in suggestion_requested().

    The implementation uses `result.lower().startswith('y')` which means any
    response starting with 'y' (case-insensitive) returns True, and anything
    else returns False.
    """

    @pytest.mark.asyncio
    async def test_returns_true_for_yes_with_explanation(self):
        """suggestion_requested() returns True when LLM says 'Yes, the user
        is asking for a visual writeup.'"""
        messages = [SimpleMessage(name="user", text="show me")]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "Yes, the user is asking for a visual writeup."
            result = await suggestion_requested(messages)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_empty_response(self):
        """suggestion_requested() returns False for an empty LLM response."""
        messages = [SimpleMessage(name="user", text="hello")]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = ""
            result = await suggestion_requested(messages)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_whitespace_response(self):
        """suggestion_requested() returns False for a whitespace-only response."""
        messages = [SimpleMessage(name="user", text="hello")]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "   "
            result = await suggestion_requested(messages)

        assert result is False

    @pytest.mark.asyncio
    async def test_handles_single_message_list(self):
        """suggestion_requested() works with a single-message conversation."""
        messages = [SimpleMessage(name="user", text="Show me products visually")]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "NO"
            result = await suggestion_requested(messages)

        assert result is False
        # Verify single message was passed correctly
        call_kwargs = mock_exec.call_args
        inputs = call_kwargs.kwargs.get("inputs") or call_kwargs[1].get("inputs")
        assert len(inputs["context"]) == 1

    @pytest.mark.asyncio
    async def test_uses_writeup_prompty_not_suggestions_prompty(self):
        """suggestion_requested() must call prompty with the writeup template,
        not the suggestions template."""
        messages = [SimpleMessage(name="user", text="test")]

        with patch("suggestions.prompty.execute_async", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "NO"
            await suggestion_requested(messages)

        # The first positional argument should be the writeup prompty object
        call_args = mock_exec.call_args
        first_arg = call_args[0][0]
        # The writeup_prompty is loaded at module level in suggestions/__init__.py
        from suggestions import writeup_prompty
        assert first_arg is writeup_prompty
