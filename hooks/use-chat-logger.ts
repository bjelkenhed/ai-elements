/**
 * Custom hook for frontend chat logging
 * Provides structured logging for UI component interactions and state changes
 */

import { useEffect, useRef } from 'react';
import { logTechnical, logOuterLoop, logBackend, logger } from '@/lib/logger';
import { conversationLogger, addUserMessage, addAssistantMessage, addToolCall, addToolResponse } from '@/lib/conversation-logger';
import type { ChatRequestOptions, Message } from 'ai';

interface UseChatLoggerProps {
  messages: Message[];
  status: 'ready' | 'loading' | 'streaming' | 'submitted' | 'error';
  backendType: 'gateway' | 'local';
}

export function useChatLogger({ messages, status, backendType }: UseChatLoggerProps) {
  const previousMessagesLength = useRef(0);
  const previousStatus = useRef<string>('');
  const currentMessageId = useRef<string>('');

  // Log status changes
  useEffect(() => {
    if (status !== previousStatus.current) {
      logTechnical('ui_state_change', `Chat status changed: ${previousStatus.current} → ${status}`, {
        previousStatus: previousStatus.current,
        newStatus: status,
        messagesCount: messages.length
      });
      previousStatus.current = status;
    }
  }, [status, messages.length]);

  // Log new messages and message parts
  useEffect(() => {
    const newMessagesCount = messages.length - previousMessagesLength.current;

    if (newMessagesCount > 0) {
      // Debug: log what we're processing
      console.log(`🐛 Hook processing ${newMessagesCount} new messages. Debug level: ${logger.getLevel()}`);

      // Log new messages
      const newMessages = messages.slice(previousMessagesLength.current);

      // Debug: log the new messages structure
      newMessages.forEach((msg, i) => {
        console.log(`🐛 Message ${i}:`, {
          role: msg.role,
          content: msg.content?.slice(0, 50),
          toolInvocations: msg.toolInvocations?.length || 0,
          hasContent: !!msg.content,
          fullStructure: Object.keys(msg)
        });
        console.log(`🐛 Full message ${i}:`, JSON.stringify(msg, null, 2));
      });

      newMessages.forEach((message, index) => {
        const messageIndex = previousMessagesLength.current + index;

        if (message.role === 'user') {
          // Handle user message
          const textPart = (message as any).parts?.find((part: any) => part.type === 'text');
          const textContent = textPart?.text || message.content || '[Empty message]';

          // Add to conversation logger
          addUserMessage(textContent, {
            messageId: message.id,
            messageIndex,
            source: backendType
          });

        } else if (message.role === 'assistant') {
          // Extract text content from parts array
          const textPart = (message as any).parts?.find((part: any) => part.type === 'text');
          const textContent = textPart?.text;

          // Log final assistant response (outer loop) only if there's actual text content
          if (textContent) {
            logOuterLoop('assistant_response_complete', `Assistant response: ${textContent.slice(0, 50)}${textContent.length > 50 ? '...' : ''}`, {
              messageId: message.id,
              messageIndex,
              contentLength: textContent.length,
              source: backendType
            });

            // Add to conversation logger
            addAssistantMessage(textContent, {
              messageId: message.id,
              messageIndex,
              source: backendType
            });

            // Also log technical rendering info at verbose level
            logTechnical('message_part_render', `UI rendering assistant message`, {
              messageId: message.id,
              messageIndex,
              contentLength: textContent.length,
              source: backendType
            });
          }

          // Log tool calls from message parts (outer loop)
          const messageParts = (message as any).parts || [];
          messageParts.forEach((part: any, partIndex: number) => {
            if (part.type === 'tool-call') {
              logOuterLoop('tool_call_start', `Tool called: ${part.toolName || 'unknown'}`, {
                messageId: message.id,
                toolName: part.toolName,
                partIndex,
                args: part.args,
                source: backendType
              });

              // Add to conversation logger
              addToolCall(
                part.toolCallId || `tool_${Date.now()}_${partIndex}`,
                part.toolName || 'unknown',
                part.args || part.input || {},
                {
                  messageId: message.id,
                  toolName: part.toolName,
                  source: backendType
                }
              );

              // Also log technical rendering info at verbose level
              logTechnical('message_part_render', `UI rendering tool call: ${part.toolName}`, {
                messageId: message.id,
                toolName: part.toolName,
                partIndex,
                source: backendType
              });
            } else if (part.type === 'tool-result' || part.type === 'tool-response') {
              logOuterLoop('tool_response', `Tool completed: ${part.toolName || 'unknown'}`, {
                messageId: message.id,
                toolName: part.toolName,
                partIndex,
                hasResult: !!part.result,
                source: backendType
              });

              // Add to conversation logger
              addToolResponse(
                part.toolCallId || `tool_${Date.now()}_${partIndex}`,
                typeof part.result === 'string' ? part.result : JSON.stringify(part.result || part.output || 'No result'),
                part.toolName || 'unknown',
                {
                  messageId: message.id,
                  toolName: part.toolName,
                  source: backendType
                }
              );

              // Also log technical rendering info at verbose level
              logTechnical('message_part_render', `UI rendering tool result: ${part.toolName}`, {
                messageId: message.id,
                toolName: part.toolName,
                partIndex,
                source: backendType
              });
            }
          });
        }
      });

      previousMessagesLength.current = messages.length;
    }
  }, [messages, backendType]);

  // Helper function to log user interactions
  const logUserInteraction = (action: string, details?: Record<string, unknown>) => {
    logTechnical('ui_state_change', `User interaction: ${action}`, {
      action,
      timestamp: Date.now(),
      backendType,
      ...details
    });
  };

  // Helper function to log form submissions
  const logMessageSubmission = (messageContent: string, options?: ChatRequestOptions) => {
    logOuterLoop('user_message', `UI submitting message: ${messageContent.slice(0, 50)}${messageContent.length > 50 ? '...' : ''}`, {
      contentLength: messageContent.length,
      hasAttachments: !!(options?.body as any)?.files?.length,
      model: (options?.body as any)?.model,
      webSearch: (options?.body as any)?.webSearch,
      backendType
    });

    // Note: User message will be added to conversation logger when it appears in the messages array during processing

    logBackend(backendType, `UI using ${backendType} backend for message submission`);
  };

  // Helper function to log backend switching
  const logBackendSwitch = (newBackendType: 'gateway' | 'local') => {
    logTechnical('ui_state_change', `UI switching backend: ${backendType} → ${newBackendType}`, {
      previousBackend: backendType,
      newBackend: newBackendType
    });
  };

  return {
    logUserInteraction,
    logMessageSubmission,
    logBackendSwitch
  };
}

export default useChatLogger;