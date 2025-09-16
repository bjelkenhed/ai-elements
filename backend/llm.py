"""
Simplified LLM client for calling completion APIs.
"""

import asyncio
from typing import List, Dict, Any, Optional, Union, AsyncGenerator

from openai import OpenAI
from pydantic import BaseModel

from messages import Messages
from utils.tools_utils import langchain_tools_to_openai_format
from utils.config_utils import get_llm_config


class LLMError(Exception):
    """Exception raised when there's an error calling the LLM API."""

    pass


class StreamEvent(BaseModel):
    """Base class for streaming events."""

    event_type: str


class TextDelta(StreamEvent):
    """Incremental text content from the model."""

    content: str
    event_type: str = "text_delta"


class ToolCallStart(StreamEvent):
    """Tool call initiation event."""

    tool_call_id: str
    tool_name: str
    event_type: str = "tool_call_start"


class ToolCallDelta(StreamEvent):
    """Incremental tool call arguments."""

    tool_call_id: str
    arguments_delta: str
    event_type: str = "tool_call_delta"


class ToolCallComplete(StreamEvent):
    """Tool call completion event."""

    tool_call_id: str
    tool_name: str
    arguments: str
    event_type: str = "tool_call_complete"


class ResponseComplete(StreamEvent):
    """Response completion event with metadata."""

    finish_reason: str
    usage: Optional[Dict[str, Any]] = None
    event_type: str = "response_complete"


class StreamingResponseParser:
    """Parser for OpenAI streaming response chunks."""

    def __init__(self):
        self.tool_calls: Dict[str, Dict[str, Any]] = {}
        self.content_buffer = ""

    def parse_chunk(self, chunk) -> List[StreamEvent]:
        """Parse a single streaming chunk into events."""
        events: List[StreamEvent] = []

        if not chunk or not hasattr(chunk, "choices") or not chunk.choices:
            return events

        choice = chunk.choices[0]

        if not hasattr(choice, "delta"):
            return events

        delta = choice.delta

        # Handle text content
        if hasattr(delta, "content") and delta.content:
            events.append(TextDelta(content=delta.content))
            self.content_buffer += delta.content

        # Handle tool calls
        if hasattr(delta, "tool_calls") and delta.tool_calls:
            for tool_call in delta.tool_calls:
                # Safely get tool call ID
                tool_call_id = getattr(tool_call, "id", None)
                if not tool_call_id:
                    continue

                # Initialize tool call if new
                if tool_call_id not in self.tool_calls:
                    self.tool_calls[tool_call_id] = {"name": "", "arguments": ""}

                # Handle function name (usually in first chunk for this tool call)
                if (
                    hasattr(tool_call, "function")
                    and tool_call.function
                    and hasattr(tool_call.function, "name")
                    and tool_call.function.name
                ):
                    tool_name = tool_call.function.name
                    self.tool_calls[tool_call_id]["name"] = tool_name
                    events.append(
                        ToolCallStart(tool_call_id=tool_call_id, tool_name=tool_name)
                    )

                # Handle function arguments
                if (
                    hasattr(tool_call, "function")
                    and tool_call.function
                    and hasattr(tool_call.function, "arguments")
                    and tool_call.function.arguments
                ):
                    args_delta = tool_call.function.arguments
                    self.tool_calls[tool_call_id]["arguments"] += args_delta

                    # Only generate delta events if we actually have arguments
                    if args_delta:
                        # Generate synthetic deltas to match AI Gateway behavior
                        # Split the arguments into character-by-character deltas for streaming
                        for char in args_delta:
                            events.append(
                                ToolCallDelta(
                                    tool_call_id=tool_call_id, arguments_delta=char
                                )
                            )

        # Handle completion
        if hasattr(choice, "finish_reason") and choice.finish_reason:
            # Generate tool call completion events
            for tool_call_id, tool_data in self.tool_calls.items():
                if tool_data["name"]:  # Only emit if we have a valid tool name
                    events.append(
                        ToolCallComplete(
                            tool_call_id=tool_call_id,
                            tool_name=tool_data["name"],
                            arguments=tool_data["arguments"],
                        )
                    )

            # Generate response completion event
            usage = getattr(chunk, "usage", None)
            usage_dict = None
            if usage:
                try:
                    usage_dict = (
                        usage.model_dump()
                        if hasattr(usage, "model_dump")
                        else dict(usage)
                    )
                except (AttributeError, TypeError, ValueError):
                    usage_dict = None

            events.append(
                ResponseComplete(finish_reason=choice.finish_reason, usage=usage_dict)
            )

        return events


async def call_llm_stream(
    messages: Union[Messages, List[Dict[str, Any]]],
    tools: Optional[Union[List[Dict[str, Any]], List]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Call an LLM completion API with streaming enabled.

    Args:
        messages: Either a Messages instance or a list of message dicts
        tools: Optional list of tools in OpenAI function calling format or LangChain StructuredTools
        api_key: OpenAI API key (if not provided, loads from .env OPENAI_API_KEY)
        model: Model name to use for completion
        base_url: Base URL for the API (useful for VLLM or other OpenAI-compatible servers)
        **kwargs: Additional parameters to pass to OpenAI API

    Yields:
        StreamEvent: Streaming events (TextDelta, ToolCallStart, ToolCallDelta, etc.)

    Raises:
        LLMError: If API call fails or configuration is invalid
    """
    # Get configuration from environment and parameters
    try:
        config = get_llm_config(api_key=api_key, model=model, base_url=base_url)
        api_key = config["api_key"]
        model = config["model"]
        base_url = config["base_url"]
    except ValueError as e:
        raise LLMError(str(e))

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key, base_url=base_url)

    # Handle different message input types
    if isinstance(messages, Messages):
        conversation_messages = messages.get_messages()
    else:
        conversation_messages = messages

    if not conversation_messages:
        raise LLMError("No messages provided for completion.")

    # Handle tools parameter - convert LangChain tools if needed
    openai_tools = None
    if tools:
        # Check if it's a list of LangChain StructuredTools
        if tools and hasattr(tools[0], "args_schema"):
            openai_tools = langchain_tools_to_openai_format(tools)
        else:
            openai_tools = tools

    try:
        # Prepare completion parameters
        completion_params = {
            "model": model,
            "messages": conversation_messages,
            "stream": True,
            **kwargs,
        }

        if openai_tools:
            completion_params["tools"] = openai_tools
            completion_params["tool_choice"] = "auto"

        # Make streaming completion request
        stream = client.chat.completions.create(**completion_params)

        # Initialize parser
        parser = StreamingResponseParser()

        # Process streaming response
        for chunk in stream:
            events = parser.parse_chunk(chunk)
            for event in events:
                yield event

    except Exception as e:
        raise LLMError(f"Failed to call streaming LLM API: {e}")


async def example_usage():
    """Example of how to use the call_llm_stream function."""
    # Example 1: Using with Messages object
    messages_obj = Messages(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is the capital of France?",
    )

    # Example 2: Using with raw message list
    messages_list = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
    ]

    # Example tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City and state, e.g. San Francisco, CA",
                        }
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    try:
        # Streaming call with Messages object
        print("Using Messages object (streaming):")
        async for event in call_llm_stream(messages_obj, temperature=0.7):
            if event.event_type == "text_delta":
                print(event.content, end="", flush=True)
            elif event.event_type == "response_complete":
                print(f"\nFinish reason: {event.finish_reason}")

        # Streaming call with raw message list
        print("\nUsing raw message list with tools (streaming):")
        async for event in call_llm_stream(messages_list, tools=tools, temperature=0.5):
            if event.event_type == "text_delta":
                print(event.content, end="", flush=True)
            elif event.event_type == "tool_call_start":
                print(
                    f"\nTool call started: {event.tool_name} (ID: {event.tool_call_id})"
                )
            elif event.event_type == "tool_call_delta":
                print(event.arguments_delta, end="", flush=True)
            elif event.event_type == "tool_call_complete":
                print(
                    f"\nTool call complete: {event.tool_name} with args: {event.arguments}"
                )
            elif event.event_type == "response_complete":
                print(f"\nFinish reason: {event.finish_reason}")

    except LLMError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())
