"""Excel-specific generation adapter: worksheet generator."""

from typing import List, Tuple

from monke.client.llm import LLMClient
from monke.generation.schemas.excel import ExcelWorksheetData


async def generate_excel_worksheet(
    model: str, token: str, worksheet_name: str
) -> ExcelWorksheetData:
    """Generate realistic Excel worksheet content with embedded verification token.

    Args:
        model: LLM model to use
        token: Unique verification token to embed in content
        worksheet_name: Name for the worksheet

    Returns:
        ExcelWorksheetData with headers and rows
    """
    llm = LLMClient(model_override=model)

    instruction = (
        f"Generate realistic data for an Excel worksheet named '{worksheet_name}'. "
        f"Create a dataset with 5-8 columns and 8-12 rows of sample data. "
        f"You MUST include the literal token '{token}' in one of the data cells. "
        "The data should look professional and realistic (e.g., sales data, project tracking, etc.). "
        "Return JSON with: name (string), headers (list of column names), "
        "rows (list of lists, each inner list is a row of cell values as strings)."
    )

    worksheet = await llm.generate_structured(ExcelWorksheetData, instruction)
    worksheet.name = worksheet_name

    # Ensure token appears somewhere in the data
    token_found = False
    for row in worksheet.rows:
        if any(token in str(cell) for cell in row):
            token_found = True
            break

    if not token_found and worksheet.rows:
        # Add token to first cell of last row
        worksheet.rows[-1][0] = f"{worksheet.rows[-1][0]} {token}"

    return worksheet


async def generate_workbook_content(
    model: str, tokens: List[str], base_name: str = "Test Data"
) -> Tuple[str, List[ExcelWorksheetData]]:
    """Generate content for a complete Excel workbook.

    Args:
        model: LLM model to use
        tokens: List of verification tokens (one per worksheet)
        base_name: Base name for the workbook

    Returns:
        Tuple of (filename, list of worksheet data)
    """
    worksheets = []

    worksheet_names = [
        "Summary",
        "Details",
        "Analysis",
        "Metrics",
        "Report",
    ]

    for i, token in enumerate(tokens):
        ws_name = worksheet_names[i] if i < len(worksheet_names) else f"Sheet{i + 1}"
        worksheet = await generate_excel_worksheet(model, token, ws_name)
        worksheets.append(worksheet)

    filename = f"Monke_{base_name.replace(' ', '_')}.xlsx"

    return filename, worksheets
