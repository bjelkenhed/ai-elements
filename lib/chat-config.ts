/**
 * Chat configuration utilities for switching between AI Gateway and FastAPI backends
 */

export interface ChatConfig {
  apiPath: string;
  backendType: 'gateway' | 'local';
  baseUrl?: string;
}

export function getChatConfig(): ChatConfig {
  // Check for FastAPI URL in environment
  const fastapiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL;

  if (fastapiUrl) {
    return {
      apiPath: '/chat',
      backendType: 'local',
      baseUrl: fastapiUrl
    };
  }

  return {
    apiPath: '/api/chat',
    backendType: 'gateway'
  };
}

export function getApiUrl(): string {
  const config = getChatConfig();

  if (config.baseUrl) {
    return `${config.baseUrl}${config.apiPath}`;
  }

  return config.apiPath;
}