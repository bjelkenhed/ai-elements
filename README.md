This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

It is a repository for getting started with [AI Elements](https://ai-sdk.dev/elements/overview), currently one of the best ways to create UIs for AI Agents.

For a youtube tutorial see [Fullstack AI Chatbot with AI SDK 5 & Vercel’s New AI Elements](https://www.youtube.com/watch?v=6lur_Yit4PM).

## Getting Started

This project supports two backend options:

### Option 1: AI Gateway (Default)
Create a `.env.local` file in the root directory with an `AI_GATEWAY_API_KEY`:

```bash
AI_GATEWAY_API_KEY=your_key_here
```

An API key can be created [here](https://vercel.com/d?to=%2F%5Bteam%5D%2F%7E%2Fai%2Fapi-keys&title=Get%20your%20AI%20Gateway%20key).

Run the development server:
```bash
npm run dev
```

### Option 2: Local FastAPI Backend
Set up the local FastAPI backend for development:

1. **Setup Python dependencies:**
```bash
npm run backend:setup
```

2. **Configure environment:**
```bash
cd backend
cp .env.example .env
# Add your OpenAI API key to backend/.env
```

3. **Add to root `.env.local`:**
```bash
NEXT_PUBLIC_FASTAPI_URL=http://localhost:8000
```

4. **Run both frontend and backend:**
```bash
npm run dev:local
```

The UI will show a small indicator in the top-right corner showing which backend is active.

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

## Features

- **Dual Backend Support**: Switch between AI Gateway and local FastAPI
- **Real-time Streaming**: Full streaming support with both backends
- **Model Selection**: Support for multiple models (GPT-4o, Deepseek R1, etc.)
- **File Attachments**: Upload and discuss files
- **Reasoning Display**: View AI reasoning steps
- **Easy Development**: Simple commands to run either backend

This repository showcases the [AI Elements chatbot](https://ai-sdk.dev/elements/examples/chatbot) with additional FastAPI backend integration.

## Learn More

To learn more about AI Elements, take a look at [this](https://vercel.com/changelog/introducing-ai-elements)

