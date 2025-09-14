import { streamText, UIMessage, convertToModelMessages } from 'ai';

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

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

  console.log('messages', messages);
  console.log('model', model);
  console.log('webSearch', webSearch);
  console.log('_endpoint', _endpoint);

  // If custom endpoint is specified, proxy to FastAPI
  if (_endpoint) {
    console.log('Proxying to FastAPI backend:', _endpoint);

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

      // Log response details for debugging
      console.log('FastAPI response status:', response.status);
      console.log('FastAPI response headers:', Object.fromEntries(response.headers.entries()));

      // Simply return the FastAPI response directly
      return new Response(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    } catch (error) {
      console.error('Error proxying to FastAPI:', error);
      return new Response(
        JSON.stringify({ error: `FastAPI proxy error: ${error}` }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
  }

  const result = streamText({
    model: webSearch ? 'perplexity/sonar' : model,
    messages: convertToModelMessages(messages),
    system:
      'You are a helpful assistant that can answer questions and help with tasks',
  });

  // send sources and reasoning back to the client
  return result.toUIMessageStreamResponse({
    sendSources: true,
    sendReasoning: true,
  });
}