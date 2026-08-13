"""shining_helmet — control SLShining / 'Shining Display' BLE LED-matrix helmets.

48x12 RGB matrix, JieLi chipset. Display channel is unauthenticated.

    from shining_helmet import ShiningHelmet, protocol, constants
"""
from . import constants, protocol  # noqa: F401
from .client import ShiningHelmet  # noqa: F401

__version__ = "0.1.0"
__all__ = ["ShiningHelmet", "protocol", "constants"]
