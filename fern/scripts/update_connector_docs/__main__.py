"""Main entry point for the connector documentation generator."""

from .parsers.entity_parser import parse_entity_file
from .parsers.source_parser import parse_source_file
from .parsers.auth_parser import parse_auth_config
from .generators.mdx_generator import generate_mdx_content
from .utils.file_utils import (
    get_connectors_from_icons,
    copy_svg_icon,
    update_docs_yml,
    update_or_create_mdx,
)
from .constants import DOCS_CONNECTORS_DIR
import os


def main():
    """Generate documentation for connectors."""
    print("Starting connector documentation generation...")

    # Get list of connectors from SVG icons
    connectors = get_connectors_from_icons()
    print(f"Found {len(connectors)} connectors from icons")

    # Parse auth config file
    auth_configs = parse_auth_config()

    # Process each connector
    valid_connectors = []

    for connector_name in sorted(connectors):
        print(f"Processing connector: {connector_name}")

        # Parse entity and source files
        entity_info = parse_entity_file(connector_name)
        source_info = parse_source_file(connector_name)

        # Skip if no entity or source info is available
        if not entity_info and not source_info:
            print(f"  Skipping {connector_name} - no entity or source information found")
            continue

        valid_connectors.append(connector_name)

        # Generate MDX content
        mdx_content = generate_mdx_content(connector_name, entity_info, source_info, auth_configs)

        # Create connector docs directory and files
        connector_docs_dir = DOCS_CONNECTORS_DIR / connector_name

        # Create the directory if it doesn't exist
        os.makedirs(connector_docs_dir, exist_ok=True)

        # Copy SVG icon to connector directory
        copy_svg_icon(connector_name, connector_docs_dir)

        # Create or update main.mdx
        update_or_create_mdx(connector_name, connector_docs_dir, mdx_content)

    # Update the docs.yml file with the valid connectors
    update_docs_yml(valid_connectors)

    print(f"Generated documentation for {len(valid_connectors)} connectors")
    print("Connector documentation generation complete!")


if __name__ == "__main__":
    main()
