from monke.client.llm import LLMClient
from monke.generation.schemas.monday import MondayItem


async def generate_monday_item(model: str, token: str) -> MondayItem:
    llm = LLMClient(model_override=model)
    instruction = (
        "Generate a realistic work item summary for a monday.com board. "
        f"Include the literal token '{token}' in the item name and note. "
        "Keep it short and useful."
    )
    item = await llm.generate_structured(MondayItem, instruction)
    item.token = token
    if token not in item.name:
        item.name = f"{token} — {item.name}"
    if item.note and token not in item.note:
        item.note += f" ({token})"
    return item
