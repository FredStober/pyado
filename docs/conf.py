#!/usr/bin/env python
"""Sphinx configuration."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

project = "Pythonic Azure DevOps Interface"
author = "Fred Stober"
copyright = "2023, Fred Stober"  # noqa:A001
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
