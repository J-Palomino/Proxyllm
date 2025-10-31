
# LiteLLM ASCII banner
LITELLM_BANNER = """   ██╗     ██╗████████╗███████╗██╗     ██╗     ███╗   ███╗
   ██║     ██║╚══██╔══╝██╔════╝██║     ██║     ████╗ ████║
   ██║     ██║   ██║   █████╗  ██║     ██║     ██╔████╔██║
   ██║     ██║   ██║   ██╔══╝  ██║     ██║     ██║╚██╔╝██║
   ███████╗██║   ██║   ███████╗███████╗███████╗██║ ╚═╝ ██║
   ╚══════╝╚═╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝     ╚═╝"""


def show_banner():
    """Display the LiteLLM CLI banner."""
    try:
      import click
      import sys
      # Use UTF-8 encoding to handle Unicode characters
      if hasattr(sys.stdout, 'reconfigure'):
        try:
          sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
          pass
      try:
        click.echo(f"\n{LITELLM_BANNER}\n")
      except UnicodeEncodeError:
        # Fallback to ASCII-safe banner if encoding fails
        click.echo("\n  LITELLM\n")
    except ImportError:
      print("\n") # noqa: T201