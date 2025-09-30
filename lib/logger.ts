/**
 * Structured logger for AI chat streaming based on two-loop architecture:
 * - Outer Loop: Complete agent response cycle (user -> tools -> assistant)
 * - Inner Loop: LLM generation process (reasoning, tool generation, content streaming)
 */

export type LogLevel = 'off' | 'basic' | 'detailed' | 'verbose';

export type OuterLoopEvent =
  | 'user_message'
  | 'agent_response_start'
  | 'tool_call_start'
  | 'tool_response'
  | 'assistant_response_start'
  | 'assistant_response_complete'
  | 'agent_response_complete';

export type InnerLoopEvent =
  | 'reasoning_stream'
  | 'tool_generation'
  | 'content_stream'
  | 'content_delta';

export type TechnicalEvent =
  | 'message_part_render'
  | 'sse_chunk'
  | 'api_request'
  | 'api_response'
  | 'frontend_stream_start'
  | 'frontend_stream_chunk'
  | 'frontend_stream_complete'
  | 'ui_state_change';

interface LogContext {
  messageId?: string;
  toolName?: string;
  userId?: string;
  sessionId?: string;
  [key: string]: unknown;
}

class ChatLogger {
  private debugLevel: LogLevel;

  constructor() {
    this.debugLevel = (process.env.NEXT_PUBLIC_DEBUG_LEVEL as LogLevel) || 'basic';
  }

  private shouldLog(eventLevel: 'basic' | 'detailed' | 'verbose'): boolean {
    if (this.debugLevel === 'off') return false;

    const levels: Record<LogLevel, number> = {
      'off': 0,
      'basic': 1,
      'detailed': 2,
      'verbose': 3
    };

    const levelOrder: Record<string, number> = {
      'basic': 1,
      'detailed': 2,
      'verbose': 3
    };

    return levels[this.debugLevel] >= levelOrder[eventLevel];
  }

  private formatMessage(icon: string, event: string, message: string, context?: LogContext): string {
    const contextStr = context && Object.keys(context).length > 0
      ? ` [${Object.entries(context).map(([k, v]) => `${k}=${v}`).join(', ')}]`
      : '';

    return `${icon} ${event.toUpperCase()}: ${message}${contextStr}`;
  }

  /**
   * Outer Loop: Complete agent response cycle events
   */
  outerLoop(event: OuterLoopEvent, message: string, context?: LogContext): void {
    if (!this.shouldLog('basic')) return;

    const icons: Record<OuterLoopEvent, string> = {
      'user_message': '👤',
      'agent_response_start': '🚀',
      'tool_call_start': '🔧',
      'tool_response': '✅',
      'assistant_response_start': '📝',
      'assistant_response_complete': '✅',
      'agent_response_complete': '🏁'
    };

    console.log(this.formatMessage(icons[event], event, message, context));
  }

  /**
   * Inner Loop: LLM generation process events
   */
  innerLoop(event: InnerLoopEvent, message: string, context?: LogContext): void {
    if (!this.shouldLog('detailed')) return;

    const icons: Record<InnerLoopEvent, string> = {
      'reasoning_stream': '💭',
      'tool_generation': '🔄',
      'content_stream': '📄',
      'content_delta': '📝'
    };

    console.log(this.formatMessage(icons[event], event, message, context));
  }

  /**
   * Technical: Low-level debugging events
   */
  technical(event: TechnicalEvent, message: string, context?: LogContext): void {
    if (!this.shouldLog('verbose')) return;

    const icons: Record<TechnicalEvent, string> = {
      'message_part_render': '🔍',
      'sse_chunk': '📡',
      'api_request': '🌐',
      'api_response': '📨',
      'frontend_stream_start': '🎬',
      'frontend_stream_chunk': '📺',
      'frontend_stream_complete': '✅',
      'ui_state_change': '🎛️'
    };

    console.log(this.formatMessage(icons[event], event, message, context));
  }

  /**
   * Always logs regardless of level (for critical errors)
   */
  error(message: string, context?: LogContext): void {
    console.error(this.formatMessage('🚨', 'ERROR', message, context));
  }

  /**
   * Always logs backend type for debugging (useful at basic level)
   */
  backend(type: 'gateway' | 'local', message: string): void {
    if (!this.shouldLog('basic')) return;
    const icon = type === 'local' ? '🏠' : '🌐';
    console.log(this.formatMessage(icon, 'BACKEND', message));
  }

  /**
   * Get current debug level
   */
  getLevel(): LogLevel {
    return this.debugLevel;
  }

  /**
   * Set debug level programmatically (useful for testing)
   */
  setLevel(level: LogLevel): void {
    this.debugLevel = level;
  }
}

// Export singleton instance
export const logger = new ChatLogger();

// Export helper functions for common patterns
export const logOuterLoop = logger.outerLoop.bind(logger);
export const logInnerLoop = logger.innerLoop.bind(logger);
export const logTechnical = logger.technical.bind(logger);
export const logError = logger.error.bind(logger);
export const logBackend = logger.backend.bind(logger);