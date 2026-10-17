"""Run bookman-tui with half-block covers, for the VHS recording.

VHS's terminal answers that it supports sixel, but sixel images don't appear
in the recording, so every cover would come out blank. Failing
textual-image's terminal queries before it picks a renderer makes it fall
back to half-block characters, which record like any other text.
"""

from contextlib import contextmanager

import textual_image._terminal as terminal


@contextmanager
def _no_answer(*args, **kwargs):
    raise TimeoutError("demo: graphics protocols off")
    yield


terminal.capture_terminal_response = _no_answer

from bookman_tui import main  # noqa: E402

main()
