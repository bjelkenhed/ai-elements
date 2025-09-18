# LLM Module Usage Guide

The `agentic_blocks.llm` module provides a unified interface for calling language models with support for streaming, tool calls, and reasoning content. All functions return the same `LLMResponse` object for consistent usage.

## Quick Start

```python
from agentic_blocks import call_llm, call_llm_stream, Messages

# Create messages
messages = Messages()
messages.add_user_message("What is the capital of France?")

# Simple call
response = call_llm(messages)
print(response.content())  # "The capital of France is Paris."

# Streaming call
response = await call_llm_stream(messages)
async for event in response.stream():
    if event.event_type == "text_delta":
        print(event.content, end="", flush=True)
```

## Core Functions

### `call_llm(messages, tools=None, **kwargs) -> LLMResponse`
- **Use case**: Simple, synchronous calls when you need the complete response
- **Best for**: Non-real-time applications, batch processing, simple Q&A

### `call_llm_stream_basic(messages, tools=None, **kwargs) -> LLMResponse`
- **Use case**: Streaming with basic tool call support (may be incomplete)
- **Best for**: Text-heavy responses where tool calls are secondary
- **Note**: Tool calls may be truncated in some edge cases

### `call_llm_stream(messages, tools=None, enable_fallback=True, **kwargs) -> LLMResponse`
- **Use case**: Streaming with robust tool call support via automatic fallback
- **Best for**: Production applications requiring reliable tool calls
- **Features**: Automatically retries with non-streaming if tool calls fail

## The LLMResponse Object

All functions return a `LLMResponse` object with these key methods:

### Content Access
```python
# Synchronous access
content = response.content()           # Complete text content
tool_calls = response.tool_calls()     # List of tool calls
reasoning = response.reasoning()       # Model reasoning (streaming only)

# Asynchronous access
content = await response.content_async()
tool_calls = await response.tool_calls_async()
reasoning = await response.reasoning_async()
```

### Streaming Events
```python
async for event in response.stream():
    # Process events in real-time
    print(f"Event: {event.event_type}")
```

### Properties
```python
if response.is_streaming:
    print("Using streaming response")
else:
    print("Used fallback to non-streaming")
```

## Streaming Events Reference

The `response.stream()` method yields different event types:

### TextDelta
Incremental text content from the model.
```python
if event.event_type == "text_delta":
    text_chunk = event.content  # string
    print(text_chunk, end="", flush=True)
```

### ReasoningDelta
Incremental reasoning/thinking content (thinking models only).
```python
if event.event_type == "reasoning_delta":
    reasoning_chunk = event.reasoning  # string
    print(f"Thinking: {reasoning_chunk}")
```

### ToolCallStart
Indicates a tool call has begun.
```python
if event.event_type == "tool_call_start":
    call_id = event.tool_call_id    # string
    tool_name = event.tool_name     # string
    print(f"Starting {tool_name} call...")
```

### ToolCallDelta
Incremental tool call arguments (character by character).
```python
if event.event_type == "tool_call_delta":
    call_id = event.tool_call_id        # string
    args_chunk = event.arguments_delta  # string
    # Usually used for real-time display
```

### ToolCallComplete
Tool call is complete with full arguments.
```python
if event.event_type == "tool_call_complete":
    call_id = event.tool_call_id    # string
    tool_name = event.tool_name     # string
    arguments = event.arguments     # JSON string

    # Parse and execute
    import json
    args_dict = json.loads(arguments)
    result = execute_tool(tool_name, args_dict)
```

### ResponseComplete
Indicates the response is finished.
```python
if event.event_type == "response_complete":
    finish_reason = event.finish_reason  # "stop", "length", etc.
    usage = event.usage                  # Token usage dict (optional)
    print(f"Finished: {finish_reason}")
```

## Tool Calls Handling

### Basic Tool Call Processing
```python
import json

# Define tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    }
]

# Make request
messages = Messages()
messages.add_user_message("What's the weather in Paris?")

response = await call_llm_stream(messages, tools=tools)
tool_calls = await response.tool_calls_async()

if tool_calls:
    for call in tool_calls:
        function_name = call.function.name
        arguments = json.loads(call.function.arguments)

        print(f"Calling {function_name} with {arguments}")

        # Execute your function
        if function_name == "get_weather":
            result = get_weather(arguments["location"])

            # Add result back to conversation
            messages.add_tool_response(call.id, str(result))
```

### Real-time Tool Call Processing
```python
async def process_streaming_with_tools(messages, tools):
    response = await call_llm_stream(messages, tools=tools)

    # Track tool calls as they stream
    active_calls = {}

    async for event in response.stream():
        if event.event_type == "text_delta":
            print(event.content, end="", flush=True)

        elif event.event_type == "tool_call_start":
            active_calls[event.tool_call_id] = {
                "name": event.tool_name,
                "arguments": ""
            }
            print(f"\n[Starting {event.tool_name}...]")

        elif event.event_type == "tool_call_complete":
            call_data = active_calls[event.tool_call_id]
            arguments = json.loads(event.arguments)

            print(f"\n[Executing {event.tool_name}({arguments})]")

            # Execute the tool
            result = execute_tool(event.tool_name, arguments)
            print(f"[Result: {result}]")

        elif event.event_type == "response_complete":
            print(f"\n[Finished: {event.finish_reason}]")
```

## Advanced Usage Patterns

### Handling Different Response Types
```python
async def handle_llm_response(messages, tools=None):
    response = await call_llm_stream(messages, tools=tools)

    # Check what type of response we got
    content = await response.content_async()
    tool_calls = await response.tool_calls_async()
    reasoning = await response.reasoning_async()

    if tool_calls:
        print(f"Model wants to call {len(tool_calls)} tools")
        for call in tool_calls:
            # Handle tool calls
            pass
    elif content:
        print(f"Model responded with text: {content}")

    if reasoning:
        print(f"Model reasoning: {reasoning}")
```

### Streaming with Buffering
```python
async def stream_with_buffering(messages):
    response = await call_llm_stream(messages)

    text_buffer = ""

    async for event in response.stream():
        if event.event_type == "text_delta":
            text_buffer += event.content

            # Send chunks when we have enough content
            if len(text_buffer) > 50:  # 50 characters
                yield text_buffer
                text_buffer = ""

        elif event.event_type == "response_complete":
            # Send remaining buffer
            if text_buffer:
                yield text_buffer
```

### Error Handling and Retry Logic
```python
from agentic_blocks.llm import LLMError

async def robust_llm_call(messages, tools=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = await call_llm_stream(
                messages,
                tools=tools,
                enable_fallback=True  # Enable automatic fallback
            )

            # Check if we got what we expected
            if tools:
                tool_calls = await response.tool_calls_async()
                if response.is_streaming:
                    print("✅ Streaming succeeded")
                else:
                    print("⚠️  Used fallback (streaming failed)")

            return response

        except LLMError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

## Configuration

### Environment Variables
```bash
# Required
OPENAI_API_KEY=your_api_key_here

# Optional
OPENAI_MODEL=gpt-4o
OPENAI_BASE_URL=https://api.openai.com/v1
```

### Per-call Configuration
```python
response = await call_llm_stream(
    messages,
    api_key="your_key",           # Override API key
    model="gpt-4o",               # Override model
    base_url="https://...",       # Override base URL
    temperature=0.7,              # OpenAI parameters
    max_tokens=1000,
    tools=tools
)
```

## Best Practices

### 1. Use Appropriate Function for Your Use Case
- **Simple Q&A**: `call_llm()`
- **Real-time streaming**: `call_llm_stream_basic()`
- **Production tool calls**: `call_llm_stream()` with fallback

### 2. Handle Both Content and Tool Calls
```python
response = await call_llm_stream(messages, tools=tools)

# Always check both
content = await response.content_async()
tool_calls = await response.tool_calls_async()

if tool_calls:
    # Handle function calls
    pass
elif content:
    # Handle text response
    pass
```

### 3. Process Streaming Events Efficiently
```python
# Good: Process events as they arrive
async for event in response.stream():
    if event.event_type == "text_delta":
        yield event.content  # Forward immediately

# Avoid: Collecting all events first
events = []
async for event in response.stream():  # Don't do this
    events.append(event)
```

### 4. Use Fallback for Reliable Tool Calls
```python
# Production: Enable fallback for reliability
response = await call_llm_stream(messages, tools=tools, enable_fallback=True)

# Development: Disable to test streaming robustness
response = await call_llm_stream(messages, tools=tools, enable_fallback=False)
```

### 5. Handle Errors Gracefully
```python
try:
    response = await call_llm_stream(messages)
    content = await response.content_async()
except LLMError as e:
    print(f"LLM call failed: {e}")
    # Implement fallback behavior
```