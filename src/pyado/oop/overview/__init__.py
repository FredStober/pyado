"""Overview section of the Azure DevOps OOP layer.

Exposes :class:`Dashboard` and :class:`Wiki` — resource wrappers for
ADO dashboards and wikis.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop.overview.dashboard import Dashboard
from pyado.oop.overview.wiki import Wiki

__all__ = ["Dashboard", "Wiki"]
