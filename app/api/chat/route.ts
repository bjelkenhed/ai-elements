import {
  streamText,
  UIMessage,
  convertToModelMessages,
  tool,
  stepCountIs,
  createUIMessageStreamResponse
} from 'ai';
import { z } from 'zod';
import { logOuterLoop, logInnerLoop, logBackend, logTechnical, logger } from '@/lib/logger';
import { addToolCall, addToolResponse, addAssistantMessage } from '@/lib/conversation-logger';

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

// Math tools matching FastAPI backend for comparison
const add = tool({
  description: 'Adds two numbers together',
  inputSchema: z.object({
    a: z.number().describe('First number'),
    b: z.number().describe('Second number'),
  }),
  async *execute({ a, b }) {
    // Yield loading state
    yield {
      status: 'loading' as const,
      text: `Adding ${a} + ${b}...`,
      result: undefined,
    };

    // Simulate calculation delay
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = a + b;

    // Yield final result
    yield {
      status: 'success' as const,
      text: `The sum of ${a} + ${b} = ${result}`,
      result: result,
    };
  },
});

const multiply = tool({
  description: 'Multiplies two numbers together',
  inputSchema: z.object({
    a: z.number().describe('First number'),
    b: z.number().describe('Second number'),
  }),
  async *execute({ a, b }) {
    // Yield loading state
    yield {
      status: 'loading' as const,
      text: `Multiplying ${a} × ${b}...`,
      result: undefined,
    };

    // Simulate calculation delay
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = a * b;

    // Yield final result
    yield {
      status: 'success' as const,
      text: `The product of ${a} × ${b} = ${result}`,
      result: result,
    };
  },
});


export async function POST(req: Request) {
  const {
    messages,
    model,
    webSearch,
    _endpoint,
  }: {
    messages: UIMessage[];
    model: string;
    webSearch: boolean;
    _endpoint?: string;
  } = await req.json();

  // Debug: log that API route is called
  console.log(`🐛 API route called. Debug level: ${process.env.NEXT_PUBLIC_DEBUG_LEVEL}. Messages count: ${messages.length}`);
  console.log(`🐛 Logger level: ${logger.getLevel()}`);

  // Log user message and request start (outer loop)
  const userMessage = messages[messages.length - 1];
  console.log('🐛 Last message structure:', JSON.stringify(userMessage, null, 2));

  if (userMessage?.role === 'user') {
    // UIMessage uses 'parts' not 'content'
    const textContent = userMessage.parts?.find(part => part.type === 'text')?.text || 'Message with attachments';
    logOuterLoop('user_message', textContent, {
      model,
      webSearch,
      endpoint: _endpoint ? 'fastapi' : 'gateway'
    });
  }

  // If custom endpoint is specified, proxy to FastAPI
  if (_endpoint) {
    logBackend('local', `Proxying to FastAPI backend: ${_endpoint}`);

    try {
      const response = await fetch(_endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages, model, webSearch }),
      });

      if (!response.ok) {
        throw new Error(`FastAPI returned ${response.status}: ${response.statusText}`);
      }

      // Return the FastAPI response directly as it's already in the correct SSE format
      return new Response(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    } catch (error) {
      logTechnical('api_request', `Error proxying to FastAPI: ${error}`, {
        error: String(error),
        endpoint: _endpoint
      });
      return new Response(
        JSON.stringify({ error: `FastAPI proxy error: ${error}` }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
  }

  // Using AI Gateway backend
  logBackend('gateway', `Using AI Gateway with model: ${webSearch ? 'perplexity/sonar' : model}`);

  logOuterLoop('agent_response_start', 'Starting AI Gateway response', {
    model: webSearch ? 'perplexity/sonar' : model,
    webSearch,
    toolsAvailable: ['add', 'multiply']
  });

  logTechnical('frontend_stream_start', 'Frontend starting AI Gateway stream processing', {
    model: webSearch ? 'perplexity/sonar' : model,
    source: 'ai-gateway'
  });

  const result = streamText({
    model: webSearch ? 'perplexity/sonar' : 'alibaba/qwen-3-235b',
    messages: convertToModelMessages(messages),
    system:
      'You are a helpful assistant that can perform mathematical calculations. You have access to add and multiply tools for arithmetic operations. When users ask for calculations, you MUST use these tools to provide accurate results. Always use the appropriate tool for mathematical operations.',
    tools: {
      add,
      multiply,
    },
    toolChoice: 'auto',
    stopWhen: stepCountIs(3), // Allow up to 3 steps for tool calls and follow-up response
    onStepFinish: ({ toolCalls, toolResults }) => {
      // Log tool calls from AI Gateway
      if (toolCalls && toolCalls.length > 0) {
        toolCalls.forEach((toolCall) => {
          console.log('🐛 Tool call structure:', Object.keys(toolCall));
          logOuterLoop('tool_call_start', `Tool called: ${toolCall.toolName}`, {
            toolCallId: toolCall.toolCallId,
            toolName: toolCall.toolName,
            args: (toolCall as any).args || (toolCall as any).arguments || 'unknown',
            source: 'ai-gateway'
          });

          // Add tool call to conversation logger
          addToolCall(toolCall.toolCallId, toolCall.toolName, (toolCall as any).args || (toolCall as any).arguments || {}, {
            source: 'ai-gateway'
          });
        });
      }

      // Log tool results from AI Gateway
      if (toolResults && toolResults.length > 0) {
        toolResults.forEach((toolResult) => {
          console.log('🐛 Tool result structure:', Object.keys(toolResult));
          logOuterLoop('tool_response', `Tool completed: ${toolResult.toolName}`, {
            toolCallId: toolResult.toolCallId,
            toolName: toolResult.toolName,
            hasResult: !!(toolResult as any).result || !!(toolResult as any).output,
            hasError: !!(toolResult as any).error,
            source: 'ai-gateway'
          });

          // Add tool response to conversation logger
          const resultContent = (toolResult as any).result || (toolResult as any).output || 'No result';
          addToolResponse(toolResult.toolCallId, typeof resultContent === 'string' ? resultContent : JSON.stringify(resultContent), toolResult.toolName, {
            source: 'ai-gateway'
          });
        });
      }
    },
  });

 

  const response = result.toUIMessageStreamResponse({
    sendSources: true,
    sendReasoning: true
  });

  // Log the stream contents for debugging
  if (response.body) {
    const originalBody = response.body;
    let streamContent = '';

    const loggingTransform = new TransformStream({
      transform(chunk, controller) {
        const decoder = new TextDecoder();
        const chunkText = decoder.decode(chunk);
        streamContent += chunkText;
        console.log('🐛 AI Gateway stream chunk:', chunkText);
        controller.enqueue(chunk);
      },
      flush() {
        console.log('🐛 AI Gateway complete stream:', streamContent);
      }
    });

    return new Response(originalBody.pipeThrough(loggingTransform), {
      status: response.status,
      headers: response.headers,
    });
  }

  // send sources and reasoning back to the client
  return response
}