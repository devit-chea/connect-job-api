import inspect
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def log_sync_call_origin(func):
    """
    Utility function to log where sync call originated from.
    Helps trace unexpected or direct usage.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get the previous 3 stack frames
        stack = inspect.stack()
        origin_info = []
        for frame in stack[1:4]:  # skip the current frame
            origin_info.append(f"{frame.function} () at {frame.filename}:{frame.lineno}")

        logger.info(
            "[TRACE] Sync call origin:\n  - " + "\n  - ".join(origin_info)
        )
        return func(*args, **kwargs)

    return wrapper
