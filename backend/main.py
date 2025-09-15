import asyncio
import json
import logging
import os
import time
import uuid
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from parent directory (.env.local)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Enable debug logging
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Elements FastAPI Backend")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for {request.method} {request.url}")
    logger.error(f"Request body: {await request.body()}")
    logger.error(f"Validation errors: {exc.errors()}")
    return HTTPException(status_code=422, detail=f"Validation error: {exc.errors()}")


# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class MessageFile(BaseModel):
    name: str
    type: str
    size: int
    url: Optional[str] = None


class MessagePart(BaseModel):
    type: str
    text: Optional[str] = None
    # Add other part types as needed


class UIMessage(BaseModel):
    id: str
    role: str
    parts: Optional[List[MessagePart]] = None
    content: Optional[str] = None  # For compatibility
    files: Optional[List[MessageFile]] = None


class ChatRequest(BaseModel):
    messages: List[UIMessage]
    model: str
    webSearch: bool = False


# Tool Framework
class ToolSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any]
    required: List[str] = []


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: ToolSchema


class BaseTool(ABC):
    def __init__(self, name: str, description: str, parameters: ToolSchema):
        self.name = name
        self.description = description
        self.parameters = parameters

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass

    def to_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name, description=self.description, parameters=self.parameters
        )


# Weather Tool Implementation
class WeatherTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="getWeather",
            description="Get the current weather for a city",
            parameters=ToolSchema(
                properties={
                    "city": {
                        "type": "string",
                        "description": "The city to get weather for",
                    }
                },
                required=["city"],
            ),
        )

    async def execute_streaming(self, streaming_callback, **kwargs):
        """Execute with streaming callback to yield progressive results"""
        city = kwargs.get("city", "Unknown")

        # First yield: loading state
        await streaming_callback(
            {
                "status": "loading",
                "text": f"Getting weather for {city}...",
                "weather": None,
            }
        )

        # Simulate processing time
        await asyncio.sleep(2.0)

        # Prepare weather data
        weather_data = {
            "city": city,
            "weather": "raining",
            "temperature": "29°C",
            "humidity": "95%",
            "description": f"It's raining cats and dogs in {city}!",
        }

        # Second yield: final result
        await streaming_callback(
            {
                "status": "success",
                "text": f"The weather in {city} is currently {weather_data['weather']} at {weather_data['temperature']}. {weather_data['description']}",
                "weather": weather_data,
            }
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Legacy execute method for backward compatibility"""
        city = kwargs.get("city", "Unknown")
        weather_data = {
            "city": city,
            "weather": "raining",
            "temperature": "39°C",
            "humidity": "95%",
            "description": f"It's raining cats and dogs in {city}!",
        }
        await asyncio.sleep(0.5)
        return weather_data


# Tool Registry
tools_registry: Dict[str, BaseTool] = {"getWeather": WeatherTool()}


def convert_messages_for_openai(ui_messages: List[UIMessage]) -> List[Dict[str, Any]]:
    """Convert UI messages to OpenAI format"""
    openai_messages = []

    for msg in ui_messages:
        # Extract content from parts or use direct content
        content = ""
        if msg.parts:
            text_parts = [
                part.text for part in msg.parts if part.type == "text" and part.text
            ]
            content = " ".join(text_parts)
        elif msg.content:
            content = msg.content

        if not content:
            logger.warning(f"No content found in message {msg.id}")
            content = "[Empty message]"

        openai_msg = {"role": msg.role, "content": content}

        # Handle files if present (basic implementation)
        if msg.files:
            logger.info(f"Message has {len(msg.files)} files attached")
            # For now, just mention files in content
            file_info = ", ".join([f.name for f in msg.files])
            openai_msg["content"] += f" [Files: {file_info}]"

        openai_messages.append(openai_msg)

    return openai_messages


async def generate_ui_message_stream(request: ChatRequest):
    """Generate UI Message Stream compatible with AI SDK useChat hook"""
    message_id = str(uuid.uuid4())

    logger.info(f"Starting chat stream for message {message_id}")
    logger.info(f"Model: {request.model}, WebSearch: {request.webSearch}")
    logger.info(f"Messages: {len(request.messages)} messages")

    # Log detailed message information
    for i, msg in enumerate(request.messages):
        logger.info(f"Message {i}: ID={msg.id}, Role={msg.role}")

        # Log content from parts or direct content
        if msg.parts:
            logger.info(f"  Parts: {len(msg.parts)} parts")
            for j, part in enumerate(msg.parts):
                logger.info(
                    f"    Part {j}: type={part.type}, text={part.text[:100] if part.text else None}..."
                )
        elif msg.content:
            logger.info(f"  Content: {msg.content[:100]}...")
        else:
            logger.info("  No content found")

        if msg.files:
            logger.info(f"  Files: {[f.name for f in msg.files]}")

    try:
        # Convert messages to OpenAI format
        openai_messages = convert_messages_for_openai(request.messages)
        logger.info(f"Converted messages for OpenAI: {openai_messages}")

        # Prepare tools for OpenAI
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters.model_dump(),
                },
            }
            for tool in tools_registry.values()
        ]

        # Add system message
        full_messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that can answer questions and help with tasks. When appropriate, use the available tools to provide accurate information.",
            }
        ] + openai_messages

        # Get the full OpenAI response (non-streaming) to process tools properly
        logger.info("Starting OpenAI request...")
        response = client.chat.completions.create(
            model="gpt-4o", messages=full_messages, tools=openai_tools, temperature=0.7
        )

        # Send start event
        yield f"data: {json.dumps({'type': 'start'})}\n\n"

        # Send start-step event (matching AI Gateway)
        yield f"data: {json.dumps({'type': 'start-step'})}\n\n"

        message = response.choices[0].message

        # If we have tool calls, stream them using AI Gateway canonical format
        if message.tool_calls:
            # Stream tool calls using the canonical format
            for tool_call in message.tool_calls:
                call_id = tool_call.id
                tool_name = tool_call.function.name
                arguments_json = tool_call.function.arguments

                logger.info(
                    f"Processing tool call: {tool_name} with args: {arguments_json}"
                )

                # Stream tool-input-start
                yield f"data: {json.dumps({'type': 'tool-input-start', 'toolCallId': call_id, 'toolName': tool_name})}\n\n"

                # Stream tool input deltas (simulate streaming the JSON parameters)
                for char in arguments_json:
                    yield f"data: {json.dumps({'type': 'tool-input-delta', 'toolCallId': call_id, 'inputTextDelta': char})}\n\n"
                    await asyncio.sleep(0.01)

                try:
                    arguments = json.loads(arguments_json)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse tool arguments: {e}")
                    continue

                # Stream tool-input-available
                provider_metadata = {"openai": {"itemId": f"fc_{call_id}"}}
                yield f"data: {json.dumps({'type': 'tool-input-available', 'toolCallId': call_id, 'toolName': tool_name, 'input': arguments, 'providerMetadata': provider_metadata})}\n\n"

                # Execute tool with streaming progressive results
                if tool_name in tools_registry:
                    tool = tools_registry[tool_name]

                    # Check if tool supports streaming execution
                    if hasattr(tool, "execute_streaming"):
                        # Use streaming execution with callback
                        results_queue = []

                        async def streaming_callback(result):
                            results_queue.append(result)

                        # First, stream loading state immediately
                        loading_result = {
                            "status": "loading",
                            "text": f"Getting weather for {arguments.get('city', 'Unknown')}...",
                            "weather": None,
                        }
                        yield f"data: {json.dumps({'type': 'tool-output-available', 'toolCallId': call_id, 'output': loading_result})}\n\n"

                        # Simulate processing delay
                        await asyncio.sleep(2.0)

                        # Then stream final result
                        city = arguments.get("city", "Unknown")
                        weather_data = {
                            "city": city,
                            "weather": "raining",
                            "temperature": "9°C",
                            "humidity": "95%",
                            "description": f"It's raining cats and dogs in {city}!",
                        }

                        final_result = {
                            "status": "success",
                            "text": f"The weather in {city} is currently {weather_data['weather']} at {weather_data['temperature']}. {weather_data['description']}",
                            "weather": weather_data,
                        }
                        yield f"data: {json.dumps({'type': 'tool-output-available', 'toolCallId': call_id, 'output': final_result})}\n\n"
                    else:
                        # Fallback to regular execution
                        result = await tool.execute(**arguments)
                        yield f"data: {json.dumps({'type': 'tool-output-available', 'toolCallId': call_id, 'output': result})}\n\n"

                    logger.info(f"Tool {tool_name} executed successfully")
                else:
                    logger.warning(f"Tool {tool_name} not found in registry")
                    error_result = {"error": "Tool not found"}
                    yield f"data: {json.dumps({'type': 'tool-output-available', 'toolCallId': call_id, 'output': error_result})}\n\n"

            # After tool execution, generate follow-up text response (matching AI Gateway multi-step pattern)

            # Send finish-step to complete tool execution phase
            yield f"data: {json.dumps({'type': 'finish-step'})}\n\n"

            # Send start-step to begin text response phase
            yield f"data: {json.dumps({'type': 'start-step'})}\n\n"

            # Generate follow-up conversational response
            follow_up_text = f"The weather in {arguments.get('city', 'Unknown')} is currently rainy, with a temperature of 19°C. It's pouring quite heavily!"

        else:
            # No tool calls, use the original response
            follow_up_text = message.content

        # Stream the response text
        if follow_up_text:
            text_id = f"msg_{message_id}"
            # Add providerMetadata to match AI Gateway format
            yield f"data: {json.dumps({'type': 'text-start', 'id': text_id, 'providerMetadata': {'openai': {'itemId': text_id}}})}\n\n"

            # Stream the text content word by word (matching AI Gateway behavior)
            words = follow_up_text.split(" ")
            for i, word in enumerate(words):
                if i == 0:
                    # First word without leading space
                    delta = word
                else:
                    # Subsequent words with leading space
                    delta = f" {word}"

                yield f"data: {json.dumps({'type': 'text-delta', 'id': text_id, 'delta': delta})}\n\n"
                await asyncio.sleep(
                    0.05
                )  # Slightly longer delay for word-based streaming

            yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"

        # Send finish-step event (matching AI Gateway)
        yield f"data: {json.dumps({'type': 'finish-step'})}\n\n"

        # Send finish event
        yield f"data: {json.dumps({'type': 'finish'})}\n\n"

        # Send final DONE marker (matching AI Gateway)
        yield "data: [DONE]\n\n"

        logger.info(f"Chat completed for message {message_id}")
        logger.info(
            f"Tool calls processed: {len(message.tool_calls) if message.tool_calls else 0}"
        )

    except Exception as e:
        logger.error(f"Error in chat stream: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Chat endpoint compatible with AI SDK useChat hook"""
    logger.info("=== CHAT REQUEST ===")
    logger.info(f"Model: {request.model}")
    logger.info(f"WebSearch: {request.webSearch}")
    logger.info(f"Messages count: {len(request.messages)}")

    for i, msg in enumerate(request.messages):
        # Extract a preview of the content for logging
        content_preview = ""
        if msg.parts:
            text_parts = [
                part.text for part in msg.parts if part.type == "text" and part.text
            ]
            if text_parts:
                content_preview = (
                    text_parts[0][:100] + "..."
                    if len(text_parts[0]) > 100
                    else text_parts[0]
                )
        elif msg.content:
            content_preview = (
                msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            )

        logger.info(f"Message {i}: {msg.role} - {content_preview}")
        if msg.files:
            logger.info(f"  Files: {[f.name for f in msg.files]}")

    # Validate OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found in environment")
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    # Only support GPT-4o for now
    if request.model != "openai/gpt-4o":
        logger.warning(f"Model {request.model} requested, using gpt-4o instead")

    return StreamingResponse(
        generate_ui_message_stream(request),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "AI Elements FastAPI Backend", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
