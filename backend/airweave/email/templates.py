# noqa: E501

"""Email templates for Airweave notifications."""


def get_api_key_expiration_email(
    days_until_expiration: int,
    api_key_preview: str,
    settings_url: str,
) -> tuple[str, str]:
    """Generate email subject and HTML body for API key expiration notification.

    Args:
    ----
        days_until_expiration (int): Number of days until key expires (0 if expired)
        api_key_preview (str): First 4 characters of the API key
        settings_url (str): URL to the API keys settings page

    Returns:
    -------
        tuple[str, str]: (subject, html_body)

    """
    if days_until_expiration <= 0:
        # Key has expired
        subject = "Airweave API Key Expired"
        html_body = f"""
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>

    <p style="margin: 0 0 15px 0;">
        Your Airweave API key (<code>{api_key_preview}...</code>) has expired and is no
        longer valid.
    </p>

    <p style="margin: 0 0 15px 0;">
        To continue using the Airweave API, you'll need to create a new API key.
    </p>

    <p style="margin: 0 0 15px 0;">
        <a href="{settings_url}"
          style="display: inline-block; padding: 10px 20px; background-color: #0066cc;
                 color: white; text-decoration: none; border-radius: 5px;">
          Create New API Key
        </a>
    </p>

    <p style="margin: 15px 0 0 0;">
        If you have any questions, feel free to reach out.<br>
        <br>
        Airweave Team
    </p>
</div>
        """
    elif days_until_expiration <= 3:
        # Urgent: 3 days or less
        plural = "s" if days_until_expiration > 1 else ""
        subject = f"Urgent: Airweave API Key Expires in {days_until_expiration} Day{plural}"
        html_body = f"""
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>

    <p style="margin: 0 0 15px 0;">
        <strong>Your Airweave API key (<code>{api_key_preview}...</code>) will expire in
        {days_until_expiration} day{"s" if days_until_expiration > 1 else ""}.</strong>
    </p>

    <p style="margin: 0 0 15px 0;">
        To avoid service disruption, you can:
    </p>

    <ul style="margin: 0 0 15px 20px;">
        <li>Use the "Rotate Key" button to generate a new key</li>
        <li>Or create a new API key and update your applications</li>
    </ul>

    <p style="margin: 0 0 15px 0;">
        <a href="{settings_url}"
          style="display: inline-block; padding: 10px 20px; background-color: #0066cc;
                 color: white; text-decoration: none; border-radius: 5px;">
          Manage API Keys
        </a>
    </p>

    <p style="margin: 15px 0 0 0;">
        If you have any questions, feel free to reach out.<br>
        <br>
        Airweave Team
    </p>
</div>
        """
    else:
        # Standard reminder: 14 days
        subject = f"Airweave API Key Expires in {days_until_expiration} Days"
        html_body = f"""
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>

    <p style="margin: 0 0 15px 0;">
        This is a friendly reminder that your Airweave API key
        (<code>{api_key_preview}...</code>) will expire in {days_until_expiration} days.
    </p>

    <p style="margin: 0 0 15px 0;">
        You can rotate your key or create a new one anytime in your settings.
    </p>

    <p style="margin: 0 0 15px 0;">
        <a href="{settings_url}"
          style="display: inline-block; padding: 10px 20px; background-color: #0066cc;
                 color: white; text-decoration: none; border-radius: 5px;">
          Manage API Keys
        </a>
    </p>

    <p style="margin: 15px 0 0 0;">
        Airweave Team
    </p>
</div>
        """

    return subject, html_body
