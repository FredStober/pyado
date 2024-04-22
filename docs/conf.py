"""Sphinx configuration."""

project = "Pythonic Azure DevOps Interface"
author = "Fred Stober"
copyright = "2023, Fred Stober"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
