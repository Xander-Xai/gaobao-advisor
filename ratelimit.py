"""
DEPRECATED: This module has been moved to server/middleware/ratelimit.py.
Please update imports to use the new location.
"""

import warnings

warnings.warn(
    "ratelimit.py has moved to server/middleware/ratelimit.py. Please update your imports.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from legacy module (which has the original TokenBucket and RateLimiter)
from legacy.ratelimit import RateLimiter, TokenBucket  # noqa: F401,E402
