"""
Simplified Messages class for managing LLM conversation history.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class Messages:
    """A simplified class for managing LLM conversation messages."""

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        add_date_and_time: bool = False,
    ):
        """
        Initialize the Messages instance.

        Args:
            system_prompt: Optional system prompt to add to the messages list
            user_prompt: Optional initial user prompt to add to the messages list
            add_date_and_time: If True, adds a message with current date and time
        """
        self.messages: List[Dict[str, Any]] = []

        if system_prompt:
            self.add_system_message(system_prompt)

        if add_date_and_time:
            self._add_date_time_message()

        if user_prompt:
            self.add_user_message(user_prompt)

    def _add_date_time_message(self):
        """Add a message with the current date and time."""
        now = datetime.now()
        day = now.day
        if 4 <= day <= 20 or 24 <= day <= 30:
            suffix = "th"
        else:
            suffix = ["st", "nd", "rd"][day % 10 - 1]

        date_str = now.strftime(f"%d{suffix} of %B %Y")
        time_str = now.strftime("%H:%M")
        date_time_message = f"Today is {date_str} and the current time is {time_str}."
        self.messages.append({"role": "system", "content": date_time_message})

    def add_system_message(self, content: str):
        """Add a system message to the messages list."""
        self.messages.append({"role": "system", "content": content})

    def add_user_message(self, content: str):
        """Add a user message to the messages list."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        """Add an assistant message to the messages list."""
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_call(self, tool_call: Dict[str, Any]):
        """
        Add a tool call to the latest assistant message or create a new one.

        Args:
            tool_call: The tool call dictionary with id, type, function, etc.
        """
        # Check if the latest message is an assistant message with tool_calls
        if (
            self.messages
            and self.messages[-1].get("role") == "assistant"
            and "tool_calls" in self.messages[-1]
        ):
            # Append to existing assistant message
            self.messages[-1]["tool_calls"].append(tool_call)
        else:
            # Create new assistant message with tool call
            assistant_message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [tool_call],
            }
            self.messages.append(assistant_message)

    def add_tool_calls(self, tool_calls):
        """
        Add multiple tool calls from ChatCompletionMessageFunctionToolCall objects.

        Args:
            tool_calls: A list of ChatCompletionMessageFunctionToolCall objects or a single object
        """
        # Handle single tool call or list of tool calls
        if not isinstance(tool_calls, list):
            tool_calls = [tool_calls]

        # Create assistant message with empty content and tool calls
        assistant_message = {"role": "assistant", "content": "", "tool_calls": []}

        for tool_call in tool_calls:
            tool_call_dict = {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            assistant_message["tool_calls"].append(tool_call_dict)

        self.messages.append(assistant_message)

    def add_tool_response(self, tool_call_id: str, content: str):
        """
        Add a tool response message.

        Args:
            tool_call_id: The ID of the tool call this response belongs to
            content: The response content
        """
        tool_message = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }
        self.messages.append(tool_message)

    def add_tool_responses(self, tool_responses: List[Dict[str, Any]]):
        """
        Add multiple tool responses to the conversation history.

        Args:
            tool_responses: List of tool response dictionaries with tool_call_id,
                           tool_response, and is_error fields
        """
        for response in tool_responses:
            tool_call_id = response.get("tool_call_id", "unknown")
            is_error = response.get("is_error", False)

            if is_error:
                content = f"Error: {response.get('error', 'Unknown error')}"
            else:
                tool_response = response.get("tool_response", {})
                # Simple content extraction
                if isinstance(tool_response, dict) and "content" in tool_response:
                    content_list = tool_response["content"]
                    if content_list and isinstance(content_list[0], dict):
                        content = content_list[0].get("text", str(tool_response))
                    else:
                        content = str(tool_response)
                else:
                    content = str(tool_response)

            self.add_tool_response(tool_call_id, content)

    def add_response_message(self, model_response):
        """
        Add a response message (ChatCompletionMessage) to the conversation.

        Args:
            model_response: A ChatCompletionMessage object with role, content, and potentially tool_calls
        """
        # If there are tool calls, use add_tool_calls
        if model_response.tool_calls:
            self.add_tool_calls(model_response.tool_calls)
            # If there's also content, update the message content
            if model_response.content:
                self.messages[-1]["content"] = model_response.content
        else:
            # No tool calls, just add content as assistant message
            self.add_assistant_message(model_response.content or "")

    def get_messages(self) -> List[Dict[str, Any]]:
        """Get the current messages list."""
        return self.messages

    def get_user_message(self) -> str:
        """Get the user message."""
        for message in reversed(self.messages):
            if message.get("role") == "user":
                return message.get("content") or ""
        return ""

    def has_pending_tool_calls(self) -> bool:
        """
        Check if the last message has tool calls that need execution.

        Returns:
            True if there are tool calls waiting for responses
        """
        if not self.messages:
            return False

        last_message = self.messages[-1]

        # Check if the last message is an assistant message with tool calls
        if last_message.get("role") == "assistant" and "tool_calls" in last_message:
            # Check if there are subsequent tool responses
            tool_call_ids = {tc.get("id") for tc in last_message["tool_calls"]}

            # Look for tool responses after this message
            for msg in reversed(self.messages):
                if (
                    msg.get("role") == "tool"
                    and msg.get("tool_call_id") in tool_call_ids
                ):
                    tool_call_ids.remove(msg.get("tool_call_id"))

            # If there are still unresponded tool call IDs, we have pending calls
            return len(tool_call_ids) > 0

        return False

    def get_pending_tool_calls(self) -> List[Dict[str, Any]]:
        """
        Get pending tool calls that need execution, formatted for MCPClient.call_tool().

        Returns:
            List of dictionaries with 'tool_name', 'arguments', and 'tool_call_id' keys
        """
        pending_calls = []

        if not self.messages:
            return pending_calls

        last_message = self.messages[-1]

        # Check if the last message is an assistant message with tool calls
        if last_message.get("role") == "assistant" and "tool_calls" in last_message:
            # Get tool call IDs that have responses
            responded_tool_call_ids = set()
            for msg in reversed(self.messages):
                if msg.get("role") == "tool" and msg.get("tool_call_id"):
                    responded_tool_call_ids.add(msg.get("tool_call_id"))

            # Find tool calls that don't have responses
            for tool_call in last_message["tool_calls"]:
                tool_call_id = tool_call.get("id")
                if tool_call_id not in responded_tool_call_ids:
                    function_info = tool_call.get("function", {})
                    tool_name = function_info.get("name")
                    arguments_str = function_info.get("arguments", "{}")

                    # Parse arguments JSON string to dict
                    import json

                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError:
                        arguments = {}

                    pending_calls.append(
                        {
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "tool_call_id": tool_call_id,
                        }
                    )

        return pending_calls

    def __str__(self) -> str:
        """Return messages in a simple, readable format."""
        if not self.messages:
            return "No messages"

        lines = []
        for i, message in enumerate(self.messages, 1):
            role = message.get("role", "unknown")
            content = message.get("content", "")

            # Handle tool calls in assistant messages
            if role == "assistant" and message.get("tool_calls"):
                lines.append(f"{i}. {role}: {content}")
                for j, tool_call in enumerate(message["tool_calls"], 1):
                    function_name = tool_call.get("function", {}).get("name", "unknown")
                    lines.append(f"   └─ Tool Call {j}: {function_name}")

            # Handle tool messages
            elif role == "tool":
                tool_call_id = message.get("tool_call_id", "unknown")
                # Truncate long content for readability
                if len(content) > 200:
                    content = content[:197] + "..."
                lines.append(f"{i}. {role} [{tool_call_id[:8]}...]: {content}")

            # Handle other message types
            else:
                # Truncate long content for readability
                if len(content) > 100:
                    content = content[:97] + "..."
                lines.append(f"{i}. {role}: {content}")

        return "\n".join(lines)


# Example usage
def example_usage():
    """Example of how to use the simplified Messages class."""
    # Create messages with system prompt
    messages = Messages(
        system_prompt="You are a helpful assistant.",
        user_prompt="Hello, how are you?",
        add_date_and_time=True,
    )

    # Add assistant response
    messages.add_assistant_message("I'm doing well, thank you!")

    # Add a tool call
    tool_call = {
        "id": "call_123",
        "type": "function",
        "function": {"name": "get_weather", "arguments": '{"location": "Paris"}'},
    }
    messages.add_tool_call(tool_call)

    # Add tool response
    messages.add_tool_response("call_123", "The weather in Paris is sunny, 22°C")

    print("Conversation:")
    print(messages)

    print(f"\nHas pending tool calls: {messages.has_pending_tool_calls()}")


if __name__ == "__main__":
    example_usage()
