"""Entity parser module for extracting information from entity files."""

import ast
import re

from ..constants import BACKEND_ENTITIES_DIR


def parse_entity_file(connector_name):
    """Parse entity file for a connector using AST.

    Args:
        connector_name (str): The name of the connector

    Returns:
        list or None: List of entity class information or None if file not found
    """

    entity_file = BACKEND_ENTITIES_DIR / f"{connector_name}.py"
    if not entity_file.exists():
        return None

    with open(entity_file, "r") as f:
        content = f.read()

    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError:
        print(f"  Warning: Could not parse {entity_file} due to syntax error")
        return None

    entity_classes = []

    # Find all class definitions that inherit from BaseEntity
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if this class inherits from any entity base class
            is_entity = False
            for base in node.bases:
                if isinstance(base, ast.Name):
                    if base.id in [
                        "BaseEntity",
                        "FileEntity",
                        "CodeFileEntity",
                        "DeletionEntity",
                        "EmailEntity",
                        "WebEntity",
                    ]:
                        is_entity = True
                        break
                # Handle complex inheritance (like with subscripts)
                elif isinstance(base, ast.Subscript) and isinstance(
                    base.value, ast.Name
                ):
                    if base.value.id in [
                        "BaseEntity",
                        "FileEntity",
                        "CodeFileEntity",
                        "DeletionEntity",
                        "EmailEntity",
                        "WebEntity",
                    ]:
                        is_entity = True
                        break

            if not is_entity:
                continue

            class_name = node.name
            docstring = ast.get_docstring(node) or "No description available."

            # Extract fields
            fields = []
            for item in node.body:
                # Look for attribute assignments with Field() constructor
                if isinstance(item, ast.AnnAssign) and hasattr(item, "target"):
                    field_name = None
                    if isinstance(item.target, ast.Name):
                        field_name = item.target.id

                    if field_name:
                        # Get field type
                        field_type = None
                        if hasattr(item, "annotation"):
                            if hasattr(ast, "unparse"):  # Python 3.9+
                                field_type = ast.unparse(item.annotation)
                            else:
                                # Fallback for older Python versions
                                if isinstance(item.annotation, ast.Name):
                                    field_type = item.annotation.id
                                elif isinstance(item.annotation, ast.Subscript):
                                    if isinstance(item.annotation.value, ast.Name):
                                        field_type = item.annotation.value.id

                        field_type = field_type or "Unknown"
                        description = "No description"

                        # Extract Field parameters for description if Field constructor is used
                        if hasattr(item, "value") and isinstance(item.value, ast.Call):
                            for keyword in item.value.keywords:
                                if keyword.arg == "description":
                                    # Simple string
                                    if isinstance(keyword.value, ast.Str):
                                        description = keyword.value.s
                                    # String in Python 3.8+ (ast.Constant)
                                    elif isinstance(
                                        keyword.value, ast.Constant
                                    ) and isinstance(keyword.value.value, str):
                                        description = keyword.value.value
                                    # Concatenated strings or multiline description
                                    elif isinstance(
                                        keyword.value, ast.BinOp
                                    ) or isinstance(keyword.value, ast.Tuple):
                                        # We need the original source for this part
                                        try:
                                            lines = content.split("\n")
                                            lineno = (
                                                keyword.value.lineno - 1
                                            )  # Convert to 0-indexed

                                            # Heuristic: take the current line and the next 3 lines
                                            # to capture multiline descriptions
                                            desc_lines = lines[lineno : lineno + 4]

                                            # Extract the part inside the quotes or parentheses
                                            desc_text = " ".join(desc_lines)
                                            desc_match = re.search(
                                                r'description\s*=\s*(?:\(?\s*"([^"]*)"|\(?\s*\'([^\']*)\')',
                                                desc_text,
                                            )
                                            if desc_match:
                                                description = desc_match.group(
                                                    1
                                                ) or desc_match.group(2)
                                        except:
                                            pass

                        # Clean up the description - remove excessive whitespace and newlines
                        description = re.sub(r"\s+", " ", description).strip()

                        fields.append(
                            {
                                "name": field_name,
                                "type": field_type,
                                "description": description,
                            }
                        )

            entity_classes.append(
                {
                    "name": class_name,
                    "docstring": docstring.strip()
                    if docstring
                    else "No description available.",
                    "fields": fields,
                }
            )

    return entity_classes
