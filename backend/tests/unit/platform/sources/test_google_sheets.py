
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from airweave.platform.sources.google_sheets import GoogleSheetsSource, GoogleSheetsCursor
from airweave.platform.entities.google_sheets import GoogleSheetsSpreadsheetEntity, GoogleSheetsWorksheetEntity

@pytest.fixture
def mock_config():
    return {"include_trashed": False, "include_shared": True}

@pytest.fixture
def source_instance(mock_config):
    # Mocking the create method internal logic or just instantiating directly if possible
    # iterating over classmethod behavior
    instance = GoogleSheetsSource()
    instance.access_token = "fake_token"
    instance.include_trashed = mock_config["include_trashed"]
    instance.include_shared = mock_config["include_shared"]
    return instance

@pytest.mark.asyncio
async def test_source_validation(source_instance):
    with patch.object(source_instance, "_validate_oauth2", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = True
        result = await source_instance.validate()
        assert result is True
        mock_validate.assert_called_once()
        args, kwargs = mock_validate.call_args
        assert "drive/v3/files?pageSize=1" in kwargs["ping_url"]

@pytest.mark.asyncio
async def test_generate_entities(source_instance):
    # Mock _list_spreadsheets and _process_spreadsheet
    mock_spreadsheet = GoogleSheetsSpreadsheetEntity(
        spreadsheet_id="sheet123",
        title="Test Sheet",
        name="Test Sheet",
        owner="test@example.com",
        created_time=datetime.now(),
        modified_time=datetime.now(),
        url="http://example.com/sheet",
        breadcrumbs=[],
    )
    
    mock_worksheet = GoogleSheetsWorksheetEntity(
        spreadsheet_id="sheet123",
        sheet_id=1,
        title="Worksheet1",
        name="Test Sheet - Worksheet1",
        index=0,
        row_count=10,
        column_count=5,
        values="Row 1: A | B",
        url="http://example.com/sheet#gid=1",
        breadcrumbs=[],
    )

    with patch.object(source_instance, "_list_spreadsheets", return_value=AsyncMock()) as mock_list_spreadsheets, \
         patch.object(source_instance, "_process_spreadsheet", return_value=AsyncMock()) as mock_process_spreadsheet:
        
        # Configure async generators
        async def async_gen_spreadsheets(client):
            yield mock_spreadsheet
            
        async def async_gen_worksheets(client, spreadsheet):
            yield mock_worksheet

        mock_list_spreadsheets.side_effect = async_gen_spreadsheets
        mock_process_spreadsheet.side_effect = async_gen_worksheets

        entities = []
        async for entity in source_instance.generate_entities():
            entities.append(entity)
        
        assert len(entities) == 2
        assert isinstance(entities[0], GoogleSheetsSpreadsheetEntity)
        assert entities[0].spreadsheet_id == "sheet123"
        assert isinstance(entities[1], GoogleSheetsWorksheetEntity)
        assert entities[1].sheet_id == 1

@pytest.mark.asyncio
async def test_google_sheets_cursor_instantiation():
    cursor = GoogleSheetsCursor(next_page_token="abc", start_page_token="123")
    assert cursor.next_page_token == "abc"
    assert cursor.start_page_token == "123"
