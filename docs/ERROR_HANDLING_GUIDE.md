# Error Handling and Best Practices Guide

This guide covers error handling patterns, best practices, and production considerations for the agentic-blocks LLM module.

## Error Types and Handling

### LLMError
The primary exception type for all LLM-related errors.

```python
from agentic_blocks.llm import LLMError

try:
    response = await call_llm_stream(messages)
    content = await response.content_async()
except LLMError as e:
    print(f"LLM call failed: {e}")
    # Handle the error appropriately
```

**Common LLMError scenarios**:
- Invalid API key or authentication failure
- Network connectivity issues
- API rate limiting
- Model not found or access denied
- Invalid parameters or configuration

### Configuration Errors
```python
try:
    response = call_llm(messages, api_key="invalid_key")
except LLMError as e:
    if "api_key" in str(e).lower():
        print("Please check your API key configuration")
    elif "model" in str(e).lower():
        print("Model not available or not specified")
    else:
        print(f"Configuration error: {e}")
```

### Streaming Interruption Errors
```python
async def robust_streaming(messages):
    response = await call_llm_stream(messages)
    content_buffer = ""

    try:
        async for event in response.stream():
            if event.event_type == "text_delta":
                content_buffer += event.content
            elif event.event_type == "response_complete":
                return content_buffer

    except Exception as e:
        print(f"Stream interrupted: {e}")
        # Return partial content if available
        if content_buffer:
            print(f"Returning partial content: {len(content_buffer)} characters")
            return content_buffer
        raise
```

## Retry Patterns

### Basic Retry with Exponential Backoff
```python
import asyncio
import random

async def call_llm_with_retry(messages, max_retries=3, base_delay=1.0):
    """Call LLM with retry logic and exponential backoff."""

    for attempt in range(max_retries):
        try:
            response = await call_llm_stream(messages)
            return response

        except LLMError as e:
            if attempt == max_retries - 1:
                # Last attempt failed
                raise

            # Calculate delay with jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(f"Attempt {attempt + 1} failed: {e}")
            print(f"Retrying in {delay:.1f} seconds...")
            await asyncio.sleep(delay)
```

### Conditional Retry
```python
def is_retryable_error(error):
    """Determine if an error is worth retrying."""
    error_str = str(error).lower()

    # Retry on temporary issues
    retryable_keywords = [
        "timeout", "connection", "network", "rate limit",
        "server error", "503", "502", "500"
    ]

    # Don't retry on permanent issues
    permanent_keywords = [
        "invalid api key", "unauthorized", "forbidden",
        "not found", "401", "403", "404"
    ]

    if any(keyword in error_str for keyword in permanent_keywords):
        return False

    return any(keyword in error_str for keyword in retryable_keywords)

async def smart_retry(messages, max_retries=3):
    """Retry only on retryable errors."""

    for attempt in range(max_retries):
        try:
            return await call_llm_stream(messages)

        except LLMError as e:
            if not is_retryable_error(e) or attempt == max_retries - 1:
                raise

            delay = 2 ** attempt
            print(f"Retryable error on attempt {attempt + 1}: {e}")
            await asyncio.sleep(delay)
```

### Circuit Breaker Pattern
```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""

        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise LLMError("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)

            # Success - reset failure count
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
            self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN

            raise

# Usage
circuit_breaker = CircuitBreaker()

async def protected_llm_call(messages):
    return await circuit_breaker.call(call_llm_stream, messages)
```

## Production Patterns

### Comprehensive Error Handling
```python
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ProductionLLMClient:
    def __init__(self, max_retries=3, timeout=30):
        self.max_retries = max_retries
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker()

    async def call_with_fallback(
        self,
        messages,
        tools=None,
        fallback_model=None
    ) -> Optional[str]:
        """Production LLM call with comprehensive error handling."""

        primary_model = "gpt-4o"
        models_to_try = [primary_model]

        if fallback_model:
            models_to_try.append(fallback_model)

        last_error = None

        for model in models_to_try:
            try:
                logger.info(f"Attempting LLM call with model: {model}")

                response = await asyncio.wait_for(
                    self.circuit_breaker.call(
                        call_llm_stream,
                        messages,
                        tools=tools,
                        model=model,
                        enable_fallback=True
                    ),
                    timeout=self.timeout
                )

                content = await response.content_async()
                tool_calls = await response.tool_calls_async()

                logger.info(f"LLM call successful with {model}")

                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "model_used": model,
                    "streaming_used": response.is_streaming
                }

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.timeout}s with {model}"
                logger.warning(last_error)

            except LLMError as e:
                last_error = f"LLM error with {model}: {e}"
                logger.warning(last_error)

                # Don't try fallback for certain errors
                if not is_retryable_error(e):
                    break

            except Exception as e:
                last_error = f"Unexpected error with {model}: {e}"
                logger.error(last_error, exc_info=True)

        # All models failed
        logger.error(f"All LLM attempts failed. Last error: {last_error}")
        raise LLMError(f"All models failed. Last error: {last_error}")
```

### Resource Management
```python
import asyncio
from contextlib import asynccontextmanager

class LLMResourceManager:
    def __init__(self, max_concurrent=10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_calls = 0
        self.total_calls = 0

    @asynccontextmanager
    async def acquire_slot(self):
        """Manage concurrent LLM calls."""
        async with self.semaphore:
            self.active_calls += 1
            self.total_calls += 1

            try:
                yield
            finally:
                self.active_calls -= 1

    async def call_with_resource_limit(self, messages, **kwargs):
        """Make LLM call with resource management."""
        async with self.acquire_slot():
            logger.info(f"Active calls: {self.active_calls}, Total: {self.total_calls}")
            return await call_llm_stream(messages, **kwargs)

# Usage
resource_manager = LLMResourceManager(max_concurrent=5)

async def managed_llm_call(messages):
    return await resource_manager.call_with_resource_limit(messages)
```

### Monitoring and Observability
```python
import time
from dataclasses import dataclass
from typing import List

@dataclass
class LLMMetrics:
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency: float = 0.0
    streaming_count: int = 0
    fallback_count: int = 0

    @property
    def success_rate(self) -> float:
        return self.success_count / self.request_count if self.request_count > 0 else 0

    @property
    def average_latency(self) -> float:
        return self.total_latency / self.request_count if self.request_count > 0 else 0

class ObservableLLMClient:
    def __init__(self):
        self.metrics = LLMMetrics()

    async def call_with_monitoring(self, messages, **kwargs):
        """LLM call with comprehensive monitoring."""
        start_time = time.time()
        self.metrics.request_count += 1

        try:
            response = await call_llm_stream(messages, **kwargs)

            # Ensure response is consumed to get accurate metrics
            content = await response.content_async()
            tool_calls = await response.tool_calls_async()

            # Record metrics
            self.metrics.success_count += 1
            if response.is_streaming:
                self.metrics.streaming_count += 1
            else:
                self.metrics.fallback_count += 1

            latency = time.time() - start_time
            self.metrics.total_latency += latency

            logger.info(f"LLM call successful in {latency:.2f}s")

            return {
                "content": content,
                "tool_calls": tool_calls,
                "latency": latency,
                "used_streaming": response.is_streaming
            }

        except Exception as e:
            self.metrics.error_count += 1
            latency = time.time() - start_time
            self.metrics.total_latency += latency

            logger.error(f"LLM call failed after {latency:.2f}s: {e}")
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            "requests": self.metrics.request_count,
            "success_rate": self.metrics.success_rate,
            "average_latency": self.metrics.average_latency,
            "streaming_rate": self.metrics.streaming_count / self.metrics.request_count if self.metrics.request_count > 0 else 0,
            "fallback_rate": self.metrics.fallback_count / self.metrics.request_count if self.metrics.request_count > 0 else 0
        }
```

## Best Practices

### 1. Configuration Management
```python
import os
from dataclasses import dataclass

@dataclass
class LLMConfig:
    api_key: str
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    max_retries: int = 3
    timeout: int = 30
    enable_fallback: bool = True

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            timeout=int(os.getenv("LLM_TIMEOUT", "30")),
            enable_fallback=os.getenv("LLM_ENABLE_FALLBACK", "true").lower() == "true"
        )

# Usage
config = LLMConfig.from_env()
response = await call_llm_stream(
    messages,
    api_key=config.api_key,
    model=config.model,
    enable_fallback=config.enable_fallback
)
```

### 2. Structured Logging
```python
import json
import logging
from datetime import datetime

class LLMLogger:
    def __init__(self, logger_name="llm_client"):
        self.logger = logging.getLogger(logger_name)

    def log_request(self, messages, model, tools=None):
        """Log LLM request details."""
        self.logger.info("LLM request", extra={
            "event": "llm_request",
            "model": model,
            "message_count": len(messages.get_messages() if hasattr(messages, 'get_messages') else messages),
            "has_tools": bool(tools),
            "tool_count": len(tools) if tools else 0,
            "timestamp": datetime.utcnow().isoformat()
        })

    def log_response(self, response_data, latency):
        """Log LLM response details."""
        self.logger.info("LLM response", extra={
            "event": "llm_response",
            "latency": latency,
            "used_streaming": response_data.get("used_streaming", False),
            "has_content": bool(response_data.get("content")),
            "has_tool_calls": bool(response_data.get("tool_calls")),
            "content_length": len(response_data.get("content", "")),
            "tool_call_count": len(response_data.get("tool_calls", [])),
            "timestamp": datetime.utcnow().isoformat()
        })

    def log_error(self, error, context=None):
        """Log LLM errors with context."""
        self.logger.error("LLM error", extra={
            "event": "llm_error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.utcnow().isoformat()
        }, exc_info=True)
```

### 3. Graceful Degradation
```python
async def llm_with_graceful_degradation(messages, tools=None):
    """LLM call with graceful degradation strategies."""

    try:
        # Try full streaming with tools
        response = await call_llm_stream(messages, tools=tools, enable_fallback=True)
        return await response.content_async()

    except LLMError as e:
        if "rate limit" in str(e).lower():
            # Rate limited - try with simpler model
            logger.warning("Rate limited, trying simpler model")
            try:
                response = await call_llm_stream(
                    messages,
                    model="gpt-3.5-turbo",
                    tools=None  # Remove tools for simpler call
                )
                return await response.content_async()
            except Exception:
                pass

        # Final fallback - return helpful error message
        logger.error(f"All LLM strategies failed: {e}")
        return "I'm temporarily unable to process your request. Please try again later."
```

### 4. Input Validation
```python
def validate_llm_inputs(messages, tools=None, max_message_length=10000):
    """Validate inputs before making LLM calls."""

    # Validate messages
    if not messages:
        raise ValueError("Messages cannot be empty")

    # Check message format
    message_list = messages.get_messages() if hasattr(messages, 'get_messages') else messages

    for i, msg in enumerate(message_list):
        if not isinstance(msg, dict):
            raise ValueError(f"Message {i} must be a dict")

        if "role" not in msg:
            raise ValueError(f"Message {i} missing 'role' field")

        if "content" in msg and len(str(msg["content"])) > max_message_length:
            raise ValueError(f"Message {i} content too long: {len(str(msg['content']))} > {max_message_length}")

    # Validate tools
    if tools:
        for i, tool in enumerate(tools):
            if not isinstance(tool, dict):
                raise ValueError(f"Tool {i} must be a dict")

            if "type" not in tool or tool["type"] != "function":
                raise ValueError(f"Tool {i} must have type='function'")

            if "function" not in tool:
                raise ValueError(f"Tool {i} missing 'function' field")

# Usage
async def safe_llm_call(messages, tools=None):
    validate_llm_inputs(messages, tools)
    return await call_llm_stream(messages, tools=tools)
```

### 5. Testing Patterns
```python
import pytest
from unittest.mock import AsyncMock, patch

class MockLLMResponse:
    def __init__(self, content="Mock response", tool_calls=None):
        self._content = content
        self._tool_calls = tool_calls or []
        self.is_streaming = True

    async def content_async(self):
        return self._content

    async def tool_calls_async(self):
        return self._tool_calls

    async def stream(self):
        from agentic_blocks.llm import TextDelta, ResponseComplete

        if self._content:
            yield TextDelta(content=self._content)
        yield ResponseComplete(finish_reason="stop")

@pytest.mark.asyncio
async def test_llm_call_success():
    """Test successful LLM call."""
    with patch('agentic_blocks.llm.call_llm_stream') as mock_call:
        mock_call.return_value = MockLLMResponse("Test response")

        response = await call_llm_stream(["test message"])
        content = await response.content_async()

        assert content == "Test response"
        assert response.is_streaming

@pytest.mark.asyncio
async def test_llm_call_with_tools():
    """Test LLM call with tool calls."""
    mock_tool_call = type('ToolCall', (), {
        'id': 'test_id',
        'function': type('Function', (), {
            'name': 'test_function',
            'arguments': '{"arg": "value"}'
        })()
    })()

    with patch('agentic_blocks.llm.call_llm_stream') as mock_call:
        mock_call.return_value = MockLLMResponse(
            content="",
            tool_calls=[mock_tool_call]
        )

        response = await call_llm_stream(["test"], tools=[{"type": "function"}])
        tool_calls = await response.tool_calls_async()

        assert len(tool_calls) == 1
        assert tool_calls[0].function.name == "test_function"

@pytest.mark.asyncio
async def test_llm_error_handling():
    """Test LLM error handling."""
    with patch('agentic_blocks.llm.call_llm_stream') as mock_call:
        mock_call.side_effect = LLMError("API error")

        with pytest.raises(LLMError):
            await call_llm_stream(["test message"])
```

This comprehensive error handling and best practices guide provides the foundation for building robust, production-ready applications with the agentic-blocks library.