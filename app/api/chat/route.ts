import { streamText, UIMessage, convertToModelMessages, tool, stepCountIs } from 'ai';
import { z } from 'zod';

// Allow streaming responses up to 30 seconds
export const maxDuration = 30;

// getWeather tool definition with generator pattern for progressive results
const getWeather = tool({
  description: 'Get the current weather for a city',
  inputSchema: z.object({
    city: z.string().describe('The city to get weather for'),
  }),
  async *execute({ city }) {
    // Yield loading state
    yield {
      status: 'loading' as const,
      text: `Getting weather for ${city}...`,
      weather: undefined,
    };

    // Simulate weather API call delay
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Prepare weather data (matching FastAPI for consistency)
    const weatherData = {
      city: city,
      weather: "raining",
      temperature: "19°C",
      humidity: "95%",
      description: `It's raining cats and dogs in ${city}!`,
    };

    // Yield final result
    yield {
      status: 'success' as const,
      text: `The weather in ${city} is currently ${weatherData.weather} at ${weatherData.temperature}. ${weatherData.description}`,
      weather: weatherData,
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
    tools: {
      getWeather,
    },
    stopWhen: stepCountIs(3), // Allow up to 3 steps for tool calls and follow-up response
  });

  // send sources and reasoning back to the client
  return result.toUIMessageStreamResponse({
    sendSources: true,
    sendReasoning: true,
  });
}