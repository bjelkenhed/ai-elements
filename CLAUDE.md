# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Next.js 15 project showcasing AI Elements - a component library for building AI interfaces. The project demonstrates a chatbot implementation using Vercel's AI SDK 5 and AI Elements components.

### Main Objective

The main objective for this project is to use AI SDK and the AI Elements components as the frontend for AI agents implemented in Python and exposed through FastAPI endpoints. As AI agents are long running, the progress is best shown by streaming back the progress of the agent to the frontend rather than just having some kind of spinner or progress bar. That way the user gets valuable information about what the agent is doing and an intuition about how the process might be improved. It will also give the user partial results while waiting for the final results at the completion of the task.

## Environment Setup

Requires a `.env.local` file with:
- `AI_GATEWAY_API_KEY` - Get one from Vercel's AI Gateway
- `OPENAI_API_KEY` - Required for the FastAPI backend

## Development Commands

- **Development server**: `npm run dev` (uses Turbopack, AI Gateway backend)
- **Local development**: `npm run dev:local` (runs both Next.js and FastAPI)
- **Backend only**: `npm run backend` (starts FastAPI server)
- **Backend setup**: `npm run backend:setup` (installs Python dependencies)
- **Build**: `npm run build` (uses Turbopack)
- **Production server**: `npm start`
- **Lint**: `eslint` (configured with Next.js TypeScript rules)

## Architecture

### Core Structure
- **App Router**: Uses Next.js 15 App Router (`app/` directory)
- **API Routes**: Chat endpoint at `app/api/chat/route.ts` handles streaming text with AI SDK
- **Components**: Organized in three main directories:
  - `components/ai-elements/` - AI-specific UI components from AI Elements
  - `components/ui/` - General UI components (Radix-based)
  - `components/ai-chat.tsx` - Main chat interface component

### AI Integration
- **Dual Backend Architecture**: Supports both AI Gateway and local FastAPI
- Uses Vercel AI SDK (`ai` package) with streaming responses
- Chat API supports model selection and web search via Perplexity (AI Gateway)
- Implements `useChat` hook for real-time conversation management
- Supports sources and reasoning display in chat responses
- FastAPI backend provides OpenAI GPT-4o with compatible streaming protocol

### Backend Switching
- Environment-based backend selection via `NEXT_PUBLIC_FASTAPI_URL`
- `lib/chat-config.ts` handles endpoint configuration
- Visual indicator shows active backend (top-right corner)
- Seamless switching between AI Gateway and local FastAPI

### Styling
- **CSS Framework**: Tailwind CSS v4
- **Fonts**: Geist Sans and Geist Mono
- **Components**: Built with Radix UI primitives
- **Styling Utils**: `lib/utils.ts` provides `cn()` function for conditional class merging

### Key Dependencies
- Next.js 15.5.3 with React 19
- AI SDK (`@ai-sdk/react`, `ai`)
- Radix UI components
- Tailwind CSS v4
- Lucide React icons
- TypeScript with strict mode

## Component Architecture

The AI Elements components follow a composable pattern:
- `Conversation` - Main chat container with scrolling
- `Message` - Individual message display
- `PromptInput` - Input interface with model selection, attachments, and tools
- `Response` - Handles AI response rendering
- `Sources`/`Reasoning` - Collapsible sections for additional context

## Configuration

- **TypeScript**: Configured with path mapping (`@/*` → `./`)
- **ESLint**: Uses Next.js core web vitals and TypeScript rules
- **Build**: Turbopack enabled for faster development and builds

### FastAPI Backend
- **Location**: `backend/` directory
- **Dependencies**: FastAPI, OpenAI, uvicorn (see `backend/requirements.txt`)
- **Environment**: Uses `OPENAI_API_KEY` from root `.env.local` file
- **Endpoints**: `/chat` (main), `/health` (status check)
- **Logging**: Extensive debugging logs to console and `backend.log`
- **Testing**: `backend/test_endpoint.py` for endpoint validation

## Backend Development Guidelines

### Critical Rule: Always Match AI Gateway Response Format

When developing or debugging the FastAPI backend, **always compare its response format to the AI Gateway** to ensure compatibility with the `useChat` hook and AI Elements components.

#### Comparison Method
```bash
# Test AI Gateway response format
curl -X POST "http://localhost:3000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"id": "test", "role": "user", "parts": [{"type": "text", "text": "Hello"}]}], "model": "openai/gpt-4o", "webSearch": false}' \
  --no-buffer | head -10

# Test FastAPI response format
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"id": "test", "role": "user", "parts": [{"type": "text", "text": "Hello"}]}], "model": "openai/gpt-4o", "webSearch": false}' \
  --no-buffer | head -10
```

#### Expected Format (Server-Sent Events)
Both backends must return identical SSE format:
```
data: {"type": "start"}

data: {"type": "start-step"}

data: {"type": "text-start", "id": "msg_..."}

data: {"type": "text-delta", "id": "msg_...", "delta": "Hello"}

data: {"type": "text-delta", "id": "msg_...", "delta": "!"}

data: {"type": "text-stop", "id": "msg_..."}

data: {"type": "finish"}
```

#### Key Requirements
- **SSE Format**: Each line starts with `data: ` and ends with `\n\n`
- **Event Types**: `start`, `start-step`, `text-start`, `text-delta`, `text-stop`, `finish`
- **Field Names**: Use `delta` (not `textDelta`), `id`, `type`
- **ID Format**: `msg_{uuid}` pattern
- **JSON Structure**: Exact same object structure as AI Gateway

#### Why This Matters
The AI Elements components and `useChat` hook expect **exact format compatibility**. Any deviation in:
- Event type names
- Field names
- SSE formatting
- JSON structure

Will cause the frontend to not render responses, even if the backend generates correct content.

#### Debugging Steps
1. **Always test both endpoints** with identical requests
2. **Compare outputs line-by-line** to identify format differences
3. **Fix FastAPI to match AI Gateway exactly**
4. **Never assume format compatibility** - always verify with curl tests


One way of look on the stream that comes from the backend APIs is that we have an outer and an inner loop. The outer loop consists of the complete agent response triggered by an user messages. In that outer loop consists of user messages, tool_calls, tool responses, and assistant messages like this: 

[{'role': 'system',
  'content': 'For calculating the sum of two numbers, use the add tool. For calculating the product of two numbers, use the multiply tool.'},
 {'role': 'user', 'content': 'What is 3 times 4 and 4 times 8?'},
 {'role': 'assistant',
  'content': '',
  'tool_calls': [{'id': '58ca373e4',
    'type': 'function',
    'function': {'name': 'multiply', 'arguments': '{"a": 4, "b": 8}'}}]},
 {'role': 'tool', 'tool_call_id': '58ca373e4', 'content': '32.0'},
 {'role': 'assistant', 'content': '3 times 4 is 12, and 4 times 8 is 32.'},
 {'role': 'user', 'content': 'What is 3 times 5'},
 {'role': 'assistant',
  'content': '',
  'tool_calls': [{'id': '3ec63da9e',
    'type': 'function',
    'function': {'name': 'multiply', 'arguments': '{"a": 3, "b": 5}'}}]},
 {'role': 'tool', 'tool_call_id': '3ec63da9e', 'content': '15.0'},
 {'role': 'assistant', 'content': '3 times 5 is 15.'}]
  
Some parts of that outer loop like tool calls and assistant messages are produced by the llm model and that can be seen as the inner loop. During an llm call there is an inner loop of a reasoning response and a tool call or an assistant content response for thinking models and only tool call or assistant messages for non thinking models. So the complete stream that is returned is a stream of the events in the outer loop and the parts of the inner loop like reasoning and tool calls/assistant messages. Most of it is represented in the example provided that is the conversion of messages, except for the reasoning part that is not represented there. 

When logging and structuring the code in the frontend and backend part it can be done with these concepts. 