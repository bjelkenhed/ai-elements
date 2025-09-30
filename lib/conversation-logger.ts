/**
 * Conversation Logger for tracking complete chat conversations in OpenAI format
 * Maintains conversation state showing the progression through outer loop events:
 * user messages -> tool calls -> tool responses -> assistant messages
 */

export type LogLevel = 'off' | 'basic' | 'detailed' | 'verbose';

export interface ConversationMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content?: string;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: {
      name: string;
      arguments: string;
    };
  }>;
  tool_call_id?: string;
  name?: string;
}

interface LogContext {
  messageId?: string;
  toolName?: string;
  sessionId?: string;
  source?: string;
  [key: string]: unknown;
}

export class ConversationLogger {
  private conversation: ConversationMessage[] = [];
  private debugLevel: LogLevel;
  private sessionId: string;

  constructor(sessionId?: string) {
    this.debugLevel = (process.env.NEXT_PUBLIC_DEBUG_LEVEL as LogLevel) || 'basic';
    this.sessionId = sessionId || `session_${Date.now()}`;

    // Initialize with system message if not present
    this.addSystemMessage('You are a helpful assistant that can perform mathematical calculations and other tasks.');
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

  addSystemMessage(content: string): void {
    // Only add if no system message exists
    if (this.conversation.length === 0 || this.conversation[0].role !== 'system') {
      this.conversation.unshift({
        role: 'system',
        content: content
      });
    }
  }

  addUserMessage(content: string, context?: LogContext): void {
    this.conversation.push({
      role: 'user',
      content: content
    });

    if (this.shouldLog('basic')) {
      this.logConversationState('User message added', context);
    }
  }

  addAssistantMessage(content: string, context?: LogContext): void {
    this.conversation.push({
      role: 'assistant',
      content: content
    });

    if (this.shouldLog('basic')) {
      this.logConversationState('Assistant response completed', context);
    }
  }

  addToolCall(toolCallId: string, toolName: string, args: any, context?: LogContext): void {
    // Find the last assistant message and add tool_calls to it, or create new assistant message
    const lastMessage = this.conversation[this.conversation.length - 1];

    if (lastMessage && lastMessage.role === 'assistant' && !lastMessage.content) {
      // Add tool call to existing assistant message
      if (!lastMessage.tool_calls) {
        lastMessage.tool_calls = [];
      }
      lastMessage.tool_calls.push({
        id: toolCallId,
        type: 'function',
        function: {
          name: toolName,
          arguments: typeof args === 'string' ? args : JSON.stringify(args)
        }
      });
    } else {
      // Create new assistant message with tool call
      this.conversation.push({
        role: 'assistant',
        content: '',
        tool_calls: [{
          id: toolCallId,
          type: 'function',
          function: {
            name: toolName,
            arguments: typeof args === 'string' ? args : JSON.stringify(args)
          }
        }]
      });
    }

    if (this.shouldLog('detailed')) {
      this.logConversationState(`Tool call added: ${toolName}`, { ...context, toolName, toolCallId });
    }
  }

  addToolResponse(toolCallId: string, content: string, toolName?: string, context?: LogContext): void {
    this.conversation.push({
      role: 'tool',
      tool_call_id: toolCallId,
      content: content,
      name: toolName
    });

    if (this.shouldLog('detailed')) {
      this.logConversationState(`Tool response added: ${toolName || 'unknown'}`, { ...context, toolName, toolCallId });
    }
  }

  getConversationState(): ConversationMessage[] {
    return [...this.conversation];
  }

  getConversationLength(): number {
    return this.conversation.length;
  }

  clearConversation(): void {
    this.conversation = [];
    this.addSystemMessage('You are a helpful assistant that can perform mathematical calculations and other tasks.');
  }

  logConversationState(event: string, context?: LogContext): void {
    if (!this.shouldLog('basic')) return;

    const contextStr = context && Object.keys(context).length > 0
      ? ` [${Object.entries(context).map(([k, v]) => `${k}=${v}`).join(', ')}]`
      : '';

    console.log(`🔄 CONVERSATION_STATE: ${event}${contextStr}`);
    console.log('📝 Current conversation:', JSON.stringify(this.conversation, null, 2));
  }

  getDebugLevel(): LogLevel {
    return this.debugLevel;
  }

  setDebugLevel(level: LogLevel): void {
    this.debugLevel = level;
  }
}

// Export singleton instance for global conversation tracking
export const conversationLogger = new ConversationLogger();

// Export helper functions for common patterns
export const addUserMessage = conversationLogger.addUserMessage.bind(conversationLogger);
export const addAssistantMessage = conversationLogger.addAssistantMessage.bind(conversationLogger);
export const addToolCall = conversationLogger.addToolCall.bind(conversationLogger);
export const addToolResponse = conversationLogger.addToolResponse.bind(conversationLogger);
export const logConversationState = conversationLogger.logConversationState.bind(conversationLogger);
export const getConversationState = conversationLogger.getConversationState.bind(conversationLogger);