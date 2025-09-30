'use client';

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation';
import { Message, MessageContent } from '@/components/ai-elements/message';
import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputAttachment,
  PromptInputAttachments,
  PromptInputBody,
  PromptInputButton,
  type PromptInputMessage,
  PromptInputModelSelect,
  PromptInputModelSelectContent,
  PromptInputModelSelectItem,
  PromptInputModelSelectTrigger,
  PromptInputModelSelectValue,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
  PromptInputTools,
} from '@/components/ai-elements/prompt-input';
import {
  Actions,
  Action,
  ActionsContent,
} from '@/components/ai-elements/actions';
import {
  Tool,
  ToolHeader,
  ToolContent,
  ToolInput,
  ToolOutput,
} from '@/components/ai-elements/tool';
import { useState, Fragment } from 'react';
import { useChat } from '@ai-sdk/react';
import { getApiUrl, getChatConfig } from '@/lib/chat-config';
import { Response } from '@/components/ai-elements/response';
import { useChatLogger } from '@/hooks/use-chat-logger';
import { GlobeIcon, RefreshCcwIcon, CopyIcon } from 'lucide-react';
import {
  Source,
  Sources,
  SourcesContent,
  SourcesTrigger,
} from '@/components/ai-elements/sources';
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from '@/components/ai-elements/reasoning';
import { Loader } from '@/components/ai-elements/loader';

const models = [
  {
    name: 'Qwen3-235b',
    value: 'alibaba/qwen-3-235b',
  },
  {
    name: 'Qwen3-Next-80B-A3B-Thinking',
    value: 'alibaba/qwen3-next-80b-a3b-thinking',
  },
];



const AIChat = () => {
  const [input, setInput] = useState('');
  const [model, setModel] = useState<string>(models[0].value);
  const [webSearch, setWebSearch] = useState(false);
  const [toolCalls, setToolCalls] = useState<Array<{
    toolCallId: string;
    toolName: string;
    state: string;
    input?: unknown;
    output?: unknown;
    errorText?: string;
  }>>([]);

  const chatConfig = getChatConfig();
  const { messages, sendMessage, status } = useChat({
    api: '/api/chat',
    onError: (error) => {
      console.error('🚨 useChat error:', error);
    }
  });

  // Frontend logging for UI interactions and state changes
  const { logUserInteraction, logMessageSubmission, logBackendSwitch } = useChatLogger({
    messages,
    status,
    backendType: chatConfig.backendType
  });

  const handleSubmit = async (message: PromptInputMessage) => {
    const hasText = Boolean(message.text);
    const hasAttachments = Boolean(message.files?.length);

    if (!(hasText || hasAttachments)) {
      return;
    }

    const requestOptions = {
      body: {
        model: model,
        webSearch: webSearch,
        _endpoint: chatConfig.backendType === 'local' ? getApiUrl() : undefined,
      },
    };

    // Log message submission with frontend logging
    logMessageSubmission(message.text || 'Message with attachments', requestOptions);

    // Clear previous tool calls
    setToolCalls([]);

    // Use the regular sendMessage
    sendMessage(
      {
        text: message.text || 'Sent with attachments',
        files: message.files
      },
      requestOptions,
    );
    setInput('');
  };

  return (
    <div className="max-w-4xl mx-auto p-6 relative size-full h-screen">
      {/* Backend indicator */}
      <div className="absolute top-2 right-2 z-10">
        <div className={`px-2 py-1 text-xs rounded-md ${
          chatConfig.backendType === 'local'
            ? 'bg-green-100 text-green-800 border border-green-200'
            : 'bg-blue-100 text-blue-800 border border-blue-200'
        }`}>
          {chatConfig.backendType === 'local' ? 'Local FastAPI' : 'AI Gateway'}
        </div>
      </div>

      <div className="flex flex-col h-full">
        <Conversation className="h-full">
          <ConversationContent>
            {messages.map((message) => {

              return (
                <div key={message.id}>
                {message.role === 'assistant' && message.parts.filter((part) => part.type === 'source-url').length > 0 && (
                  <Sources>
                    <SourcesTrigger
                      count={
                        message.parts.filter(
                          (part) => part.type === 'source-url',
                        ).length
                      }
                    />
                    {message.parts.filter((part) => part.type === 'source-url').map((part, i) => (
                      <SourcesContent key={`${message.id}-${i}`}>
                        <Source
                          key={`${message.id}-${i}`}
                          href={part.url}
                          title={part.url}
                        />
                      </SourcesContent>
                    ))}
                  </Sources>
                )}

                {/* Display active tool calls */}
                {toolCalls.map((toolCall) => (
                  <Tool key={toolCall.toolCallId} className="mb-4">
                    <ToolHeader
                      type={toolCall.toolName}
                      state={toolCall.state}
                    />
                    <ToolContent>
                      {toolCall.input && (
                        <ToolInput input={toolCall.input} />
                      )}
                      {(toolCall.output || toolCall.errorText) && (
                        <ToolOutput
                          output={toolCall.output}
                          errorText={toolCall.errorText}
                        />
                      )}
                    </ToolContent>
                  </Tool>
                ))}
                {message.parts.map((part, i) => {
                  switch (part.type) {
                    case 'text':
                      return (
                        <Fragment key={`${message.id}-${i}`}>
                          <Message from={message.role}>
                            <MessageContent>
                              <Response>
                                {part.text}
                              </Response>
                            </MessageContent>
                          </Message>
                          {message.role === 'assistant' && i === messages.length - 1 && (
                            <Actions className="mt-2">
                              <Action
                                onClick={() => window.location.reload()}
                                label="Retry"
                              >
                                <RefreshCcwIcon className="size-3" />
                              </Action>
                              <Action
                                onClick={() =>
                                  navigator.clipboard.writeText(part.text)
                                }
                                label="Copy"
                              >
                                <CopyIcon className="size-3" />
                              </Action>
                            </Actions>
                          )}
                        </Fragment>
                      );
                    case 'reasoning':
                      return (
                        <Reasoning
                          key={`${message.id}-${i}`}
                          className="w-full"
                          isStreaming={status === 'streaming' && i === message.parts.length - 1 && message.id === messages.at(-1)?.id}
                        >
                          <ReasoningTrigger />
                          <ReasoningContent>{part.text}</ReasoningContent>
                        </Reasoning>
                      );
                    case 'tool-call':
                      return (
                        <Tool key={`${message.id}-${i}`} className="mb-4">
                          <ToolHeader
                            type={part.toolName}
                            state={part.state}
                          />
                          <ToolContent>
                            {part.input && (
                              <ToolInput input={part.input} />
                            )}
                            {(part.output || part.errorText) && (
                              <ToolOutput
                                output={part.output}
                                errorText={part.errorText}
                              />
                            )}
                          </ToolContent>
                        </Tool>
                      );
                    default:
                      // Handle dynamic tool types from AI Gateway (e.g., 'tool-getWeather')
                      if (part.type && part.type.startsWith('tool-')) {
                        if ('state' in part) {
                          const toolPart = part as {
                            type: string;
                            state: string;
                            input?: unknown;
                            output?: unknown;
                            errorText?: string;
                          };
                          const toolName = part.type.replace('tool-', ''); // Extract tool name from type

                          return (
                            <Tool key={`${message.id}-${i}`} className="mb-4">
                              <ToolHeader
                                type={toolName as `tool-${string}`}
                                state={toolPart.state as "input-streaming" | "input-available" | "output-available" | "output-error"}
                              />
                              <ToolContent>
                                {toolPart.input && (
                                  <ToolInput input={toolPart.input as unknown} />
                                )}
                                {(toolPart.output || toolPart.errorText) && (
                                  <ToolOutput
                                    output={toolPart.output as unknown}
                                    errorText={toolPart.errorText}
                                  />
                                )}
                              </ToolContent>
                            </Tool>
                          );
                        }
                      }
                      return null;
                  }
                })}
                </div>
              );
            })}
            {status === 'submitted' && <Loader />}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        <PromptInput onSubmit={handleSubmit} className="mt-4" globalDrop multiple>
          <PromptInputBody>
            <PromptInputAttachments>
              {(attachment) => <PromptInputAttachment data={attachment} />}
            </PromptInputAttachments>
            <PromptInputTextarea
              onChange={(e) => setInput(e.target.value)}
              value={input}
            />
          </PromptInputBody>
          <PromptInputToolbar>
            <PromptInputTools>
              <PromptInputActionMenu>
                <PromptInputActionMenuTrigger />
                <PromptInputActionMenuContent>
                  <PromptInputActionAddAttachments />
                </PromptInputActionMenuContent>
              </PromptInputActionMenu>
              <PromptInputButton
                variant={webSearch ? 'default' : 'ghost'}
                onClick={() => {
                  const newWebSearchState = !webSearch;
                  setWebSearch(newWebSearchState);
                  logUserInteraction('web_search_toggle', {
                    webSearch: newWebSearchState,
                    model
                  });
                }}
              >
                <GlobeIcon size={16} />
                <span>Search</span>
              </PromptInputButton>
              <PromptInputModelSelect
                onValueChange={(value) => {
                  setModel(value);
                  logUserInteraction('model_change', {
                    previousModel: model,
                    newModel: value,
                    webSearch
                  });
                }}
                value={model}
              >
                <PromptInputModelSelectTrigger>
                  <PromptInputModelSelectValue />
                </PromptInputModelSelectTrigger>
                <PromptInputModelSelectContent>
                  {models.map((model) => (
                    <PromptInputModelSelectItem key={model.value} value={model.value}>
                      {model.name}
                    </PromptInputModelSelectItem>
                  ))}
                </PromptInputModelSelectContent>
              </PromptInputModelSelect>
            </PromptInputTools>
            <PromptInputSubmit disabled={!input && !status} status={status} />
          </PromptInputToolbar>
        </PromptInput>
      </div>
    </div>
  );
};

export default AIChat;