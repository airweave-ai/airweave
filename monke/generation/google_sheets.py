"""Google Sheets-specific generation adapter: spreadsheet generator."""

from typing import List

from monke.client.llm import LLMClient
from monke.generation.schemas.google_sheets import GoogleSheetsSpreadsheet


async def generate_google_sheets_spreadsheet(
    model: str, token: str, sheet_title: str
) -> GoogleSheetsSpreadsheet:
    """Generate realistic Google Sheets spreadsheet content with embedded verification token.

    Args:
        model: LLM model to use
        token: Unique verification token to embed in content
        sheet_title: Title for the spreadsheet

    Returns:
        GoogleSheetsSpreadsheet with title and content
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic content for a Google Sheets spreadsheet titled '{sheet_title}'. "
        f"Create 3-5 rows of tabular data (e.g., project tracking, budget, inventory, or sales data). "
        f"Format as CSV-like data with headers and rows. "
        f"You MUST include the literal token '{token}' naturally within the content. "
        "The content should look professional and realistic. "
        "Return JSON with: title (string), content (string with CSV-like data, use \\n for newlines)."
    )

    spreadsheet = await llm.generate_structured(GoogleSheetsSpreadsheet, instruction)
    spreadsheet.title = sheet_title

    # Ensure token appears in the content
    if token not in spreadsheet.content:
        # Add token to the end if not present
        spreadsheet.content = f"{spreadsheet.content}\n\nVerification: {token}"

    return spreadsheet


async def generate_spreadsheets(
    model: str, tokens: List[str], base_name: str = "Test Spreadsheet"
) -> List[GoogleSheetsSpreadsheet]:
    """Generate multiple Google Sheets spreadsheets.

    Args:
        model: LLM model to use
        tokens: List of verification tokens (one per spreadsheet)
        base_name: Base name for the spreadsheets

    Returns:
        List of GoogleSheetsSpreadsheet objects
    """
    spreadsheets = []

    spreadsheet_types = [
        "Project Tracker",
        "Budget Analysis",
        "Sales Report",
        "Inventory Management",
        "Team Performance",
    ]

    for i, token in enumerate(tokens):
        sheet_type = (
            spreadsheet_types[i]
            if i < len(spreadsheet_types)
            else f"Spreadsheet {i + 1}"
        )
        sheet_title = f"{base_name} - {sheet_type}"
        spreadsheet = await generate_google_sheets_spreadsheet(
            model, token, sheet_title
        )
        spreadsheets.append(spreadsheet)

    return spreadsheets
