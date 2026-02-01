"""Google Sheets-specific generation adapter: spreadsheet generator."""

from typing import List

from monke.client.llm import LLMClient
from monke.generation.schemas.google_sheets import GoogleSheetsSpreadsheet


async def generate_google_sheet(
    model: str, token: str, sheet_title: str
) -> GoogleSheetsSpreadsheet:
    """Generate realistic Google Sheets spreadsheet content with embedded verification token.

    Args:
        model: LLM model to use
        token: Unique verification token to embed in content
        sheet_title: Title for the spreadsheet

    Returns:
        GoogleSheetsSpreadsheet with title, headers, and data rows
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic spreadsheet data for a Google Sheet titled '{sheet_title}'. "
        "Create headers and 5-8 rows of sample data. "
        "The data should be realistic (e.g., sales data, employee records, inventory, etc.). "
        f"You MUST include the literal token '{token}' in at least one cell in the first column. "
        "Return JSON with: "
        "title (string), "
        "headers (list of column header strings, 3-5 columns), "
        "rows (list of lists, each inner list is a row of cell values as strings)."
    )

    sheet = await llm.generate_structured(GoogleSheetsSpreadsheet, instruction)
    sheet.title = sheet_title

    # Ensure token appears in the data
    token_found = False
    for row in sheet.rows:
        for cell in row:
            if token in cell:
                token_found = True
                break
        if token_found:
            break

    if not token_found:
        # Add token to first cell of first row
        if sheet.rows and sheet.rows[0]:
            sheet.rows[0][0] = f"{sheet.rows[0][0]} [{token}]"
        else:
            # Create a row with the token
            sheet.rows.insert(0, [f"Token: {token}"] + ["" for _ in range(len(sheet.headers) - 1)])

    return sheet


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

    sheet_types = [
        "Sales Report",
        "Employee Directory",
        "Inventory Tracker",
        "Project Budget",
        "Customer List",
    ]

    for i, token in enumerate(tokens):
        sheet_type = sheet_types[i] if i < len(sheet_types) else f"Data Sheet {i + 1}"
        sheet_title = f"{base_name} - {sheet_type}"
        sheet = await generate_google_sheet(model, token, sheet_title)
        spreadsheets.append(sheet)

    return spreadsheets
