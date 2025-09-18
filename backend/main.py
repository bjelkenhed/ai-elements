import asyncio
import json
import logging
import os
import time
import uuid
from typing import List, Dict, Any, Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from agentic_blocks import call_llm_stream, Messages

# Setup
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Elements FastAPI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return HTTPException(status_code=422, detail=f"Validation error: {exc.errors()}")


# Request Models
class MessageFile(BaseModel):
    name: str
    type: str
    size: int
    url: Optional[str] = None

class MessagePart(BaseModel):
    type: str
    text: Optional[str] = None

class UIMessage(BaseModel):
    id: str
    role: str
    parts: Optional[List[MessagePart]] = None
    content: Optional[str] = None
    files: Optional[List[MessageFile]] = None

class ChatRequest(BaseModel):
    messages: List[UIMessage]
    model: str
    webSearch: bool = False


# Weather Tool (simplified)
class WeatherTool:
    def __init__(self):
        self.name = "getWeather"
        self.description = "Get the current weather for a city"
        self.parameters = {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "The city to get weather for"}
            },
            "required": ["city"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        city = kwargs.get("city", "Unknown")
        await asyncio.sleep(2.0)  # Simulate API call
        return {
            "city": city,
            "weather": "raining",
            "temperature": "19°C",
            "humidity": "95%",
            "description": f"It's raining cats and dogs in {city}!",
        }

# Tool Registry
tools_registry = {"getWeather": WeatherTool()}


class FastAPIStreamAdapter:
    """Converts call_llm_stream events to AI Gateway SSE format."""

    def __init__(self, message_id: str, model: str = "", messages=None, openai_tools=None):
        self.message_id = message_id
        self.model = model
        self.messages = messages
        self.openai_tools = openai_tools
        self.text_id = f"msg_{message_id}"
        self.tool_calls = {}
        self.has_started_text = False
        self.has_started_reasoning = False
        self.reasoning_id = "reasoning-0"

    async def convert_to_sse_stream(self, response) -> AsyncGenerator[str, None]:
        """Convert agentic-blocks LLMResponse to AI Gateway SSE format."""
        logger = logging.getLogger(__name__)

        logger.info(f"Starting chat stream {self.message_id} using model: {self.model}")
        yield self._sse_event({'type': 'start'})
        yield self._sse_event({'type': 'start-step'})

        has_tool_calls = False
        streaming_events = []
        text_content_buffer = ""

        # Stream text events from response.stream()
        async for event in response.stream():
            streaming_events.append(event.event_type)

            if event.event_type == "text_delta":
                # Buffer text content instead of immediately showing it
                text_content_buffer += event.content
            elif event.event_type == "reasoning_delta":
                # Handle reasoning events only for thinking models
                async for reasoning_event in self._handle_reasoning_delta(event):
                    yield reasoning_event
            elif event.event_type == "tool_call_start":
                pass  # Tool call started
            elif event.event_type == "tool_call_complete":
                pass  # Tool call completed
            elif event.event_type == "response_complete":
                pass  # Response completed
                if self.has_started_reasoning:
                    yield self._sse_event({'type': 'reasoning-end', 'id': self.reasoning_id})
                break

        reasoning_count = streaming_events.count("reasoning_delta")
        other_events = [e for e in streaming_events if e != "reasoning_delta"]
        # Stream processing completed

        # Get reliable tool calls from response.tool_calls()
        tool_calls = await response.tool_calls_async()
        if tool_calls:
            logger.info(f"Processing {len(tool_calls)} tool calls")

        # Decide whether to show initial text content
        should_show_initial_text = False
        if text_content_buffer.strip():  # Only show if there's meaningful content
            should_show_initial_text = True
        elif not tool_calls:  # Show even empty content if no tool calls
            should_show_initial_text = True

        if should_show_initial_text and text_content_buffer:
            yield self._sse_event({
                'type': 'text-start',
                'id': self.text_id,
                'providerMetadata': {'openai': {'itemId': self.text_id}}
            })
            yield self._sse_event({'type': 'text-delta', 'id': self.text_id, 'delta': text_content_buffer})
            yield self._sse_event({'type': 'text-end', 'id': self.text_id})

        if tool_calls:
            has_tool_calls = True
            for i, tool_call in enumerate(tool_calls):
                # Processing tool call silently
                async for tool_event in self._handle_reliable_tool_call(tool_call):
                    yield tool_event

        # Generate follow-up response with tool results
        if has_tool_calls:
            # Generating follow-up response
            yield self._sse_event({'type': 'finish-step'})
            yield self._sse_event({'type': 'start-step'})

            async for followup_event in self._generate_model_followup_response(tool_calls):
                yield followup_event

        logger.info(f"Chat completed {self.message_id}")
        yield self._sse_event({'type': 'finish-step'})
        yield self._sse_event({'type': 'finish'})
        yield "data: [DONE]\n\n"

    def _sse_event(self, data: Dict[str, Any]) -> str:
        """Format data as SSE event."""
        event_str = f"data: {json.dumps(data)}\n\n"
        return event_str

    async def _handle_text_delta(self, event):
        """Handle streaming text content."""
        if not self.has_started_text:
            yield self._sse_event({
                'type': 'text-start',
                'id': self.text_id,
                'providerMetadata': {'openai': {'itemId': self.text_id}}
            })
            self.has_started_text = True
        yield self._sse_event({'type': 'text-delta', 'id': self.text_id, 'delta': event.content})

    async def _handle_reasoning_delta(self, event):
        """Handle reasoning content from thinking models."""
        # Only expose reasoning for thinking models (indicated by "thinking" in model name)
        if 'thinking' not in self.model.lower():
            return

        if not self.has_started_reasoning:
            yield self._sse_event({
                'type': 'reasoning-start',
                'id': self.reasoning_id
            })
            self.has_started_reasoning = True
        yield self._sse_event({'type': 'reasoning-delta', 'id': self.reasoning_id, 'delta': event.reasoning})

    async def _handle_tool_start(self, event):
        """Handle tool call start."""
        self.tool_calls[event.tool_call_id] = {
            'name': event.tool_name, 'arguments': '', 'completed': False
        }
        yield self._sse_event({
            'type': 'tool-input-start',
            'toolCallId': event.tool_call_id,
            'toolName': event.tool_name
        })

    async def _handle_tool_delta(self, event):
        """Handle tool call argument deltas."""
        if event.tool_call_id in self.tool_calls:
            self.tool_calls[event.tool_call_id]['arguments'] += event.arguments_delta
            yield self._sse_event({
                'type': 'tool-input-delta',
                'toolCallId': event.tool_call_id,
                'inputTextDelta': event.arguments_delta
            })

    async def _handle_tool_complete(self, event):
        """Handle tool call completion and execution."""
        if event.tool_call_id not in self.tool_calls:
            return

        self.tool_calls[event.tool_call_id]['completed'] = True
        accumulated_args = self.tool_calls[event.tool_call_id]['arguments']

        # Parse arguments
        try:
            arguments = json.loads(accumulated_args) if accumulated_args else {}
        except json.JSONDecodeError:
            arguments = {}

        # Stream tool-input-available
        yield self._sse_event({
            'type': 'tool-input-available',
            'toolCallId': event.tool_call_id,
            'toolName': event.tool_name,
            'input': arguments,
            'providerMetadata': {'openai': {'itemId': f'fc_{event.tool_call_id}'}}
        })

        # Execute and stream tool
        async for tool_event in self._execute_tool(event.tool_call_id, event.tool_name, arguments):
            yield tool_event

    async def _handle_reliable_tool_call(self, tool_call):
        """Handle complete tool call from response.tool_calls() - more reliable than streaming."""
        logger = logging.getLogger(__name__)
        tool_call_id = tool_call.id
        tool_name = tool_call.function.name
        arguments_str = tool_call.function.arguments or "{}"

        logger.info(f"🎬 Simulating tool-input-delta events for {tool_name}")

        # Parse arguments from the complete tool call
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            arguments = {}

        # Stream tool-input-start
        yield self._sse_event({
            'type': 'tool-input-start',
            'toolCallId': tool_call_id,
            'toolName': tool_name
        })

        # Stream tool-input-delta events character by character (like AI Gateway)
        for char in arguments_str:
            yield self._sse_event({
                'type': 'tool-input-delta',
                'toolCallId': tool_call_id,
                'inputTextDelta': char
            })
            # Small delay to simulate streaming (optional)
            await asyncio.sleep(0.01)

        # Stream tool-input-available (complete arguments)
        yield self._sse_event({
            'type': 'tool-input-available',
            'toolCallId': tool_call_id,
            'toolName': tool_name,
            'input': arguments,
            'providerMetadata': {'openai': {'itemId': f'fc_{tool_call_id}'}}
        })

        # Execute and stream tool
        async for tool_event in self._execute_tool(tool_call_id, tool_name, arguments):
            yield tool_event

    async def _execute_tool(self, tool_call_id: str, tool_name: str, arguments: Dict[str, Any]):
        """Execute a tool and stream progress."""
        if tool_name not in tools_registry:
            yield self._sse_event({
                'type': 'tool-output-available',
                'toolCallId': tool_call_id,
                'output': {'error': 'Tool not found'}
            })
            return

        tool = tools_registry[tool_name]
        city = arguments.get('city', 'Unknown')

        # Stream loading state
        yield self._sse_event({
            'type': 'tool-output-available',
            'toolCallId': tool_call_id,
            'output': {'status': 'loading', 'text': f'Getting weather for {city}...'},
            'preliminary': True
        })

        # Execute tool
        result = await tool.execute(**arguments)

        # Stream final result
        yield self._sse_event({
            'type': 'tool-output-available',
            'toolCallId': tool_call_id,
            'output': {
                'status': 'success',
                'text': f"The weather in {result['city']} is currently {result['weather']} at {result['temperature']}. {result['description']}",
                'weather': result
            }
        })

    async def _generate_followup_response(self):
        """Generate follow-up text after tool execution."""
        yield self._sse_event({'type': 'finish-step'})
        yield self._sse_event({'type': 'start-step'})

        # Check if we have successful weather tool calls
        followup_text = "I'd be happy to help you with weather information, but I wasn't able to determine which city you wanted weather for. Could you please specify the city name?"

        for tool_data in self.tool_calls.values():
            if tool_data['name'] == 'getWeather' and tool_data['completed']:
                try:
                    arguments = json.loads(tool_data['arguments']) if tool_data['arguments'] else {}
                    if arguments.get('city'):
                        city = arguments['city']
                        followup_text = f"The weather in {city} is currently rainy, with a temperature of 19°C. It's pouring quite heavily!"
                        break
                except (json.JSONDecodeError, KeyError):
                    pass

        # Stream follow-up text
        followup_id = f"msg_{self.message_id}_followup"
        yield self._sse_event({
            'type': 'text-start',
            'id': followup_id,
            'providerMetadata': {'openai': {'itemId': followup_id}}
        })

        # Stream word by word
        words = followup_text.split(' ')
        for i, word in enumerate(words):
            delta = word if i == 0 else f' {word}'
            yield self._sse_event({'type': 'text-delta', 'id': followup_id, 'delta': delta})
            await asyncio.sleep(0.05)

        yield self._sse_event({'type': 'text-end', 'id': followup_id})

    async def _generate_model_followup_response(self, tool_calls):
        """Generate follow-up response from the model after tool execution."""
        if not self.messages or not tool_calls:
            return

        logger = logging.getLogger(__name__)

        # Add tool results to the conversation
        for tool_call in tool_calls:
            # Execute the tool to get the result
            tool_name = tool_call.function.name
            if tool_name in tools_registry:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    tool = tools_registry[tool_name]
                    result = await tool.execute(**arguments)

                    # Add tool response to messages
                    self.messages.add_tool_response(tool_call.id, json.dumps(result))
                    logger.info(f"✅ Added tool result for {tool_name}: {result}")
                except Exception as e:
                    logger.error(f"❌ Tool execution failed for {tool_name}: {e}")
                    self.messages.add_tool_response(tool_call.id, f"Error: {str(e)}")

        # Generate follow-up response from the model
        try:
            followup_response = await call_llm_stream(
                messages=self.messages,
                tools=self.openai_tools,
                temperature=0.7,
                enable_fallback=True
            )

            # Stream the follow-up response
            followup_id = f"msg_{uuid.uuid4()}"
            has_started_followup = False

            async for event in followup_response.stream():
                if event.event_type == "text_delta":
                    if not has_started_followup:
                        yield self._sse_event({
                            'type': 'text-start',
                            'id': followup_id,
                            'providerMetadata': {'openai': {'itemId': followup_id}}
                        })
                        has_started_followup = True
                    yield self._sse_event({'type': 'text-delta', 'id': followup_id, 'delta': event.content})
                elif event.event_type == "response_complete":
                    if has_started_followup:
                        yield self._sse_event({'type': 'text-end', 'id': followup_id})
                    break

        except Exception as e:
            logger.error(f"❌ Follow-up response generation failed: {e}")
            # Fallback to the tool output
            yield self._sse_event({
                'type': 'text-start',
                'id': f"msg_{uuid.uuid4()}",
                'providerMetadata': {'openai': {'itemId': f"msg_{uuid.uuid4()}"}}
            })
            yield self._sse_event({'type': 'text-delta', 'id': f"msg_{uuid.uuid4()}", 'delta': "Tool execution completed successfully."})
            yield self._sse_event({'type': 'text-end', 'id': f"msg_{uuid.uuid4()}"})



def extract_message_content(ui_msg: UIMessage) -> str:
    """Extract text content from UI message."""
    if ui_msg.parts:
        text_parts = [part.text for part in ui_msg.parts if part.type == "text" and part.text]
        content = " ".join(text_parts)
    elif ui_msg.content:
        content = ui_msg.content
    else:
        content = "[Empty message]"

    # Add file information if present
    if ui_msg.files:
        file_info = ", ".join([f.name for f in ui_msg.files])
        content += f" [Files: {file_info}]"

    return content

async def generate_ui_message_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Generate streaming response compatible with AI SDK useChat hook."""
    message_id = str(uuid.uuid4())
    logger.info(f"Starting chat stream {message_id} - {len(request.messages)} messages")

    try:
        # Build messages for LLM
        messages = Messages()
        messages.add_system_message("You are a helpful assistant that can answer questions and help with tasks. When appropriate, use the available tools to provide accurate information.")

        for ui_msg in request.messages:
            content = extract_message_content(ui_msg)
            if ui_msg.role == "user":
                messages.add_user_message(content)
            elif ui_msg.role == "assistant":
                messages.add_assistant_message(content)

        # Prepare tools in OpenAI format
        openai_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        } for tool in tools_registry.values()]

        # Stream LLM response through adapter
        adapter = FastAPIStreamAdapter(message_id, request.model, messages, openai_tools)
        response = await call_llm_stream(
            messages=messages,
            tools=openai_tools,
            temperature=0.7,
            enable_fallback=True  # Automatic fallback for reliable tool calls
        )

        async for sse_event in adapter.convert_to_sse_stream(response):
            yield sse_event

        logger.info(f"Chat completed {message_id}")

    except Exception as e:
        logger.error(f"Error in chat stream: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


# API Endpoints
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Chat endpoint compatible with AI SDK useChat hook."""
    logger.info(f"Chat request: {request.model}, {len(request.messages)} messages")

    # Validate API key
    try:
        from utils.config_utils import get_llm_config
        config = get_llm_config()
        if not config.get("api_key"):
            raise HTTPException(status_code=500, detail="API key not configured. Set OPENROUTER_API_KEY or OPENAI_API_KEY.")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        generate_ui_message_stream(request),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        from utils.config_utils import get_llm_config
        api_key_configured = bool(get_llm_config().get("api_key"))
    except (ValueError, ImportError):
        api_key_configured = False

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "api_key_configured": api_key_configured
    }

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Elements FastAPI Backend", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
