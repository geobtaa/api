from __future__ import annotations

from dataclasses import dataclass

from .analytics import CommandAnalytics
from .client import BtaaApiClient
from .config import CliConfig


@dataclass
class Runtime:
    config: CliConfig
    client: BtaaApiClient
    analytics: CommandAnalytics
