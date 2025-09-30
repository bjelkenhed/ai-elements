# Frontend Logging Architecture

## Overview

This project implements a two-loop logging architecture for AI chat systems:

- **Backend (agentic-blocks)**: Handles outer loop logging via `messages.getMessages()` and RichLogger for tool calls, reasoning, etc.
- **Frontend**: Focuses on UI component lifecycle, streaming response processing, and user interactions.

## Environment Configuration

Set the debug level using the `NEXT_PUBLIC_DEBUG_LEVEL` environment variable in `.env.local`:

```bash
# No logging (production default)
NEXT_PUBLIC_DEBUG_LEVEL=off

# Basic logging - outer loop events only (user messages, tool calls, responses)
NEXT_PUBLIC_DEBUG_LEVEL=basic

# Detailed logging - includes inner loop events (reasoning, content streaming)
NEXT_PUBLIC_DEBUG_LEVEL=detailed

# Verbose logging - includes technical debug info (SSE chunks, UI state changes)
NEXT_PUBLIC_DEBUG_LEVEL=verbose
```

## Logging Levels

### Basic Level (Recommended for Development)
- 👤 User messages
- 🚀 Agent response start/complete
- 🔧 Tool calls
- ✅ Tool responses
- 🏠/🌐 Backend selection

### Detailed Level
- All basic events plus:
- 💭 Reasoning streams
- 🔄 Tool generation
- 📄 Content streaming
- 📝 Content deltas

### Verbose Level
- All detailed events plus:
- 🔍 Message part rendering
- 📡 SSE chunks
- 🌐 API requests/responses
- 🎬 Frontend stream processing
- 🎛️ UI state changes

## Example Output

### Basic Level
```
👤 USER_MESSAGE: Hello, write a story about a robot [model=qwen/qwen3-next-80b-a3b-thinking, webSearch=false, endpoint=fastapi]
🏠 BACKEND: Using local backend: http://localhost:8000/chat
🚀 AGENT_RESPONSE_START: Starting agent response [model=qwen/qwen3-next-80b-a3b-thinking, webSearch=false]
🔧 TOOL_CALL_START: Tool: multiply [messageId=msg_123, toolName=multiply, state=input-streaming]
✅ TOOL_RESPONSE: multiply completed [messageId=msg_123, toolName=multiply, hasOutput=true, hasError=false]
✅ ASSISTANT_RESPONSE_COMPLETE: AI response completed [messageId=msg_123]
```

### Detailed Level (adds inner loop)
```
💭 REASONING_STREAM: Reasoning: The user wants a story about a robot. I should create an engaging narrative... [messageId=msg_123, length=1250, isStreaming=true]
📝 CONTENT_DELTA: Content: Once upon a time, in a bustling city... [messageId=msg_123, length=45]
```

### Verbose Level (adds technical details)
```
🎬 FRONTEND_STREAM_START: Frontend started processing stream from FastAPI [endpoint=http://localhost:8000/chat]
🎛️ UI_STATE_CHANGE: Chat status changed: submitted → streaming [previousStatus=submitted, newStatus=streaming, messagesCount=4]
📺 FRONTEND_STREAM_CHUNK: Frontend processing text delta: Once upon a time... [messageId=msg_123, deltaLength=45, source=fastapi]
```

## Usage in Components

The logging is automatically handled by:

1. **API Routes** (`app/api/chat/route.ts`): Logs streaming events and backend interactions
2. **Custom Hook** (`hooks/use-chat-logger.ts`): Logs UI component state changes and user interactions
3. **Chat Component** (`components/ai-chat.tsx`): Uses the custom hook for user interaction logging

## Frontend vs Backend Logging

### Frontend Logging Focus
- **UI Component Lifecycle**: Message rendering, tool state display
- **User Interactions**: Form submissions, model changes, backend switching
- **Stream Processing**: How frontend processes SSE events from backends
- **Performance**: UI responsiveness, rendering performance

### Backend Logging Focus (agentic-blocks)
- **Agent Reasoning**: Actual AI thinking and decision making
- **Tool Execution**: Tool calls and their results
- **Model Interactions**: LLM requests and responses
- **Business Logic**: Agent workflow and state management

This separation ensures clean, focused debugging for both frontend UI issues and backend AI logic issues.