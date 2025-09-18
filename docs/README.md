# Agentic Blocks LLM Documentation

This directory contains comprehensive documentation for using the `agentic_blocks.llm` module effectively in your projects.

## 📚 Documentation Overview

### 🚀 [LLM Usage Guide](LLM_USAGE_GUIDE.md)
**Start here for a complete overview of the LLM module.**

Covers:
- Quick start examples
- All three core functions (`call_llm`, `call_llm_stream_basic`, `call_llm_stream`)
- `LLMResponse` object interface
- Configuration and environment setup
- Advanced usage patterns
- Best practices summary

### 🌊 [Streaming Events Reference](STREAMING_EVENTS.md)
**Deep dive into real-time streaming capabilities.**

Covers:
- Complete event types reference (`TextDelta`, `ToolCallStart`, etc.)
- Real-time processing patterns
- Streaming UI integration examples
- Performance optimization techniques
- Event buffering and validation

### 🔧 [Tool Calls Handling Guide](TOOL_CALLS_GUIDE.md)
**Everything about function calling with LLMs.**

Covers:
- Tool definition patterns and schemas
- Execution strategies (sequential, parallel, conditional)
- Real-time tool call processing
- Advanced patterns (caching, validation, retry logic)
- Error handling for tool calls

### ⚠️ [Error Handling & Best Practices](ERROR_HANDLING_GUIDE.md)
**Production-ready patterns and error handling.**

Covers:
- Error types and recovery strategies
- Retry patterns with exponential backoff
- Circuit breaker implementation
- Production monitoring and observability
- Testing patterns and mocking
- Configuration management

## 🎯 Quick Navigation by Use Case

### Building a Chat Interface
1. **Basic Chat**: [LLM Usage Guide - Quick Start](LLM_USAGE_GUIDE.md#quick-start)
2. **Real-time Streaming**: [Streaming Events - Chat Interface Pattern](STREAMING_EVENTS.md#pattern-1-real-time-chat-interface)
3. **Error Handling**: [Error Handling - Graceful Degradation](ERROR_HANDLING_GUIDE.md#3-graceful-degradation)

### Implementing Function Calling
1. **Basic Setup**: [Tool Calls Guide - Quick Start](TOOL_CALLS_GUIDE.md#quick-start)
2. **Execution Patterns**: [Tool Calls Guide - Execution Patterns](TOOL_CALLS_GUIDE.md#execution-patterns)
3. **Error Handling**: [Tool Calls Guide - Error Handling](TOOL_CALLS_GUIDE.md#tool-call-error-handling)

### Building Production Systems
1. **Configuration**: [Error Handling - Configuration Management](ERROR_HANDLING_GUIDE.md#1-configuration-management)
2. **Monitoring**: [Error Handling - Monitoring and Observability](ERROR_HANDLING_GUIDE.md#monitoring-and-observability)
3. **Resource Management**: [Error Handling - Resource Management](ERROR_HANDLING_GUIDE.md#resource-management)

### Web API Integration
1. **Streaming Responses**: [Streaming Events - Progressive Tool Execution](STREAMING_EVENTS.md#pattern-2-progressive-tool-execution)
2. **Event Processing**: [Streaming Events - Multi-Event Processing](STREAMING_EVENTS.md#pattern-4-multi-event-processing)
3. **Error Recovery**: [Error Handling - Retry Patterns](ERROR_HANDLING_GUIDE.md#retry-patterns)

## 🔍 Key Concepts

### Unified Response Interface
All three LLM functions return the same `LLMResponse` object:

```python
# All return LLMResponse with identical interface
response1 = call_llm(messages)                    # Non-streaming
response2 = await call_llm_stream_basic(messages) # Basic streaming
response3 = await call_llm_stream(messages)       # Streaming + fallback

# Same methods work for all
content = await response.content_async()
tool_calls = await response.tool_calls_async()
async for event in response.stream():
    # Process events...
```

### Streaming vs Non-Streaming
- **Non-streaming** (`call_llm`): Simple, synchronous, complete response
- **Basic streaming** (`call_llm_stream_basic`): Fast streaming, may have incomplete tool calls
- **Robust streaming** (`call_llm_stream`): Streaming with automatic fallback for reliable tool calls

### Tool Call Reliability
The module automatically handles tool call reliability:
- Validates JSON completeness
- Detects incomplete streaming
- Falls back to non-streaming when needed
- Provides detailed error context

### Event-Driven Architecture
Real-time processing through streaming events:
- `TextDelta`: Incremental text content
- `ToolCallComplete`: Complete function calls
- `ReasoningDelta`: Model thinking process
- `ResponseComplete`: Finished response

## 📖 Code Examples Library

### Basic Usage
```python
from agentic_blocks import call_llm_stream, Messages

messages = Messages()
messages.add_user_message("Hello!")

response = await call_llm_stream(messages)
print(await response.content_async())
```

### Streaming Text
```python
response = await call_llm_stream(messages)
async for event in response.stream():
    if event.event_type == "text_delta":
        print(event.content, end="", flush=True)
```

### Tool Calls
```python
tools = [{"type": "function", "function": {...}}]
response = await call_llm_stream(messages, tools=tools)

tool_calls = await response.tool_calls_async()
if tool_calls:
    for call in tool_calls:
        result = execute_function(call.function.name,
                                json.loads(call.function.arguments))
        messages.add_tool_response(call.id, str(result))
```

### Error Handling
```python
try:
    response = await call_llm_stream(messages)
    content = await response.content_async()
except LLMError as e:
    print(f"LLM error: {e}")
    # Handle gracefully
```

## 🚦 Getting Started Checklist

### Environment Setup
- [ ] Set `OPENAI_API_KEY` environment variable
- [ ] Optionally set `OPENAI_MODEL` and `OPENAI_BASE_URL`
- [ ] Install package: `pip install agentic-blocks`

### Basic Implementation
- [ ] Import: `from agentic_blocks import call_llm_stream, Messages`
- [ ] Create messages: `messages = Messages()`
- [ ] Make call: `response = await call_llm_stream(messages)`
- [ ] Get content: `content = await response.content_async()`

### Adding Streaming
- [ ] Process events: `async for event in response.stream():`
- [ ] Handle `text_delta` events for real-time text
- [ ] Handle `response_complete` for completion

### Adding Tool Calls
- [ ] Define tools in OpenAI format
- [ ] Pass tools to `call_llm_stream(messages, tools=tools)`
- [ ] Process `tool_calls_async()` results
- [ ] Add results back with `messages.add_tool_response()`

### Production Readiness
- [ ] Add error handling with try/catch for `LLMError`
- [ ] Implement retry logic for transient failures
- [ ] Add monitoring and logging
- [ ] Configure rate limiting and resource management

## 💡 Integration Tips

### For Web Applications
- Use `response.stream()` for real-time user interfaces
- Implement Server-Sent Events or WebSocket streaming
- Handle partial responses gracefully on connection drops

### For API Services
- Use `enable_fallback=True` for reliable tool calls
- Implement circuit breakers for service resilience
- Add comprehensive monitoring and alerting

### For Batch Processing
- Use `call_llm()` for simple, synchronous processing
- Implement parallel processing with resource limits
- Add progress tracking and resumable operations

### For Development
- Use `enable_fallback=False` to test streaming robustness
- Add detailed logging to understand model behavior
- Mock responses for testing without API calls

## 🔗 External Resources

- [OpenAI Function Calling Documentation](https://platform.openai.com/docs/guides/function-calling)
- [Server-Sent Events Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)

---

For questions or contributions, please refer to the main project repository.