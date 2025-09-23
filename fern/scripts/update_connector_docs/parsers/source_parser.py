"""Source parser module for extracting information from source connector files."""

import ast
import re

from ..constants import BACKEND_SOURCES_DIR


def parse_source_file(connector_name):
    """Parse source file for a connector using AST.

    Args:
        connector_name (str): The name of the connector

    Returns:
        list or None: List of source class information or None if file not found
    """
    source_file = BACKEND_SOURCES_DIR / f"{connector_name}.py"
    if not source_file.exists():
        return None

    with open(source_file, "r") as f:
        content = f.read()

    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError:
        print(f"  Warning: Could not parse {source_file} due to syntax error")
        return None

    source_classes = []

    # First extract information from decorators
    decorators_info = {}

    for node in ast.walk(tree):
        # Look for classes with @source decorator
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            auth_methods = []
            oauth_type = None
            auth_config_class = None
            config_class = None
            requires_byoc = False

            # Check decorators for @source
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                    and decorator.func.id == "source"
                ):
                    # Extract keyword arguments from the new decorator format
                    for keyword in decorator.keywords:
                        if keyword.arg == "auth_methods":
                            # Handle list of AuthenticationMethod enums
                            if isinstance(keyword.value, ast.List):
                                for elem in keyword.value.elts:
                                    if isinstance(elem, ast.Attribute):
                                        auth_methods.append(elem.attr)
                                    elif isinstance(elem, ast.Name):
                                        # Handle cases like AuthenticationMethod.OAUTH_BROWSER
                                        auth_methods.append(
                                            elem.id.replace("AuthenticationMethod.", "")
                                        )

                        elif keyword.arg == "oauth_type":
                            # Handle OAuthType enum
                            if isinstance(keyword.value, ast.Attribute):
                                oauth_type = keyword.value.attr
                            elif isinstance(keyword.value, ast.Name):
                                oauth_type = keyword.value.id.replace("OAuthType.", "")
                            elif (
                                isinstance(keyword.value, ast.Constant)
                                and keyword.value.value is None
                            ):
                                oauth_type = None

                        elif keyword.arg == "auth_config_class":
                            if isinstance(keyword.value, ast.Constant):
                                auth_config_class = keyword.value.value
                            elif isinstance(keyword.value, ast.Name) and keyword.value.id == "None":
                                auth_config_class = None

                        elif keyword.arg == "config_class" and isinstance(
                            keyword.value, ast.Constant
                        ):
                            config_class = keyword.value.value

                        elif keyword.arg == "requires_byoc" and isinstance(
                            keyword.value, ast.Constant
                        ):
                            requires_byoc = keyword.value.value

                    decorators_info[class_name] = {
                        "auth_methods": auth_methods,
                        "oauth_type": oauth_type,
                        "auth_config_class": auth_config_class,
                        "config_class": config_class,
                        "requires_byoc": requires_byoc,
                    }

    # Now process class definitions
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if this class inherits from BaseSource
            is_source = False
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseSource":
                    is_source = True
                    break

            if not is_source:
                continue

            class_name = node.name
            docstring = ast.get_docstring(node) or "No description available."

            # Get auth information from decorators
            auth_methods = []
            oauth_type = None
            auth_config_class = None
            config_class = None
            requires_byoc = False

            # Check if we found decorator info
            if class_name in decorators_info:
                auth_methods = decorators_info[class_name]["auth_methods"]
                oauth_type = decorators_info[class_name]["oauth_type"]
                auth_config_class = decorators_info[class_name]["auth_config_class"]
                config_class = decorators_info[class_name]["config_class"]
                requires_byoc = decorators_info[class_name]["requires_byoc"]

            # If not found in decorator, check for class attributes (fallback for old format)
            if not auth_methods:
                for item in node.body:
                    if isinstance(item, ast.Assign) and len(item.targets) == 1:
                        target = item.targets[0]
                        if isinstance(target, ast.Name):
                            if target.id == "_auth_methods":
                                # Try to extract auth methods from class attribute
                                if isinstance(item.value, ast.List):
                                    for elem in item.value.elts:
                                        if isinstance(elem, ast.Attribute):
                                            auth_methods.append(elem.attr)
                            elif target.id == "_oauth_type":
                                if isinstance(item.value, ast.Attribute):
                                    oauth_type = item.value.attr
                                elif isinstance(item.value, ast.Constant):
                                    oauth_type = item.value.value
                            elif target.id == "_auth_config_class":
                                if isinstance(item.value, ast.Constant):
                                    auth_config_class = item.value.value
                            elif target.id == "_config_class":
                                if isinstance(item.value, ast.Constant):
                                    config_class = item.value.value
                            elif target.id == "_requires_byoc":
                                if isinstance(item.value, ast.Constant):
                                    requires_byoc = item.value.value

            # If we still don't have auth info, try regex as last fallback
            if not auth_methods and not oauth_type:
                # Try to find oauth_type in the source
                oauth_match = re.search(r"oauth_type\s*=\s*OAuthType\.([^\s,\)]*)", content)
                if oauth_match:
                    oauth_type = oauth_match.group(1)

                # Try to find auth_methods
                auth_methods_match = re.search(r"auth_methods\s*=\s*\[(.*?)\]", content, re.DOTALL)
                if auth_methods_match:
                    methods_str = auth_methods_match.group(1)
                    # Extract method names
                    method_matches = re.findall(r"AuthenticationMethod\.(\w+)", methods_str)
                    auth_methods = method_matches

            source_classes.append(
                {
                    "name": class_name,
                    "docstring": docstring.strip() if docstring else "No description available.",
                    "auth_methods": auth_methods,
                    "oauth_type": oauth_type,
                    "auth_config_class": auth_config_class,
                    "config_class": config_class,
                    "requires_byoc": requires_byoc,
                }
            )

    return source_classes
