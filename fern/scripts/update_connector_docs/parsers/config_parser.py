"""Config parser module for extracting information from config files."""

import ast

from ..constants import CONFIG_CONFIG_PATH


def parse_config_file():
    """Parse config.py file using Python's AST module.

    Returns:
        dict: Dictionary of config classes and their information
    """
    with open(CONFIG_CONFIG_PATH, "r") as f:
        content = f.read()

    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError:
        print("  Warning: Could not parse config.py file due to syntax error")
        return {}

    # Find all class definitions and their inheritance
    config_classes = {}

    # First pass: collect all classes
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name

            # Check if this is a config class
            parent_classes = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    parent_classes.append(base.id)

            # Skip if not config-related
            if not (
                any("Config" in parent for parent in parent_classes)
                or "Config" in class_name
            ):
                continue

            # Get docstring
            docstring = ast.get_docstring(node) or "No description available."

            # Get fields
            fields = []
            for item in node.body:
                # Look for attribute assignments with Field() constructor
                if isinstance(item, ast.AnnAssign) and hasattr(item, "target"):
                    field_name = (
                        item.target.id if isinstance(item.target, ast.Name) else None
                    )

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
                        is_required = True
                        default_value = None

                        # Extract Field parameters by traversing the AST
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

                                elif keyword.arg == "default":
                                    is_required = False
                                    # Extract default value
                                    if isinstance(keyword.value, ast.Str):
                                        default_value = keyword.value.s
                                    elif isinstance(keyword.value, ast.Constant):
                                        default_value = keyword.value.value
                                    elif isinstance(keyword.value, ast.Name):
                                        # For constants like True, False, None - convert to actual Python values
                                        name = keyword.value.id
                                        if name == "True":
                                            default_value = True
                                        elif name == "False":
                                            default_value = False
                                        elif name == "None":
                                            default_value = None
                                        else:
                                            default_value = name  # For other named constants
                                    elif isinstance(keyword.value, ast.List):
                                        default_value = "[]"  # Simplified for lists
                                    elif isinstance(keyword.value, ast.Dict):
                                        default_value = "{}"  # Simplified for dicts

                        fields.append(
                            {
                                "name": field_name,
                                "type": field_type,
                                "description": description,
                                "required": is_required,
                                "default": default_value,
                            }
                        )

            config_classes[class_name] = {
                "name": class_name,
                "parent_class": parent_classes[0] if parent_classes else None,
                "docstring": docstring,
                "fields": fields,
            }

    print(f"  Parsed {len(config_classes)} config classes")
    return config_classes
