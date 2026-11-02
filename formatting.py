"""Treat AI and document strings as text rather than executable Markdown."""
import re


def escape_text(value):
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~<>-])', r'\\\1', str(value))
