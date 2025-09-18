# Tool Calls Handling Guide

This guide covers everything you need to know about using function calls (tool calls) with the agentic-blocks LLM module, from basic setup to advanced patterns.

## Quick Start

### 1. Define Your Tools
```python
# OpenAI function calling format
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
                        "description": "City name, e.g. 'San Francisco'"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit"
                    }
                },
                "required": ["location"]
            }
        }
    }
]
```

### 2. Make LLM Call with Tools
```python
from agentic_blocks import call_llm_stream, Messages
import json

messages = Messages()
messages.add_user_message("What's the weather in Paris?")

response = await call_llm_stream(messages, tools=tools)
tool_calls = await response.tool_calls_async()

if tool_calls:
    for call in tool_calls:
        function_name = call.function.name
        arguments = json.loads(call.function.arguments)
        print(f"Calling {function_name} with {arguments}")
```

### 3. Execute Functions and Continue Conversation
```python
# Execute the function
if function_name == "get_weather":
    weather_data = get_weather_api(arguments["location"])
    result = f"Weather in {arguments['location']}: {weather_data}"

    # Add result back to conversation
    messages.add_tool_response(call.id, result)

    # Continue conversation
    next_response = await call_llm_stream(messages)
    final_answer = await next_response.content_async()
    print(final_answer)  # Model's response using the weather data
```

## Tool Definition Patterns

### Simple Function
```python
def create_simple_tool(name, description, parameters):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": list(parameters.keys())
            }
        }
    }

# Usage
weather_tool = create_simple_tool(
    "get_weather",
    "Get weather for a location",
    {
        "location": {"type": "string", "description": "City name"},
        "unit": {"type": "string", "enum": ["C", "F"], "description": "Temperature unit"}
    }
)
```

### Complex Tool with Nested Objects
```python
search_tool = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": "Search through document database",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "filters": {
                    "type": "object",
                    "properties": {
                        "document_type": {"type": "string", "enum": ["pdf", "doc", "txt"]},
                        "date_range": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string", "format": "date"},
                                "end": {"type": "string", "format": "date"}
                            }
                        }
                    }
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100}
            },
            "required": ["query"]
        }
    }
}
```

### Tools with Optional Parameters
```python
calculation_tool = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "Perform mathematical calculations",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematical expression"},
                "precision": {"type": "integer", "description": "Decimal places", "default": 2}
            },
            "required": ["expression"]  # precision is optional
        }
    }
}
```

## Execution Patterns

### Basic Function Router
```python
async def execute_tool_call(call):
    """Execute a single tool call and return the result."""
    function_name = call.function.name
    arguments = json.loads(call.function.arguments)

    if function_name == "get_weather":
        return get_weather(arguments["location"], arguments.get("unit", "celsius"))
    elif function_name == "search_documents":
        return search_docs(arguments["query"], arguments.get("filters"), arguments.get("limit", 10))
    elif function_name == "calculate":
        return calculate_expression(arguments["expression"], arguments.get("precision", 2))
    else:
        raise ValueError(f"Unknown function: {function_name}")

# Usage
tool_calls = await response.tool_calls_async()
if tool_calls:
    for call in tool_calls:
        result = await execute_tool_call(call)
        messages.add_tool_response(call.id, str(result))
```

### Class-based Tool Handler
```python
class ToolHandler:
    def __init__(self):
        self.functions = {
            "get_weather": self.get_weather,
            "search_documents": self.search_documents,
            "calculate": self.calculate
        }

    async def execute(self, call):
        function_name = call.function.name
        if function_name not in self.functions:
            raise ValueError(f"Unknown function: {function_name}")

        arguments = json.loads(call.function.arguments)
        return await self.functions[function_name](**arguments)

    async def get_weather(self, location, unit="celsius"):
        # Implementation
        return f"Weather in {location}: 22°{unit[0].upper()}"

    async def search_documents(self, query, filters=None, limit=10):
        # Implementation
        return f"Found {limit} documents for '{query}'"

    async def calculate(self, expression, precision=2):
        # Implementation
        try:
            result = eval(expression)  # Use safely in production!
            return round(result, precision)
        except Exception as e:
            return f"Error: {e}"

# Usage
handler = ToolHandler()
tool_calls = await response.tool_calls_async()
if tool_calls:
    for call in tool_calls:
        result = await handler.execute(call)
        messages.add_tool_response(call.id, str(result))
```

### Parallel Tool Execution
```python
import asyncio

async def execute_tools_parallel(tool_calls, handler):
    """Execute multiple tool calls in parallel."""

    async def execute_single(call):
        try:
            result = await handler.execute(call)
            return call.id, str(result), None
        except Exception as e:
            return call.id, None, str(e)

    # Execute all tools concurrently
    tasks = [execute_single(call) for call in tool_calls]
    results = await asyncio.gather(*tasks)

    # Process results
    for call_id, result, error in results:
        if error:
            messages.add_tool_response(call_id, f"Error: {error}")
        else:
            messages.add_tool_response(call_id, result)

# Usage
tool_calls = await response.tool_calls_async()
if tool_calls:
    await execute_tools_parallel(tool_calls, handler)
```

## Streaming Tool Call Processing

### Real-time Tool Execution
```python
async def stream_with_immediate_execution(messages, tools, handler):
    """Execute tool calls as soon as they complete in the stream."""

    response = await call_llm_stream(messages, tools=tools)

    async for event in response.stream():
        if event.event_type == "text_delta":
            print(event.content, end="", flush=True)

        elif event.event_type == "tool_call_complete":
            print(f"\n🔧 Executing {event.tool_name}...")

            # Parse and execute immediately
            try:
                arguments = json.loads(event.arguments)
                result = await handler.execute_by_name(event.tool_name, arguments)

                print(f"✅ Result: {result}")

                # Add to conversation for context
                messages.add_tool_response(event.tool_call_id, str(result))

            except Exception as e:
                print(f"❌ Error: {e}")
                messages.add_tool_response(event.tool_call_id, f"Error: {e}")

        elif event.event_type == "response_complete":
            print(f"\n✅ Response complete: {event.finish_reason}")
```

### Progressive Tool Call Display
```python
async def display_progressive_tool_calls(messages, tools):
    """Show tool calls as they build up character by character."""

    response = await call_llm_stream(messages, tools=tools)
    active_calls = {}

    async for event in response.stream():
        if event.event_type == "tool_call_start":
            active_calls[event.tool_call_id] = {
                "name": event.tool_name,
                "arguments": "",
                "display_line": None
            }

            # Create display line
            print(f"\n🔧 {event.tool_name}(", end="", flush=True)

        elif event.event_type == "tool_call_delta":
            # Add to arguments buffer
            call_data = active_calls[event.tool_call_id]
            call_data["arguments"] += event.arguments_delta

            # Display the character
            print(event.arguments_delta, end="", flush=True)

        elif event.event_type == "tool_call_complete":
            print(")")  # Close the function call display

            # Validate and execute
            try:
                arguments = json.loads(event.arguments)
                print(f"   Executing with: {arguments}")

                result = await execute_tool(event.tool_name, arguments)
                print(f"   Result: {result}")

            except json.JSONDecodeError:
                print(f"   ❌ Invalid JSON: {event.arguments}")
```

## Advanced Tool Call Patterns

### Conditional Tool Execution
```python
async def conditional_tool_execution(messages, tools, conditions):
    """Execute tools only if certain conditions are met."""

    response = await call_llm_stream(messages, tools=tools)
    tool_calls = await response.tool_calls_async()

    if not tool_calls:
        return await response.content_async()

    executed_calls = []

    for call in tool_calls:
        function_name = call.function.name
        arguments = json.loads(call.function.arguments)

        # Check conditions
        if function_name in conditions:
            condition_func = conditions[function_name]
            if not condition_func(arguments):
                # Skip execution, provide error message
                messages.add_tool_response(
                    call.id,
                    f"Function {function_name} not allowed with arguments {arguments}"
                )
                continue

        # Execute if conditions pass
        result = await execute_tool(function_name, arguments)
        messages.add_tool_response(call.id, str(result))
        executed_calls.append(call)

    return executed_calls

# Define conditions
conditions = {
    "get_weather": lambda args: "location" in args and len(args["location"]) > 0,
    "send_email": lambda args: "@" in args.get("to", ""),  # Must have valid email
    "delete_file": lambda args: False,  # Never allow file deletion
}
```

### Tool Call Validation and Sanitization
```python
import jsonschema

class ValidatingToolHandler:
    def __init__(self):
        self.schemas = {
            "get_weather": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "minLength": 1},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["location"]
            }
        }

    def validate_arguments(self, function_name, arguments):
        """Validate function arguments against schema."""
        if function_name in self.schemas:
            try:
                jsonschema.validate(arguments, self.schemas[function_name])
                return True, None
            except jsonschema.ValidationError as e:
                return False, str(e)
        return True, None  # No schema = no validation

    def sanitize_arguments(self, function_name, arguments):
        """Sanitize function arguments."""
        if function_name == "get_weather":
            # Clean location string
            if "location" in arguments:
                arguments["location"] = arguments["location"].strip().title()

            # Ensure unit is lowercase
            if "unit" in arguments:
                arguments["unit"] = arguments["unit"].lower()

        return arguments

    async def execute_with_validation(self, call):
        function_name = call.function.name

        try:
            arguments = json.loads(call.function.arguments)
        except json.JSONDecodeError as e:
            return f"Invalid JSON arguments: {e}"

        # Validate
        valid, error = self.validate_arguments(function_name, arguments)
        if not valid:
            return f"Validation error: {error}"

        # Sanitize
        arguments = self.sanitize_arguments(function_name, arguments)

        # Execute
        return await self.execute_function(function_name, arguments)
```

### Tool Call Retry Logic
```python
async def execute_with_retry(call, max_retries=3, delay=1.0):
    """Execute a tool call with retry logic for failures."""

    function_name = call.function.name
    arguments = json.loads(call.function.arguments)

    for attempt in range(max_retries):
        try:
            result = await execute_tool(function_name, arguments)
            return result

        except Exception as e:
            if attempt == max_retries - 1:
                return f"Failed after {max_retries} attempts: {e}"

            print(f"Attempt {attempt + 1} failed: {e}, retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff

    return "Max retries exceeded"
```

### Tool Call Caching
```python
import hashlib
from functools import wraps

class CachingToolHandler:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {}  # Time-to-live for cache entries

    def _cache_key(self, function_name, arguments):
        """Generate cache key from function name and arguments."""
        args_str = json.dumps(arguments, sort_keys=True)
        return hashlib.md5(f"{function_name}:{args_str}".encode()).hexdigest()

    def _is_cacheable(self, function_name):
        """Determine if a function's results should be cached."""
        cacheable_functions = {"get_weather", "search_documents", "calculate"}
        return function_name in cacheable_functions

    async def execute_with_cache(self, call, ttl_seconds=300):
        """Execute tool call with caching."""
        function_name = call.function.name
        arguments = json.loads(call.function.arguments)

        if not self._is_cacheable(function_name):
            return await self.execute_function(function_name, arguments)

        # Check cache
        cache_key = self._cache_key(function_name, arguments)

        if cache_key in self.cache:
            cache_time = self.cache_ttl.get(cache_key, 0)
            if time.time() - cache_time < ttl_seconds:
                print(f"🔄 Cache hit for {function_name}")
                return self.cache[cache_key]

        # Execute and cache
        result = await self.execute_function(function_name, arguments)
        self.cache[cache_key] = result
        self.cache_ttl[cache_key] = time.time()

        return result
```

## Tool Call Error Handling

### Graceful Error Handling
```python
async def robust_tool_execution(messages, tools):
    """Handle tool call errors gracefully."""

    response = await call_llm_stream(messages, tools=tools)
    tool_calls = await response.tool_calls_async()

    if not tool_calls:
        return await response.content_async()

    execution_results = []

    for call in tool_calls:
        try:
            # Parse arguments
            arguments = json.loads(call.function.arguments)

            # Execute function
            result = await execute_tool(call.function.name, arguments)

            # Success
            messages.add_tool_response(call.id, str(result))
            execution_results.append({
                "call_id": call.id,
                "function": call.function.name,
                "success": True,
                "result": result
            })

        except json.JSONDecodeError as e:
            # Invalid JSON arguments
            error_msg = f"Invalid arguments format: {e}"
            messages.add_tool_response(call.id, error_msg)
            execution_results.append({
                "call_id": call.id,
                "function": call.function.name,
                "success": False,
                "error": error_msg
            })

        except Exception as e:
            # Function execution error
            error_msg = f"Execution error: {e}"
            messages.add_tool_response(call.id, error_msg)
            execution_results.append({
                "call_id": call.id,
                "function": call.function.name,
                "success": False,
                "error": error_msg
            })

    return execution_results
```

### Partial Failure Handling
```python
async def handle_partial_failures(tool_calls, handler):
    """Handle cases where some tool calls succeed and others fail."""

    successful_calls = []
    failed_calls = []

    for call in tool_calls:
        try:
            result = await handler.execute(call)
            successful_calls.append((call, result))
            messages.add_tool_response(call.id, str(result))

        except Exception as e:
            failed_calls.append((call, e))
            # Provide helpful error message to the model
            error_context = f"Failed to execute {call.function.name}: {e}. Please try a different approach."
            messages.add_tool_response(call.id, error_context)

    # Log results
    print(f"✅ {len(successful_calls)} successful, ❌ {len(failed_calls)} failed")

    # If any calls succeeded, continue; if all failed, maybe retry
    if failed_calls and not successful_calls:
        print("⚠️ All tool calls failed, consider fallback strategy")

    return successful_calls, failed_calls
```

This comprehensive tool calls guide provides everything needed to implement robust function calling with the agentic-blocks library, from basic usage to advanced error handling and optimization patterns.