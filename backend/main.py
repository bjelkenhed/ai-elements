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

from llm import call_llm_stream, TextDelta, ToolCallStart, ToolCallDelta, ToolCallComplete, ResponseComplete
from messages import Messages

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

    def __init__(self, message_id: str):
        self.message_id = message_id
        self.text_id = f"msg_{message_id}"
        self.tool_calls = {}
        self.has_started_text = False

    async def convert_to_sse_stream(self, stream_events) -> AsyncGenerator[str, None]:
        """Convert call_llm_stream events to AI Gateway SSE format."""

        yield self._sse_event({'type': 'start'})
        yield self._sse_event({'type': 'start-step'})

        has_tool_calls = False

        async for event in stream_events:
            if isinstance(event, TextDelta):
                async for text_event in self._handle_text_delta(event):
                    yield text_event
            elif isinstance(event, ToolCallStart):
                has_tool_calls = True
                async for tool_event in self._handle_tool_start(event):
                    yield tool_event
            elif isinstance(event, ToolCallDelta):
                async for tool_event in self._handle_tool_delta(event):
                    yield tool_event
            elif isinstance(event, ToolCallComplete):
                async for tool_event in self._handle_tool_complete(event):
                    yield tool_event
            elif isinstance(event, ResponseComplete):
                if self.has_started_text:
                    yield self._sse_event({'type': 'text-end', 'id': self.text_id})
                break

        # Generate follow-up text after tool execution
        if has_tool_calls:
            async for followup_event in self._generate_followup_response():
                yield followup_event

        yield self._sse_event({'type': 'finish-step'})
        yield self._sse_event({'type': 'finish'})
        yield "data: [DONE]\n\n"

    def _sse_event(self, data: Dict[str, Any]) -> str:
        """Format data as SSE event."""
        return f"data: {json.dumps(data)}\n\n"

    async def _handle_text_delta(self, event: TextDelta):
        """Handle streaming text content."""
        if not self.has_started_text:
            yield self._sse_event({
                'type': 'text-start',
                'id': self.text_id,
                'providerMetadata': {'openai': {'itemId': self.text_id}}
            })
            self.has_started_text = True
        yield self._sse_event({'type': 'text-delta', 'id': self.text_id, 'delta': event.content})

    async def _handle_tool_start(self, event: ToolCallStart):
        """Handle tool call start."""
        self.tool_calls[event.tool_call_id] = {
            'name': event.tool_name, 'arguments': '', 'completed': False
        }
        yield self._sse_event({
            'type': 'tool-input-start',
            'toolCallId': event.tool_call_id,
            'toolName': event.tool_name
        })

    async def _handle_tool_delta(self, event: ToolCallDelta):
        """Handle tool call argument deltas."""
        if event.tool_call_id in self.tool_calls:
            self.tool_calls[event.tool_call_id]['arguments'] += event.arguments_delta
            yield self._sse_event({
                'type': 'tool-input-delta',
                'toolCallId': event.tool_call_id,
                'inputTextDelta': event.arguments_delta
            })

    async def _handle_tool_complete(self, event: ToolCallComplete):
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
        messages = Messages(
            system_prompt="You are a helpful assistant that can answer questions and help with tasks. When appropriate, use the available tools to provide accurate information."
        )

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
        adapter = FastAPIStreamAdapter(message_id)
        stream_events = call_llm_stream(
            messages=messages,
            tools=openai_tools,
            model=None,  # Use MODEL_ID from environment
            temperature=0.7
        )

        async for sse_event in adapter.convert_to_sse_stream(stream_events):
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
