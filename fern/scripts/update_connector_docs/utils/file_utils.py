"""File utility functions for the connector documentation generator."""

import ast
import os
import shutil

import yaml

from ..constants import (
    BACKEND_SOURCES_DIR,
    CONTENT_END_MARKER,
    CONTENT_START_MARKER,
    DOCS_YML_PATH,
    FRONTEND_ICONS_DIR,
    REPO_ROOT,  # Add this import
)


def _is_internal_source(decorator_node):
    """Check if a @source decorator has internal=True.

    Args:
        decorator_node: AST node for the decorator

    Returns:
        bool: True if the decorator has internal=True
    """
    if not isinstance(decorator_node, ast.Call):
        return False

    for keyword in decorator_node.keywords:
        if keyword.arg == "internal" and isinstance(keyword.value, ast.Constant):
            return keyword.value.value is True

    return False


def get_connectors_from_sources():
    """Get list of connectors from source files by scanning for @source decorator.

    This is the improved approach that uses the actual source code as the source of truth
    instead of relying on icon files. Internal sources (those with `internal=True` in the
    @source decorator) are automatically excluded from documentation.

    Returns:
        list: List of connector names found in source files
    """
    connectors = []

    # Scan all Python files in the sources directory
    for source_file in BACKEND_SOURCES_DIR.glob("*.py"):
        # Skip __init__.py and _base.py
        if source_file.name in ["__init__.py", "_base.py"]:
            continue

        connector_name = source_file.stem

        try:
            with open(source_file, "r") as f:
                content = f.read()

            # Parse the Python file
            tree = ast.parse(content)

            # Look for classes with @source decorator that inherit from BaseSource
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it inherits from BaseSource
                    inherits_from_base_source = any(
                        isinstance(base, ast.Name) and base.id == "BaseSource"
                        for base in node.bases
                    )

                    if not inherits_from_base_source:
                        continue

                    # Find the @source decorator
                    source_decorator = None
                    for decorator in node.decorator_list:
                        if (
                            isinstance(decorator, ast.Call)
                            and isinstance(decorator.func, ast.Name)
                            and decorator.func.id == "source"
                        ) or (
                            isinstance(decorator, ast.Name)
                            and decorator.id == "source"
                        ):
                            source_decorator = decorator
                            break

                    if source_decorator is None:
                        continue

                    # Skip internal sources (internal=True in @source decorator)
                    if _is_internal_source(source_decorator):
                        print(f"  Skipping internal source: {connector_name}")
                        break

                    connectors.append(connector_name)
                    break  # Found one source class, move to next file

        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"  Warning: Could not parse {source_file}: {e}")
            continue

    return sorted(connectors)


def get_connectors_from_icons():
    """Get list of connectors from SVG icons (legacy method)."""
    connectors = []
    for svg_file in FRONTEND_ICONS_DIR.glob("*.svg"):
        connector_name = svg_file.stem
        # Skip light/dark variations
        if connector_name.endswith("-light") or connector_name.endswith("-dark"):
            base_name = connector_name.rsplit("-", 1)[0]
            if base_name not in connectors:
                connectors.append(base_name)
        else:
            if connector_name not in connectors:
                connectors.append(connector_name)
    return connectors


def copy_svg_icon(connector_name, connector_docs_dir):
    """Copy SVG icon to connector documentation directory.

    Now returns True/False to indicate success, and doesn't treat missing icons as errors.
    """
    # Look for the icon in the apps directory
    icon_path = None
    for icon_candidate in [f"{connector_name}.svg", f"{connector_name}-light.svg"]:
        source_path = FRONTEND_ICONS_DIR / icon_candidate
        if source_path.exists():
            icon_path = source_path
            break

    if not icon_path:
        print(f"  Info: No SVG icon found for {connector_name}, using placeholder")
        # Create a placeholder icon or skip icon creation
        return False

    # Copy icon to the connector directory
    dest_path = connector_docs_dir / "icon.svg"
    shutil.copy2(icon_path, dest_path)

    # Fix: Use REPO_ROOT for relative path calculation instead of Path.cwd()
    try:
        relative_dest = dest_path.relative_to(REPO_ROOT)
        print(f"  Copied {icon_path.name} to {relative_dest}")
    except ValueError:
        # Fallback to absolute path if relative calculation fails
        print(f"  Copied {icon_path.name} to {dest_path}")

    return True


def update_docs_yml(valid_connectors):
    """Update the docs.yml file with the connector list."""
    try:
        print(f"Reading docs.yml from: {DOCS_YML_PATH}")
        print(f"File exists: {DOCS_YML_PATH.exists()}")

        with open(DOCS_YML_PATH, "r") as f:
            docs_config = yaml.safe_load(f)

        print(f"Loaded YAML config with keys: {docs_config.keys()}")
        print(
            f"Navigation structure: {[item.get('section', item.get('api', 'unknown')) for item in docs_config['navigation']]}"
        )

        # Find the Docs section
        docs_section = None
        for i, section in enumerate(docs_config["navigation"]):
            print(f"  Section {i}: {section}")
            if (
                isinstance(section, dict)
                and "section" in section
                and section["section"] == "Docs"
            ):
                docs_section = section
                print(f"  Found Docs section at index {i}")
                break

        if not docs_section:
            print("Warning: Could not find 'Docs' section in navigation")
            print(
                "Available sections:",
                [s.get("section", s.get("api")) for s in docs_config["navigation"]],
            )
            return

        print(f"Docs section contents: {docs_section.get('contents', [])}")

        # Look for existing Connectors section
        connectors_section = None
        for i, item in enumerate(docs_section["contents"]):
            print(f"  Content item {i}: {item}")
            if (
                isinstance(item, dict)
                and "section" in item
                and item["section"] == "Connectors"
            ):
                connectors_section = item
                print(f"  Found existing Connectors section at index {i}")
                break

        # Create Connectors section if it doesn't exist
        if not connectors_section:
            connectors_section = {"section": "Connectors", "contents": []}
            docs_section["contents"].append(connectors_section)
            print("Created new 'Connectors' section in docs.yml")

        # Preserve manually added pages (like Overview) at the top
        preserved_pages = []
        for item in connectors_section.get("contents", []):
            if isinstance(item, dict) and "path" in item:
                # Keep pages that aren't auto-generated connector pages (e.g., overview.mdx)
                if not item["path"].endswith("/main.mdx"):
                    preserved_pages.append(item)

        # Clear existing connector list and rebuild with preserved pages first
        connectors_section["contents"] = preserved_pages

        # Add all auto-generated connectors
        for connector in sorted(valid_connectors):
            display_name = connector.replace("_", " ").title()
            connectors_section["contents"].append(
                {
                    "page": display_name,
                    "path": f"docs/pages/connectors/{connector}/main.mdx",
                }
            )

        print(f"Added {len(valid_connectors)} connectors to the section")
        print(f"Final connectors section: {connectors_section}")

        # Write back the updated config
        print(f"Writing back to: {DOCS_YML_PATH}")
        with open(DOCS_YML_PATH, "w") as f:
            yaml.dump(
                docs_config, f, default_flow_style=False, sort_keys=False, indent=2
            )

        print(f"Updated docs.yml with {len(valid_connectors)} connectors")

        # Verify the file was written
        print(f"File size after write: {DOCS_YML_PATH.stat().st_size} bytes")

    except Exception as e:
        print(f"Error updating docs.yml: {str(e)}")
        import traceback

        traceback.print_exc()


def update_or_create_mdx(connector_name, connector_docs_dir, mdx_content):
    """Create or update main.mdx file for a connector."""
    # Create connector docs directory if it doesn't exist
    os.makedirs(connector_docs_dir, exist_ok=True)

    # Create or update main.mdx
    main_mdx_path = connector_docs_dir / "main.mdx"

    # Format display name for frontmatter
    display_name = connector_name.replace("_", " ").title()

    # Add frontmatter
    frontmatter = f"""---
title: "{display_name}"
description: "{display_name} integration with Airweave"
---

"""

    if main_mdx_path.exists():
        # If file exists, preserve custom content and update only auto-generated part
        with open(main_mdx_path, "r") as f:
            existing_content = f.read()

        # Replace content between auto-generated markers
        start_index = existing_content.find(CONTENT_START_MARKER)
        end_index = existing_content.find(CONTENT_END_MARKER) + len(CONTENT_END_MARKER)

        if start_index != -1 and end_index != -1:
            # Replace only the auto-generated part
            updated_content = (
                existing_content[:start_index]
                + CONTENT_START_MARKER
                + "\n\n"
                + mdx_content.replace(CONTENT_START_MARKER, "").replace(
                    CONTENT_END_MARKER, ""
                )
                + "\n\n"
                + CONTENT_END_MARKER
                + existing_content[end_index:]
            )

            with open(main_mdx_path, "w") as f:
                f.write(updated_content)

            print(f"  Updated auto-generated content for {connector_name}")
        else:
            # No markers found, treat as a new file
            with open(main_mdx_path, "w") as f:
                f.write(frontmatter + mdx_content)

            print(
                f"  Created new main.mdx for {connector_name} (no markers found in existing file)"
            )
    else:
        # Create the file with the frontmatter and generated content
        with open(main_mdx_path, "w") as f:
            f.write(frontmatter + mdx_content)

        print(f"  Created new main.mdx for {connector_name}")

    return True
