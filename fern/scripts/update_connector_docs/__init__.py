"""Connector documentation generator package."""

from .constants import DOCS_CONNECTORS_DIR
from .generators.mdx_generator import generate_mdx_content
from .parsers.auth_parser import parse_auth_config
from .parsers.config_parser import parse_config_file
from .parsers.entity_parser import parse_entity_file
from .parsers.source_parser import parse_source_file
from .utils.file_utils import (
    copy_svg_icon,
    get_connectors_from_icons,
    get_connectors_from_sources,
    update_docs_yml,
    update_or_create_mdx,
)


__all__ = [
    "parse_entity_file",
    "parse_source_file",
    "parse_auth_config",
    "parse_config_file",
    "generate_mdx_content",
    "get_connectors_from_sources",
    "get_connectors_from_icons",
    "copy_svg_icon",
    "update_docs_yml",
    "update_or_create_mdx",
    "DOCS_CONNECTORS_DIR",
]
