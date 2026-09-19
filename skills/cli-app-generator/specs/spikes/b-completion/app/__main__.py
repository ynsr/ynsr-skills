import os
import typer

app = typer.Typer(add_completion=False)

ITEMS_DIR = os.environ.get("SPIKE_ITEMS_DIR", os.path.expanduser("~/.config/spike-items"))

def complete_item(incomplete: str):
    try:
        names = sorted(os.listdir(ITEMS_DIR))
    except OSError:
        return []
    # lazy: read a small state file only when needed
    return [n for n in names if n.startswith(incomplete)]

@app.command()
def items(arg: str = typer.Argument(None, autocompletion=complete_item),
          opt: str = typer.Option(None, "--pick", autocompletion=complete_item)):
    """List items, optionally picking one."""
    print(arg or "", opt or "")

@app.command()
def show(key: str = typer.Argument(None, autocompletion=complete_item)):
    """Show a single key."""
    print(key or "")

if __name__ == "__main__":
    app()
