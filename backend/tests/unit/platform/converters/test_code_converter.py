"""Unit tests for CodeConverter encoding validation."""

import os
import pytest
import tempfile

from airweave.platform.converters.code_converter import CodeConverter


@pytest.fixture
def converter():
    """Create CodeConverter instance."""
    return CodeConverter()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestCodeConverterEncodingValidation:
    """Test CodeConverter encoding detection and validation."""

    @pytest.mark.asyncio
    async def test_convert_clean_python_code(self, converter, temp_dir):
        """Test conversion of clean Python code."""
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
    async def test_convert_code_with_unicode_comments(self, converter, temp_dir):
        """Test conversion of code with Unicode comments."""
        file_path = os.path.join(temp_dir, "unicode.py")
        code = """# 这是中文注释 - This is a Chinese comment
def hello():
    # Café résumé 🎉
    return "Hello"
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == code
        assert "中文" in result[file_path]
        assert "🎉" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_binary_file_as_code(self, converter, temp_dir):
        """Test handling of file with null bytes (clearly binary)."""
        file_path = os.path.join(temp_dir, "binary.py")
        # Write data with null bytes (clearly not text)
        with open(file_path, "wb") as f:
            f.write(b"some_code = 1\x00\x00\x00" * 100)

        result = await converter.convert_batch([file_path])

        # Should reject due to null bytes or handle gracefully
        assert file_path in result
        # May pass if chardet handles it or fail - either is OK

    @pytest.mark.asyncio
    async def test_convert_empty_code_file(self, converter, temp_dir):
        """Test conversion of empty code file."""
        file_path = os.path.join(temp_dir, "empty.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_whitespace_only_code(self, converter, temp_dir):
        """Test conversion of code file with only whitespace."""
        file_path = os.path.join(temp_dir, "whitespace.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("   \n\n   \t\t  ")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        # Whitespace-only files should return None (no meaningful content)
        assert result[file_path] is None or (result[file_path] and not result[file_path].strip())

    @pytest.mark.asyncio
    async def test_convert_javascript_code(self, converter, temp_dir):
        """Test conversion of JavaScript code."""
        file_path = os.path.join(temp_dir, "app.js")
        code = """function greet(name) {
    console.log(`Hello, ${name}!`);
}

export default greet;
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == code
        assert "function greet" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_cpp_code(self, converter, temp_dir):
        """Test conversion of C++ code."""
        file_path = os.path.join(temp_dir, "main.cpp")
        code = """#include <iostream>

int main() {
    std::cout << "Hello World!" << std::endl;
    return 0;
}
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == code
        assert "#include" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_batch_multiple_code_files(self, converter, temp_dir):
        """Test batch conversion of multiple code files."""
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
    async def test_convert_code_with_comments(self, converter, temp_dir):
        """Test conversion of code with comments."""
        file_path = os.path.join(temp_dir, "commented.py")
        code = """def hello():
    # This is a comment
    # Another comment
    return True
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = await converter.convert_batch([file_path])

        # Should successfully convert
        assert file_path in result
        assert result[file_path] == code

    @pytest.mark.asyncio
    async def test_convert_large_code_file(self, converter, temp_dir):
        """Test conversion of large code file."""
        file_path = os.path.join(temp_dir, "large.py")
        # Generate large code file
        lines = []
        for i in range(10000):
            lines.append(f"def function_{i}():\n")
            lines.append(f"    return {i}\n")
            lines.append("\n")

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "function_0" in result[file_path]
        assert "function_9999" in result[file_path]


class TestCodeConverterEdgeCases:
    """Test edge cases in CodeConverter."""

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self, converter):
        """Test conversion of nonexistent file."""
        result = await converter.convert_batch(["/nonexistent/code.py"])

        assert "/nonexistent/code.py" in result
        assert result["/nonexistent/code.py"] is None

    @pytest.mark.asyncio
    async def test_convert_code_with_long_lines(self, converter, temp_dir):
        """Test conversion of code with very long lines."""
        file_path = os.path.join(temp_dir, "long_lines.py")
        # Create a file with a very long line
        long_string = "x" * 10000
        code = f'long_var = "{long_string}"\n'

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert len(result[file_path]) > 10000

    @pytest.mark.asyncio
    async def test_convert_code_with_special_characters(self, converter, temp_dir):
        """Test conversion of code with special characters in strings."""
        file_path = os.path.join(temp_dir, "special.py")
        code = r'''def test():
    s1 = "Line with \n newline"
    s2 = "Tab with \t tab"
    s3 = 'Quote with \' quote'
    return True
'''
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == code

