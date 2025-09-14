# FastAPI Backend for AI Elements

A minimal FastAPI backend that provides OpenAI GPT-4o streaming compatible with the AI SDK's useChat hook.

## Quick Start

### 1. Setup Python Environment
```bash
# Install dependencies
npm run backend:setup
```

### 2. Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Add your OpenAI API key to .env
echo "OPENAI_API_KEY=your_key_here" > .env
```

### 3. Start Development Servers

**Option 1: Backend + Frontend together**
```bash
npm run dev:local
```

**Option 2: Backend only**
```bash
npm run backend
```

**Option 3: Frontend only (AI Gateway)**
```bash
npm run dev:gateway
```

## Endpoints

- **POST /chat** - Main chat endpoint compatible with useChat
- **GET /health** - Health check endpoint
- **GET /** - Root endpoint with version info

## Features

✅ OpenAI GPT-4o streaming
✅ AI SDK compatible SSE format
✅ Extensive logging for debugging
✅ CORS enabled for local development
✅ Health check endpoint
✅ File attachment support (basic)

## Debugging

Logs are written to:
- Console (formatted with timestamps)
- `backend.log` file

Log levels include:
- Request/response details
- OpenAI API calls
- Streaming token details
- Error stack traces

## Architecture

The FastAPI backend implements the exact same streaming protocol as the AI SDK:
- `message-start` - Begin new assistant message
- `text-start` - Begin text streaming
- `text-delta` - Stream text tokens
- `text-end` - Complete text streaming
- `message-finish` - Complete assistant message
- `error` - Error handling

This ensures compatibility with the existing `useChat` hook without frontend changes.