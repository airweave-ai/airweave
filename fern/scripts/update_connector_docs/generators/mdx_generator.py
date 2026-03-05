"""MDX generator module for creating connector documentation."""

from ..constants import CONTENT_END_MARKER, CONTENT_START_MARKER


def escape_mdx_special_chars(text):
    """Escape special characters that could cause issues in MDX parsing.

    Args:
        text (str): The text to escape

    Returns:
        str: Text with special characters escaped
    """
    if not text:
        return text

    # Replace angle brackets with their HTML entity equivalents
    escaped_text = text.replace("<", "&lt;").replace(">", "&gt;")

    # Debug statement to verify the function is working
    print(f"Escaping text: '{text}' -> '{escaped_text}'")

    return escaped_text


def generate_mdx_content(
    connector_name, entity_info, source_info, auth_configs, config_configs=None
):
    """Generate MDX content for a connector."""
    # Normalize connector name for display
    display_name = connector_name.replace("_", " ").title()

    # Build content using simple string concatenation to avoid escaping issues
    content = "<div className=\"connector-header\" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>\n"
    content += f'  <img src="icon.svg" alt="{display_name} logo" width="48" height="48" className="connector-icon" />\n'
    # Avoid f-string for style attribute to prevent curly brace interpretation
    content += "  <h1 style={{ margin: 0 }}>" + display_name + "</h1>\n"
    content += "</div>\n\n"
    content += f"This connector enables AI agents and RAG systems to retrieve context from {display_name} through Airweave's unified search layer.\n\n"
    content += "## Configuration\n"

    # Add source information
    if source_info:
        for source in source_info:
            if source["docstring"]:
                content += f"\n{source['docstring']}\n\n"

            # Add GitHub reference card
            content += f"""<Card
  title="View Source Code"
  icon="brands github"
  href="https://github.com/airweave-ai/airweave/tree/main/backend/airweave/platform/sources/{connector_name}.py"
>
  Explore the {display_name} connector implementation
</Card>

"""

            # Add authentication information section
            content += "### Authentication\n\n"

            auth_methods = source.get("auth_methods", [])
            oauth_type = source.get("oauth_type")
            auth_config_class = source.get("auth_config_class")
            requires_byoc = source.get("requires_byoc", False)

            # Determine authentication type from auth_methods and oauth_type
            has_oauth = any(method in ["OAUTH_BROWSER", "OAUTH_TOKEN"] for method in auth_methods)
            has_direct = "DIRECT" in auth_methods
            has_auth_provider = "AUTH_PROVIDER" in auth_methods

            # Handle OAuth authentication
            if has_oauth and oauth_type:
                if requires_byoc:
                    # BYOC (Bring Your Own Credentials) OAuth
                    content += "This connector uses **OAuth 2.0 with custom credentials**. You need to provide your OAuth application's Client ID and Client Secret, then complete the OAuth consent flow.\n\n"

                    content += """<Card
  title="OAuth Setup Required"
  className="auth-setup-card"
  style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', padding: '16px', marginBottom: '24px' }}
>

1. Create an OAuth application in your provider's developer console
2. Enter your Client ID and Client Secret when configuring the connection
3. Complete the OAuth consent flow

</Card>

"""
                else:
                    # Regular OAuth (Airweave-managed credentials)
                    content += "This connector uses **OAuth 2.0 authentication**. You can connect through the Airweave UI or API using the OAuth flow.\n\n"

                    # Show available authentication methods
                    if auth_methods:
                        content += "**Supported authentication methods:**\n"
                        for method in auth_methods:
                            if method == "OAUTH_BROWSER":
                                content += "- OAuth Browser Flow (recommended for UI)\n"
                            elif method == "OAUTH_TOKEN":
                                content += "- OAuth Token (for programmatic access)\n"
                            elif method == "AUTH_PROVIDER":
                                content += "- Auth Provider (enterprise SSO)\n"
                        content += "\n"

            # Handle Direct authentication
            elif has_direct and auth_config_class and auth_config_class in auth_configs:
                # Custom authentication config class
                auth_info = auth_configs[auth_config_class]
                content += "This connector uses a custom authentication configuration.\n\n"

                # Only show auth fields for non-OAuth configs
                content += """<Card
  title="Authentication Configuration"
  className="auth-config-card"
  style={{ backgroundColor: 'rgba(0, 0, 0, 0.1)', padding: '16px', marginBottom: '24px' }}
>
"""

                if auth_info["docstring"]:
                    content += f"\n{auth_info['docstring']}\n\n"

                if auth_info["fields"]:
                    for field in auth_info["fields"]:
                        # Get descriptions from parent class if available
                        field_description = field["description"]
                        if field_description == "No description" and "parent_class" in auth_info:
                            parent_class = auth_info["parent_class"]
                            if parent_class in auth_configs:
                                parent_fields = auth_configs[parent_class]["fields"]
                                for parent_field in parent_fields:
                                    if (
                                        parent_field["name"] == field["name"]
                                        and parent_field["description"] != "No description"
                                    ):
                                        field_description = parent_field["description"]
                                        break

                        # Escape special characters in description
                        escaped_description = escape_mdx_special_chars(field_description)

                        # Prepare default value attribute if exists
                        default_attr = ""
                        if "default" in field and field["default"] is not None:
                            # Properly format default value for JSX
                            default_value = field["default"]

                            if isinstance(default_value, str):
                                # String values need quotes
                                default_attr = f'  default="{default_value}"\n'
                            elif isinstance(default_value, (int, float)):
                                # Numbers need curly braces
                                default_attr = f"  default={{{default_value}}}\n"
                            elif isinstance(default_value, bool):
                                # Booleans need curly braces and proper JS boolean values
                                default_attr = f"  default={{{str(default_value).lower()}}}\n"
                            elif isinstance(default_value, list):
                                # Arrays need curly braces and proper formatting
                                default_attr = f"  default={{{str(default_value)}}}\n"
                            else:
                                # Fallback for other types
                                default_attr = f"  default={{{str(default_value)}}}\n"

                        # Generate ParamField component
                        content += f"""<ParamField
  path="{field["name"]}"
  type="{field["type"]}"
  required={{{"true" if field["required"] else "false"}}}
{default_attr}>
  {escaped_description}
</ParamField>
"""
                # Close the Card component
                content += "</Card>\n\n"

            # Handle cases where no auth methods are specified or authentication is not required
            elif not auth_methods:
                content += "This connector does not require authentication.\n\n"
            else:
                # Generic fallback for other authentication scenarios
                content += "**Supported authentication methods:**\n"
                for method in auth_methods:
                    if method == "OAUTH_BROWSER":
                        content += "- OAuth Browser Flow\n"
                    elif method == "OAUTH_TOKEN":
                        content += "- OAuth Token\n"
                    elif method == "AUTH_PROVIDER":
                        content += "- Auth Provider\n"
                    elif method == "DIRECT":
                        content += "- Direct Credentials\n"
                    else:
                        content += f"- {method}\n"
                content += "\n"

            # Add configuration options section
            config_class = source.get("config_class")
            if config_class and config_configs and config_class in config_configs:
                config_info = config_configs[config_class]

                content += "### Configuration Options\n\n"

                # Check if there are actually fields to display
                if config_info["fields"] and len(config_info["fields"]) > 0:
                    content += (
                        "The following configuration options are available for this connector:\n\n"
                    )

                    # Wrap the configuration options in a Card
                    content += """<Card
  title="Configuration Parameters"
  className="config-card"
  style={{ backgroundColor: 'rgba(0, 0, 0, 0.05)', padding: '16px', marginBottom: '24px' }}
>
"""

                    if config_info["docstring"]:
                        content += f"\n{config_info['docstring']}\n"

                    for field in config_info["fields"]:
                        # Escape special characters in description
                        escaped_description = escape_mdx_special_chars(field["description"])

                        # Prepare default value attribute if exists
                        default_attr = ""
                        if "default" in field and field["default"] is not None:
                            # Properly format default value for JSX
                            default_value = field["default"]

                            # Check bool before int/float because bool is a subclass of int in Python
                            if isinstance(default_value, bool):
                                # Booleans need curly braces and proper JS boolean values
                                default_attr = f"  default={{{str(default_value).lower()}}}\n"
                            elif isinstance(default_value, str):
                                # String values need quotes
                                default_attr = f'  default="{default_value}"\n'
                            elif isinstance(default_value, (int, float)):
                                # Numbers need curly braces
                                default_attr = f"  default={{{default_value}}}\n"
                            elif isinstance(default_value, list):
                                # Arrays need curly braces and proper formatting
                                default_attr = f"  default={{{str(default_value)}}}\n"
                            else:
                                # Fallback for other types
                                default_attr = f"  default={{{str(default_value)}}}\n"

                        # Generate ParamField component for config fields
                        content += f"""<ParamField
  path="{field["name"]}"
  type="{field["type"]}"
  required={{{"true" if field["required"] else "false"}}}
{default_attr}>
  {escaped_description}
</ParamField>
"""
                    # Close the Card component
                    content += "</Card>\n\n"
                else:
                    # No configuration fields available
                    content += (
                        "This connector does not have any additional configuration options.\n\n"
                    )
            else:
                # No config class found
                content += "### Configuration Options\n\n"
                content += "This connector does not have any additional configuration options.\n\n"

    # Add entity information (keep this section as it's useful)
    if entity_info:
        content += "## Data Models\n\n"
        content += "The following data models are available for this connector:\n\n"

        for entity in entity_info:
            # Start with opening Accordion tag
            content += f'<Accordion title="{entity["name"]}">\n\n'
            content += f"{entity['docstring']}\n\n"

            # Use markdown tables for entity fields
            content += "| Field | Type | Description |\n"
            content += "|-------|------|-------------|\n"
            for field in entity["fields"]:
                # Escape special characters in the description
                escaped_description = escape_mdx_special_chars(field["description"])
                content += f"| {field['name']} | {field['type']} | {escaped_description} |\n"

            content += "\n</Accordion>\n"

    # Wrap the content with delimiters
    return f"{CONTENT_START_MARKER}\n\n{content}\n\n{CONTENT_END_MARKER}"
