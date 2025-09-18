# Streaming Events Reference

The `LLMResponse.stream()` method provides real-time access to events as they arrive from the language model. This is essential for building responsive user interfaces and processing model output incrementally.

## Event Types Overview

All streaming events inherit from `StreamEvent` and have an `event_type` field that identifies the event type:

| Event Type | Purpose | Key Fields |
|------------|---------|------------|
| `TextDelta` | Incremental text content | `content` |
| `ReasoningDelta` | Incremental reasoning/thinking | `reasoning` |
| `ToolCallStart` | Tool call begins | `tool_call_id`, `tool_name` |
| `ToolCallDelta` | Tool arguments streaming | `tool_call_id`, `arguments_delta` |
| `ToolCallComplete` | Tool call complete | `tool_call_id`, `tool_name`, `arguments` |
| `ResponseComplete` | Response finished | `finish_reason`, `usage` |

## Event Details

### TextDelta
**Purpose**: Delivers incremental text content as the model generates it.

**Fields**:
- `event_type`: `"text_delta"`
- `content`: `str` - The incremental text chunk

**Example**:
```python
async for event in response.stream():
    if event.event_type == "text_delta":
        print(event.content, end="", flush=True)  # Stream to console
        # Or buffer: text_buffer += event.content
```

**Common Use Cases**:
- Real-time text display in chat interfaces
- Progressive text streaming to web clients
- Building complete responses incrementally

### ReasoningDelta
**Purpose**: Provides access to the model's internal reasoning process (thinking models only).

**Fields**:
- `event_type`: `"reasoning_delta"`
- `reasoning`: `str` - The incremental reasoning content

**Example**:
```python
reasoning_buffer = ""

async for event in response.stream():
    if event.event_type == "reasoning_delta":
        reasoning_buffer += event.reasoning
        print(f"Thinking: {event.reasoning}", end="")
    elif event.event_type == "text_delta":
        print(f"\nResponse: {event.content}", end="")
```

**Common Use Cases**:
- Debugging model decision-making
- Showing "thinking" indicators in UIs
- Understanding model reasoning patterns

### ToolCallStart
**Purpose**: Indicates that the model has begun making a function call.

**Fields**:
- `event_type`: `"tool_call_start"`
- `tool_call_id`: `str` - Unique identifier for this tool call
- `tool_name`: `str` - Name of the function being called

**Example**:
```python
active_calls = {}

async for event in response.stream():
    if event.event_type == "tool_call_start":
        active_calls[event.tool_call_id] = {
            "name": event.tool_name,
            "arguments": "",
            "start_time": time.time()
        }
        print(f"🔧 Starting {event.tool_name}...")
```

**Common Use Cases**:
- Showing "function calling" indicators
- Tracking multiple concurrent tool calls
- Logging function call initiation

### ToolCallDelta
**Purpose**: Streams function arguments as they're generated character by character.

**Fields**:
- `event_type`: `"tool_call_delta"`
- `tool_call_id`: `str` - Identifier linking to the started call
- `arguments_delta`: `str` - Incremental argument characters (usually 1 character)

**Example**:
```python
call_arguments = {}

async for event in response.stream():
    if event.event_type == "tool_call_delta":
        call_id = event.tool_call_id
        if call_id not in call_arguments:
            call_arguments[call_id] = ""

        call_arguments[call_id] += event.arguments_delta

        # Show progressive argument building
        print(f"Args so far: {call_arguments[call_id]}")
```

**Common Use Cases**:
- Real-time display of function arguments
- Progressive validation of JSON arguments
- Building interactive function call UIs

**Note**: Arguments are built character by character and may not be valid JSON until complete.

### ToolCallComplete
**Purpose**: Signals that a function call is complete with fully formed arguments.

**Fields**:
- `event_type`: `"tool_call_complete"`
- `tool_call_id`: `str` - Identifier for the completed call
- `tool_name`: `str` - Function name
- `arguments`: `str` - Complete JSON arguments string

**Example**:
```python
import json

async for event in response.stream():
    if event.event_type == "tool_call_complete":
        try:
            args = json.loads(event.arguments)
            print(f"✅ {event.tool_name}({args})")

            # Execute the function
            result = await execute_function(event.tool_name, args)
            print(f"📤 Result: {result}")

        except json.JSONDecodeError:
            print(f"❌ Invalid arguments: {event.arguments}")
```

**Common Use Cases**:
- Executing function calls immediately
- Validating complete argument sets
- Building tool execution pipelines

### ResponseComplete
**Purpose**: Indicates the model has finished generating its response.

**Fields**:
- `event_type`: `"response_complete"`
- `finish_reason`: `str` - Why the response ended ("stop", "length", "tool_calls", etc.)
- `usage`: `Optional[Dict]` - Token usage statistics (if available)

**Example**:
```python
async for event in response.stream():
    if event.event_type == "response_complete":
        print(f"\n✅ Response complete: {event.finish_reason}")

        if event.usage:
            print(f"📊 Tokens used: {event.usage}")
            prompt_tokens = event.usage.get("prompt_tokens", 0)
            completion_tokens = event.usage.get("completion_tokens", 0)
            print(f"   Prompt: {prompt_tokens}, Completion: {completion_tokens}")
```

**Common Use Cases**:
- Finalizing UI states
- Logging completion statistics
- Triggering post-processing workflows

## Practical Streaming Patterns

### Pattern 1: Real-time Chat Interface
```python
async def stream_to_chat_ui(messages, tools=None):
    response = await call_llm_stream(messages, tools=tools)

    current_message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [],
        "reasoning": ""
    }

    async for event in response.stream():
        if event.event_type == "text_delta":
            current_message["content"] += event.content
            # Update UI with new content
            update_chat_message(current_message)

        elif event.event_type == "reasoning_delta":
            current_message["reasoning"] += event.reasoning
            # Show thinking indicator
            show_thinking_indicator(event.reasoning)

        elif event.event_type == "tool_call_complete":
            current_message["tool_calls"].append({
                "id": event.tool_call_id,
                "name": event.tool_name,
                "arguments": event.arguments
            })
            # Show function call in UI
            show_function_call(event.tool_name, event.arguments)

        elif event.event_type == "response_complete":
            # Finalize the message
            finalize_chat_message(current_message)
```

### Pattern 2: Progressive Tool Execution
```python
async def execute_tools_progressively(messages, tools):
    response = await call_llm_stream(messages, tools=tools)

    executed_tools = []

    async for event in response.stream():
        if event.event_type == "tool_call_complete":
            # Execute immediately when complete
            result = await execute_tool(event.tool_name, event.arguments)

            executed_tools.append({
                "call_id": event.tool_call_id,
                "name": event.tool_name,
                "arguments": event.arguments,
                "result": result
            })

            # Add result back to conversation immediately
            messages.add_tool_response(event.tool_call_id, str(result))

    return executed_tools
```

### Pattern 3: Buffered Streaming with Validation
```python
async def buffered_stream_with_validation(messages):
    response = await call_llm_stream(messages)

    text_buffer = ""
    word_count = 0

    async for event in response.stream():
        if event.event_type == "text_delta":
            text_buffer += event.content

            # Send complete words only
            if ' ' in event.content or event.content in '.!?':
                words = text_buffer.split()
                if len(words) > 1:  # Keep last partial word
                    complete_text = ' '.join(words[:-1]) + ' '
                    yield complete_text
                    text_buffer = words[-1]
                    word_count += len(words) - 1

        elif event.event_type == "response_complete":
            # Send remaining buffer
            if text_buffer.strip():
                yield text_buffer
```

### Pattern 4: Multi-Event Processing
```python
async def comprehensive_event_handler(messages, tools=None):
    response = await call_llm_stream(messages, tools=tools)

    state = {
        "text_content": "",
        "reasoning_content": "",
        "active_tools": {},
        "completed_tools": [],
        "start_time": time.time()
    }

    async for event in response.stream():
        event_time = time.time() - state["start_time"]

        if event.event_type == "text_delta":
            state["text_content"] += event.content
            log_event("text", event_time, len(event.content))

        elif event.event_type == "reasoning_delta":
            state["reasoning_content"] += event.reasoning
            log_event("reasoning", event_time, len(event.reasoning))

        elif event.event_type == "tool_call_start":
            state["active_tools"][event.tool_call_id] = {
                "name": event.tool_name,
                "start_time": event_time,
                "arguments": ""
            }
            log_event("tool_start", event_time, event.tool_name)

        elif event.event_type == "tool_call_complete":
            tool_info = state["active_tools"].pop(event.tool_call_id, {})
            tool_info.update({
                "arguments": event.arguments,
                "completion_time": event_time,
                "duration": event_time - tool_info.get("start_time", 0)
            })
            state["completed_tools"].append(tool_info)
            log_event("tool_complete", event_time, event.tool_name)

        elif event.event_type == "response_complete":
            state["finish_reason"] = event.finish_reason
            state["total_time"] = event_time
            log_event("complete", event_time, event.finish_reason)

    return state

def log_event(event_type, timestamp, data):
    print(f"[{timestamp:.2f}s] {event_type}: {data}")
```

## Error Handling in Streaming

### Handling Incomplete Streams
```python
async def robust_streaming(messages, tools=None):
    response = await call_llm_stream(messages, tools=tools)

    received_complete = False

    try:
        async for event in response.stream():
            if event.event_type == "response_complete":
                received_complete = True

            # Process event
            yield event

    except Exception as e:
        if not received_complete:
            # Stream was interrupted
            yield ResponseComplete(
                finish_reason="interrupted",
                usage=None
            )
        raise
```

### Validating Tool Call Completeness
```python
async def validate_tool_calls(messages, tools):
    response = await call_llm_stream(messages, tools=tools)

    started_calls = set()
    completed_calls = set()

    async for event in response.stream():
        if event.event_type == "tool_call_start":
            started_calls.add(event.tool_call_id)

        elif event.event_type == "tool_call_complete":
            completed_calls.add(event.tool_call_id)

        elif event.event_type == "response_complete":
            incomplete_calls = started_calls - completed_calls
            if incomplete_calls:
                print(f"⚠️ Incomplete tool calls: {incomplete_calls}")

                # Check if fallback was used
                if not response.is_streaming:
                    print("✅ Fallback should have handled this")
```

## Performance Considerations

### Minimize Event Processing Overhead
```python
# Good: Process only needed events
async for event in response.stream():
    if event.event_type == "text_delta":
        yield event.content
    # Skip other events if not needed

# Better: Use event filtering
text_events = (e for e in response.stream() if e.event_type == "text_delta")
async for event in text_events:
    yield event.content
```

### Batch Small Events
```python
async def batch_text_deltas(response, batch_size=10):
    buffer = ""
    count = 0

    async for event in response.stream():
        if event.event_type == "text_delta":
            buffer += event.content
            count += 1

            if count >= batch_size:
                yield buffer
                buffer = ""
                count = 0

    if buffer:  # Send remaining
        yield buffer
```

This streaming events system provides fine-grained control over LLM response processing, enabling sophisticated real-time applications while maintaining simplicity for basic use cases.