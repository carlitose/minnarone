"""Nominal compatibility exports for the former read-only router names.

The runtime now constructs the platform-neutral router with an explicit policy
and typed target. These aliases preserve imports and ``isinstance`` checks, not
the retired ``video_id=...`` constructor signature.
"""

from .public_router import PublicOutputRouter
from .public_send import SendDecision as YouTubeShadowDecision

YouTubeShadowOutputRouter = PublicOutputRouter

__all__ = ["YouTubeShadowDecision", "YouTubeShadowOutputRouter"]
