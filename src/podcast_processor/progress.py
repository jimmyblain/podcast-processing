"""Invocation-scoped progress; presentation never owns workflow state or retries."""
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import threading
import time

from rich.console import Console
from rich.live import Live
from rich.text import Text

_listener: ContextVar[Callable[[str], None] | None] = ContextVar('progress_listener', default=None)


def progress(message: str) -> None:
    listener = _listener.get()
    if listener:
        listener(message)


@contextmanager
def terminal_progress(operation: str, source: Path) -> Iterator[None]:
    console = Console(stderr=True, markup=False, highlight=False)
    started = time.monotonic()
    stopped = threading.Event()
    lock = threading.Lock()
    current = ''
    live = Live(console=console, auto_refresh=False, transient=True) if console.is_terminal else None

    def elapsed() -> str:
        seconds = int(time.monotonic() - started)
        return f'{seconds // 60:02d}:{seconds % 60:02d} elapsed'

    def emit(message: str) -> None:
        nonlocal current
        with lock:
            if message == current:
                return
            current = message
            try:
                console.print(f'[{elapsed()}] {message}', soft_wrap=True)
                if live:
                    live.update(Text(f'{elapsed()} · {current}'), refresh=True)
            except OSError:
                # A closed progress pipe must not interrupt an accepted paid job.
                stopped.set()

    def heartbeat() -> None:
        while not stopped.wait(1 if live else 10):
            with lock:
                try:
                    if live:
                        live.update(Text(f'{elapsed()} · {current}'), refresh=True)
                    else:
                        console.print(f'[{elapsed()}] Still working: {current}', soft_wrap=True)
                except OSError:
                    return

    emit(f'Starting {operation}: {source.resolve()}')
    if live:
        live.start()
    token = _listener.set(emit)
    worker = threading.Thread(target=heartbeat, name='terminal-progress', daemon=True)
    worker.start()
    try:
        yield
    finally:
        _listener.reset(token)
        stopped.set()
        worker.join()
        if live:
            live.stop()
