from monke.client.llm import LLMClient
from monke.generation.schemas.outlook_calendar import OutlookEvent


async def generate_outlook_event(model: str, token: str) -> OutlookEvent:
    """
    Generate a short meeting; token must be in subject/body. Times auto-set near future.
    """
    # For simplicity (and to avoid model hallucinating invalid timestamps), prebuild times
    return OutlookEvent.near_future(token)
