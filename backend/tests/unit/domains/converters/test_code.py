"""Unit tests for CodeConverter encoding validation."""

import os
import tempfile

import pytest

from airweave.domains.converters.code import CodeConverter


@pytest.fixture
def converter():
    return CodeConverter()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestCodeConverterEncodingValidation:

    @pytest.mark.asyncio
    async def test_convert_clean_python_code(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "clean.py")
        code = """def hello_world():
    print("Hello, world!")
    return True
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == code

    @pytest.mark.asyncio
    async def test_convert_empty_code_file(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "empty.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_batch_multiple_code_files(self, converter, temp_dir):
        py_path = os.path.join(temp_dir, "script.py")
        with open(py_path, "w", encoding="utf-8") as f:
            f.write("print('Python')")

        js_path = os.path.join(temp_dir, "script.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("console.log('JavaScript');")

        result = await converter.convert_batch([py_path, js_path])

        assert result[py_path] == "print('Python')"
        assert result[js_path] == "console.log('JavaScript');"

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self, converter):
        result = await converter.convert_batch(["/nonexistent/code.py"])
        assert "/nonexistent/code.py" in result
        assert result["/nonexistent/code.py"] is None
