from typing import Callable, Any, Optional, Dict, Union
from rich.console import Group, Console
from rich.json import JSON
from rich.live import Live
from rich.markdown import Markdown
from rich.status import Status
from rich.text import Text
from rich.box import HEAVY
from rich.panel import Panel
from rich.syntax import Syntax


class RichLogger:
    """A Rich-based logger for agent steps with customizable tool formatters."""
    
    def __init__(self, console_width: int = 150):
        self.console_width = console_width
        self.tool_formatters: Dict[str, Callable] = {}
        self.tool_response_formatters: Dict[str, Callable] = {}
        self.panels = []
        self.live_log: Optional[Live] = None
        self._console = Console(width=console_width)
    
    def __enter__(self):
        """Start the live display context."""
        self.live_log = Live(console=self._console, auto_refresh=False)
        self.live_log.__enter__()
        self.panels = []
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End the live display context."""
        if self.live_log:
            self.live_log.__exit__(exc_type, exc_val, exc_tb)
            self.live_log = None
    
    def register_tool_formatter(self, tool_name: str, formatter: Callable[[dict], Any]):
        """Register a custom formatter for tool calls."""
        self.tool_formatters[tool_name] = formatter
    
    def register_tool_response_formatter(self, tool_name: str, formatter: Callable[[dict, Any], Any]):
        """Register a custom formatter for tool responses."""
        self.tool_response_formatters[tool_name] = formatter
    
    def tool_formatter(self, tool_name: str):
        """Decorator to register a tool formatter."""
        def decorator(func: Callable[[dict], Any]):
            self.register_tool_formatter(tool_name, func)
            return func
        return decorator
    
    def tool_response_formatter(self, tool_name: str):
        """Decorator to register a tool response formatter."""
        def decorator(func: Callable[[dict, Any], Any]):
            self.register_tool_response_formatter(tool_name, func)
            return func
        return decorator
    
    def _add_panel(self, panel: Panel):
        """Add a panel and refresh the display."""
        if not self.live_log:
            raise RuntimeError("RichLogger must be used as a context manager")
        
        self.panels.append(panel)
        self.live_log.update(Group(*self.panels))
        self.live_log.refresh()
    
    def _create_panel(self, content, title: str, border_style: str = "blue") -> Panel:
        """Create a Rich panel with consistent styling."""
        return Panel(
            content,
            title=title,
            title_align="left",
            border_style=border_style,
            box=HEAVY,
            expand=True,
            padding=(1, 1),
        )
    
    def _format_tool_call_default(self, tool_name: str, args: dict) -> Any:
        """Default formatter for tool calls."""
        if isinstance(args, dict):
            if len(args) == 0:
                return Text(f"{tool_name}()", style="bold cyan")
            
            # Create a nicely formatted representation
            args_parts = []
            for k, v in args.items():
                if isinstance(v, str) and len(v) > 50:
                    args_parts.append(f"{k}='{v[:47]}...'")
                else:
                    args_parts.append(f"{k}={repr(v)}")
            
            args_str = ", ".join(args_parts)
            if len(args_str) > 100:
                # For very long arguments, use JSON formatting
                return Group(
                    Text(f"{tool_name}(", style="bold cyan"),
                    JSON(args, indent=2),
                    Text(")", style="bold cyan")
                )
            else:
                return Text(f"{tool_name}({args_str})", style="bold cyan")
        else:
            return Text(f"{tool_name}({args})", style="bold cyan")
    
    def _format_tool_response_default(self, tool_name: str, response: Any) -> Any:
        """Default formatter for tool responses."""
        if isinstance(response, dict):
            import json
            return JSON(json.dumps(response), indent=2)
        elif isinstance(response, str):
            if len(response) > 500:
                return Text(f"{response[:497]}...", style="dim white")
            return Text(response, style="white")
        else:
            return Text(str(response), style="white")
    
    def status(self, message: str, spinner: str = "aesthetic"):
        """Display a status message with spinner."""
        status_obj = Status(message, spinner=spinner, speed=0.4)
        self.panels = [status_obj]  # Replace any existing content with status
        if self.live_log:
            self.live_log.update(status_obj)
            self.live_log.refresh()
    
    def user_message(self, content: str):
        """Display a user message panel."""
        panel = self._create_panel(
            content=Text(content, style="green"),
            title="Message",
            border_style="cyan"
        )
        self._add_panel(panel)
    
    def assistant_message(self, content: str):
        """Display an assistant message panel.""" 
        panel = self._create_panel(
            content=Text(content, style="bold blue"),
            title="Final Response",
            border_style="green"
        )
        self._add_panel(panel)
    
    def tool_call(self, tool_name: str, args: dict):
        """Display a tool call panel with automatic formatter dispatch."""
        # Check for custom formatter
        if tool_name in self.tool_formatters:
            content = self.tool_formatters[tool_name](args)
        else:
            content = self._format_tool_call_default(tool_name, args)
        
        panel = self._create_panel(
            content=content,
            title=f"🔧 {tool_name}",
            border_style="blue"
        )
        self._add_panel(panel)
    
    def tool_response(self, tool_name: str, response: Any):
        """Display a tool response panel with automatic formatter dispatch."""
        # Check for custom formatter
        if tool_name in self.tool_response_formatters:
            content = self.tool_response_formatters[tool_name]({}, response)
        else:
            content = self._format_tool_response_default(tool_name, response)
        
        panel = self._create_panel(
            content=content,
            title=f"📤 {tool_name} Result",
            border_style="green"
        )
        self._add_panel(panel)
    
    def custom_panel(self, content: Any, title: str, border_style: str = "blue"):
        """Display a custom panel with any content."""
        panel = self._create_panel(content, title, border_style)
        self._add_panel(panel)


# Convenience function for backwards compatibility
def create_panel(content, title, border_style="blue"):
    """Create a panel with the same signature as before."""
    return Panel(
        content,
        title=title,
        title_align="left",
        border_style=border_style,
        box=HEAVY,
        expand=True,
        padding=(1, 1),
    )


# Example usage and formatters
def create_think_formatter():
    """Create a formatter for think_tool that displays thoughts as Markdown."""
    def format_think(args: dict) -> Markdown:
        thoughts = args.get("thoughts", args.get("content", "Thinking..."))
        return Markdown(thoughts)
    return format_think


def create_code_formatter():
    """Create a formatter for code tools that displays syntax-highlighted code."""
    def format_code(args: dict) -> Syntax:
        code = args.get("code", args.get("content", ""))
        language = args.get("language", "python")
        return Syntax(code, language, theme="monokai", line_numbers=True)
    return format_code


def create_search_formatter():
    """Create a formatter for search tools that highlights the query."""
    def format_search(args: dict) -> Group:
        query = args.get("query", "")
        filters = args.get("filters", {})
        
        content = [Text("🔍 ", style="bold yellow")]
        content.append(Text(f"Query: {query}", style="bold white"))
        
        if filters:
            content.append(Text("\nFilters:", style="dim white"))
            content.append(JSON(filters, indent=2))
        
        return Group(*content)
    return format_search