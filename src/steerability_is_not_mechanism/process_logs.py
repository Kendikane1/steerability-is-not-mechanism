"""Drain worker output through EOF before a supervisor records its checksum."""

from pathlib import Path
from threading import Thread
from typing import IO


class ProcessLog:
    """The reader owns the log; EOF includes descendants inheriting the output pipe."""

    def __init__(self, stream: IO[bytes], path: Path):
        self.error: BaseException | None = None
        self.thread = Thread(target=self._drain, args=(stream, path), daemon=True)
        self.thread.start()

    def _drain(self, stream: IO[bytes], path: Path) -> None:
        try:
            with stream, path.open("xb") as log:
                while block := stream.read(8192):
                    log.write(block)
        except BaseException as error:
            self.error = error

    def finish(self, timeout: float = 15) -> None:
        self.thread.join(timeout)
        if self.thread.is_alive():
            raise TimeoutError("worker output has not reached EOF; do not hash this log")
        if self.error is not None:
            raise RuntimeError("worker log capture failed") from self.error
