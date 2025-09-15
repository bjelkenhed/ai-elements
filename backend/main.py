import json
import logging
import os
import time
import uuid
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from parent directory (.env.local)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.local'))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Enable debug logging
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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


def convert_messages_for_openai(ui_messages: List[UIMessage]) -> List[Dict[str, Any]]:
    """Convert UI messages to OpenAI format"""
    openai_messages = []

    for msg in ui_messages:
        # Extract content from parts or use direct content
        content = ""
        if msg.parts:
            text_parts = [part.text for part in msg.parts if part.type == "text" and part.text]
            content = " ".join(text_parts)
        elif msg.content:
            content = msg.content

        if not content:
            logger.warning(f"No content found in message {msg.id}")
            content = "[Empty message]"

        openai_msg = {
            "role": msg.role,
            "content": content
        }

        # Handle files if present (basic implementation)
        if msg.files:
            logger.info(f"Message has {len(msg.files)} files attached")
            # For now, just mention files in content
            file_info = ", ".join([f.name for f in msg.files])
            openai_msg["content"] += f" [Files: {file_info}]"

        openai_messages.append(openai_msg)

    return openai_messages

def generate_ui_message_stream(request: ChatRequest):
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
                logger.info(f"    Part {j}: type={part.type}, text={part.text[:100] if part.text else None}...")
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

        # Add system message
        full_messages = [
            {"role": "system", "content": "You are a helpful assistant that can answer questions and help with tasks"}
        ] + openai_messages

        # Send start event (like AI Gateway)
        yield f'data: {json.dumps({"type": "start"})}\n\n'

        # Send start-step event
        yield f'data: {json.dumps({"type": "start-step"})}\n\n'

        # Start OpenAI streaming
        logger.info("Starting OpenAI stream...")
        stream = client.chat.completions.create(
            model="gpt-4o",  # Fixed to gpt-4o as requested
            messages=full_messages,
            stream=True,
            temperature=0.7
        )

        text_id = f"msg_{message_id}"
        accumulated_text = ""

        # Send text-start event (like AI Gateway)
        yield f'data: {json.dumps({"type": "text-start", "id": text_id})}\n\n'

        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                accumulated_text += content
                logger.debug(f"Streaming content: {repr(content)}")

                # Send text-delta event (like AI Gateway)
                yield f'data: {json.dumps({"type": "text-delta", "id": text_id, "delta": content})}\n\n'

        # Send text-stop event
        yield f'data: {json.dumps({"type": "text-stop", "id": text_id})}\n\n'

        # Send finish event
        yield f'data: {json.dumps({"type": "finish"})}\n\n'

        logger.info(f"Chat stream completed for message {message_id}")
        logger.info(f"Total content length: {len(accumulated_text)}")

    except Exception as e:
        logger.error(f"Error in chat stream: {str(e)}", exc_info=True)
        yield f'data: {json.dumps({"type": "error", "error": str(e)})}\n\n'

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
            text_parts = [part.text for part in msg.parts if part.type == "text" and part.text]
            if text_parts:
                content_preview = text_parts[0][:100] + "..." if len(text_parts[0]) > 100 else text_parts[0]
        elif msg.content:
            content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content

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
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "openai_key_configured": bool(os.getenv("OPENAI_API_KEY"))
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "AI Elements FastAPI Backend", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)