# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from .base import HttpScraper
from .generic_http import GenericHttpScraper
from .sapumu_content import SapumuContentScraper

__all__ = ["HttpScraper", "GenericHttpScraper", "SapumuContentScraper"]
