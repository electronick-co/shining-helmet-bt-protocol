"""shining_helmet — control SLShining / 'Shining Display' BLE LED-matrix helmets.

48x12 RGB matrix, JieLi chipset. Display channel is unauthenticated.

    from shining_helmet import ShiningHelmet, protocol, constants
"""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

from . import constants, protocol  # noqa: F401
from .client import ShiningHelmet  # noqa: F401

try:
    # Single source of truth is pyproject.toml; read it back from the installed
    # distribution so the two can never drift.
    __version__ = _pkg_version("shining-helmet")
except PackageNotFoundError:  # running from a source checkout, not installed
    __version__ = "0.0.0+unknown"
__all__ = ["ShiningHelmet", "protocol", "constants"]
