from airweave import AirweaveSDK

client = AirweaveSDK(api_key="REDACTED")

# Create a Google Drive connection using Composio credentials
source_connection = client.source_connections.create_source_connection(
    name="Sales Team Google Mail",
    short_name="gmail",
    auth_provider="REDACTED",  # Your Composio auth provider id
    auth_provider_config={
        "auth_config_id": "REDACTED",  # From Composio dashboard
        "account_id": "REDACTED",  # From Composio dashboard
    },
)

print(f"Created: {source_connection.name}")
