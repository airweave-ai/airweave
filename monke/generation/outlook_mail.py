from monke.client.llm import LLMClient
from monke.generation.schemas.outlook_mail import OutlookMessage


async def generate_outlook_message(model: str, token: str) -> OutlookMessage:
    llm = LLMClient(model_override=model if model else None)
    instruction = (
        "Generate a short, safe, non-sensitive email draft about an internal product update. "
        f"Include the literal token '{token}' in subject and body. Use example recipients @example.test"
    )
    msg = await llm.generate_structured(OutlookMessage, instruction)
    msg.token = token
    if token not in msg.subject:
        msg.subject = f"{token} — {msg.subject}"
    if token not in msg.body_html:
        msg.body_html += f"<p>Token: <b>{token}</b></p>"
    # Ensure recipients exist (but stay in a safe domain)
    if not msg.to:
        msg.to = [f"{token}@example.test"]
    return msg
