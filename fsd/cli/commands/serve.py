"""FSD web server command."""

import click
from rich.console import Console

console = Console()


@click.command()
@click.option(
    "--host",
    "-h",
    default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1)",
)
@click.option(
    "--port",
    "-p",
    default=10010,
    type=int,
    help="Port to bind to (default: 10010)",
)
@click.option(
    "--reload",
    "-r",
    is_flag=True,
    help="Enable auto-reload for development",
)
def serve_command(host: str, port: int, reload: bool) -> None:
    """Start the FSD web interface.

    Launches a web server that provides a visual interface for monitoring
    and managing FSD tasks, queue status, and system activity.

    Examples:
        fsd serve                    # Start on http://127.0.0.1:10010
        fsd serve --port 3000        # Start on custom port
        fsd serve --host 0.0.0.0     # Allow external connections
        fsd serve --reload           # Enable auto-reload for development
    """
    try:
        console.print(f"[blue]Starting FSD Web Server...[/blue]")
        console.print(f"[dim]Host:[/dim] {host}")
        console.print(f"[dim]Port:[/dim] {port}")
        console.print()
        console.print(f"[green]✓[/green] Web interface available at: http://{host}:{port}")
        console.print(f"[green]✓[/green] API documentation at: http://{host}:{port}/docs")
        console.print()
        console.print("[dim]Press Ctrl+C to stop the server[/dim]")
        console.print()

        from fsd.web.server import run_server

        run_server(host=host, port=port, reload=reload)

    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    except ImportError as e:
        console.print(f"[red]Failed to import web server dependencies:[/red] {e}")
        console.print("[yellow]Make sure FastAPI and uvicorn are installed:[/yellow]")
        console.print("  pip install 'fastapi>=0.104.0' 'uvicorn[standard]>=0.24.0'")
        raise click.ClickException("Web server dependencies not installed")
    except Exception as e:
        console.print(f"[red]Failed to start web server:[/red] {e}")
        raise click.ClickException(f"Server start failed: {e}")
