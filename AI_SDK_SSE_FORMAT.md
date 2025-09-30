# AI SDK SSE Format Requirements for useChat Compatibility

## Overview
This document specifies the exact Server-Sent Events (SSE) format that AI SDK's `useChat` hook expects. Use this as a reference to make the Agent's `.run_stream_sse()` implementation compatible.

## Required HTTP Headers
```
Content-Type: text/plain; charset=utf-8
Cache-Control: no-cache
Connection: keep-alive
x-vercel-ai-ui-message-stream: v1
```

## SSE Format Structure
Every event must follow this format:
```
data: {JSON_OBJECT}

```
- Each line starts with `data: `
- Followed by a JSON object
- Ends with two newlines (`\n\n`)

## Required Event Sequence

### 1. Stream Start
```
data: {"type":"start","messageId":"msg_12345"}

```

### 2. Step Start (Optional)
```
data: {"type":"start-step"}

```

### 3. Tool Calls (if any)

#### Tool Input Start
```
data: {"type":"tool-input-start","toolCallId":"call_abc123","toolName":"add"}

```

#### Tool Input Delta (character by character)
```
data: {"type":"tool-input-delta","toolCallId":"call_abc123","inputTextDelta":"{"}

data: {"type":"tool-input-delta","toolCallId":"call_abc123","inputTextDelta":"\""}

data: {"type":"tool-input-delta","toolCallId":"call_abc123","inputTextDelta":"a"}

...
```

#### Tool Input Available (complete arguments)
```
data: {"type":"tool-input-available","toolCallId":"call_abc123","toolName":"add","input":{"a":3,"b":4}}

```

#### Tool Output Available (execution result)
```
data: {"type":"tool-output-available","toolCallId":"call_abc123","output":{"status":"success","text":"The sum of 3 + 4 = 7","result":7}}

```

### 4. Text Response

#### Text Start
```
data: {"type":"text-start","id":"txt-12345"}

```

#### Text Delta (character by character)
```
data: {"type":"text-delta","id":"txt-12345","delta":"The"}

data: {"type":"text-delta","id":"txt-12345","delta":" answer"}

data: {"type":"text-delta","id":"txt-12345","delta":" is"}

data: {"type":"text-delta","id":"txt-12345","delta":" 7"}

data: {"type":"text-delta","id":"txt-12345","delta":"."}

```

#### Text End
```
data: {"type":"text-end","id":"txt-12345"}

```

### 5. Step End (Optional)
```
data: {"type":"finish-step"}

```

### 6. Stream End
```
data: {"type":"finish"}

data: [DONE]

```

## Current Agent Output vs Required Format

### ❌ Current Agent Format (Incorrect)
```
{"type":"start"}{"type":"start-step"}{"type":"finish-step"}{"type":"start-step"}{"type":"tool-input-start","toolCallId":"call_af8491148e254687875c06","toolName":"add"}{"type":"tool-input-delta","toolCallId":"call_af8491148e254687875c06","inputTextDelta":"{\"a\":3,\"b\":4}"}{"type":"tool-input-available","toolCallId":"call_af8491148e254687875c06","toolName":"add","input":{"a":3,"b":4}}{"type":"tool-output-available","toolCallId":"call_af8491148e254687875c06","output":{"status":"loading","text":"Executing add..."},"preliminary":true}{"type":"tool-output-available","toolCallId":"call_af8491148e254687875c06","output":{"status":"success","text":"Tool execution completed","result":7.0},"preliminary":false}{"type":"finish-step"}{"type":"start-step"}{"type":"finish-step"}{"type":"start-step"}{"type":"text-start","id":"txt-90a0d80b"}{"type":"text-delta","id":"txt-90a0d80b","delta":"3"}{"type":"text-delta","id":"txt-90a0d80b","delta":" plus"}{"type":"text-delta","id":"txt-90a0d80b","delta":" "}{"type":"text-delta","id":"txt-90a0d80b","delta":"4"}{"type":"text-delta","id":"txt-90a0d80b","delta":" is"}{"type":"text-delta","id":"txt-90a0d80b","delta":" "}{"type":"text-delta","id":"txt-90a0d80b","delta":"7"}{"type":"text-delta","id":"txt-90a0d80b","delta":"."}{"type":"text-end","id":"txt-90a0d80b"}{"type":"finish-step"}{"type":"finish"}[DONE]
```

### ✅ Required AI SDK Format (Correct)
```
data: {"type":"start"}

data: {"type":"start-step"}

data: {"type":"tool-input-start","toolCallId":"chatcmpl-tool-531cfffa5e394e9ab4315af035451909","toolName":"add"}

data: {"type":"tool-input-delta","toolCallId":"chatcmpl-tool-531cfffa5e394e9ab4315af035451909","inputTextDelta":"{\"a\": 3"}

data: {"type":"tool-input-delta","toolCallId":"chatcmpl-tool-531cfffa5e394e9ab4315af035451909","inputTextDelta":", \"b\": 4}"}

data: {"type":"tool-input-available","toolCallId":"chatcmpl-tool-531cfffa5e394e9ab4315af035451909","toolName":"add","input":{"a":3,"b":4}}

data: {"type":"tool-output-available","toolCallId":"chatcmpl-tool-531cfffa5e394e9ab4315af035451909","output":{"status":"loading","text":"Adding 3 + 4..."},"preliminary":true}

data: {"type":"tool-output-available","toolCallId":"chatcmpl-tool-531cfffa5e294e9ab4315af035451909","output":{"status":"success","text":"The sum of 3 + 4 = 7","result":7},"preliminary":true}

data: {"type":"tool-output-available","toolCallId":"chatcmpl-tool-531cfffa5e394e9ab4315af035451909","output":{"status":"success","text":"The sum of 3 + 4 = 7","result":7}}

data: {"type":"finish-step"}

data: {"type":"start-step"}

data: {"type":"text-start","id":"txt-0"}

data: {"type":"text-delta","id":"txt-0","delta":"The"}

data: {"type":"text-delta","id":"txt-0","delta":" sum"}

data: {"type":"text-delta","id":"txt-0","delta":" of"}

data: {"type":"text-delta","id":"txt-0","delta":" "}

data: {"type":"text-delta","id":"txt-0","delta":"3"}

data: {"type":"text-delta","id":"txt-0","delta":" plus"}

data: {"type":"text-delta","id":"txt-0","delta":" "}

data: {"type":"text-delta","id":"txt-0","delta":"4"}

data: {"type":"text-delta","id":"txt-0","delta":" is"}

data: {"type":"text-delta","id":"txt-0","delta":" "}

data: {"type":"text-delta","id":"txt-0","delta":"7"}

data: {"type":"text-delta","id":"txt-0","delta":"."}

data: {"type":"text-end","id":"txt-0"}

data: {"type":"finish-step"}

data: {"type":"finish"}

data: [DONE]

```

## Key Differences to Fix

1. **Missing `data: ` prefix**: Every line must start with `data: `
2. **Missing newlines**: Each event must end with `\n\n`
3. **Missing messageId**: Start event should include unique message ID (optional but recommended)
4. **Concatenated events**: Events are currently concatenated without proper separation
5. **Tool output text mismatch**: Agent says "Executing add..." vs AI Gateway says "Adding 3 + 4..."
6. **Tool output final message**: Agent says "Tool execution completed" vs AI Gateway says "The sum of 3 + 4 = 7"

## Critical Fixes Needed

### 1. Fix SSE Formatting in Agent
The Agent's `run_stream_sse()` method needs to:
- Add `data: ` prefix to each event
- Add `\n\n` after each event
- NOT concatenate events

### 2. HTTP Headers Required
FastAPI endpoint must add:
```python
headers = {
    "x-vercel-ai-ui-message-stream": "v1",
    "Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive"
}
```

### 3. Tool Output Message Matching
Agent should output tool messages that match AI Gateway:
- Loading: `"Adding {a} + {b}..."`
- Success: `"The sum of {a} + {b} = {result}"`
- Not generic "Executing" and "Tool execution completed"

## Event Type Reference

| AI SDK Event Type | Required Fields | Purpose |
|------------------|----------------|---------|
| `start` | `messageId` | Initialize message stream |
| `start-step` | none | Begin processing step |
| `tool-input-start` | `toolCallId`, `toolName` | Tool execution begins |
| `tool-input-delta` | `toolCallId`, `inputTextDelta` | Tool arguments streaming |
| `tool-input-available` | `toolCallId`, `toolName`, `input` | Complete tool arguments |
| `tool-output-available` | `toolCallId`, `output` | Tool execution result |
| `text-start` | `id` | Text response begins |
| `text-delta` | `id`, `delta` | Text content streaming |
| `text-end` | `id` | Text response complete |
| `finish-step` | none | Processing step complete |
| `finish` | none | Stream complete |

## Implementation Notes

1. **Message ID Generation**: Use UUID format like `msg_${uuid()}`
2. **Text ID Generation**: Use format like `txt-${randomId}`
3. **Tool Call IDs**: Preserve original IDs from tool system
4. **Character-by-character streaming**: Both tool inputs and text should stream character by character
5. **Proper JSON escaping**: Ensure all JSON is properly escaped in the data field

## Testing

To verify format compatibility, compare output with working AI Gateway:
```bash
curl -X POST "http://localhost:3000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"id": "test", "role": "user", "parts": [{"type": "text", "text": "What is 3 plus 4?"}]}], "model": "openai/gpt-4o", "webSearch": false}' \
  --no-buffer
```

The FastAPI endpoint should produce identical format to ensure UI compatibility.