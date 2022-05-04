from ddtrace import patch_all

patch_all()

from .logs import *  # noqa: F403, E402, F401
