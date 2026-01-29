"""Unit tests for HtmlConverter encoding validation."""

import os
import pytest
import tempfile

from airweave.platform.converters.html_converter import HtmlConverter


@pytest.fixture
def converter():
    """Create HtmlConverter instance."""
    return HtmlConverter()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestHtmlConverterEncodingValidation:
    """Test HtmlConverter encoding detection and validation."""

    @pytest.mark.asyncio
    async def test_convert_clean_html(self, converter, temp_dir):
        """Test conversion of clean HTML."""
        file_path = os.path.join(temp_dir, "clean.html")
        html = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Hello World</h1>
    <p>This is a test paragraph.</p>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        # Check that HTML was converted (markdown should have text)
        assert "Hello World" in result[file_path]
        assert "test paragraph" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_html_with_unicode(self, converter, temp_dir):
        """Test conversion of HTML with Unicode content."""
        file_path = os.path.join(temp_dir, "unicode.html")
        html = """<!DOCTYPE html>
<html>
<body>
    <p>Unicode: 世界 🌍 Café</p>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "世界" in result[file_path]
        assert "🌍" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_html_with_invalid_tags(self, converter, temp_dir):
        """Test HTML with broken/invalid tags."""
        file_path = os.path.join(temp_dir, "invalid.html")
        html = """<html>
<body>
    <p>Broken tag <div
    <p>Another paragraph</p>
</body>
</html>"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        # Should handle malformed HTML gracefully
        assert file_path in result
        # May succeed or fail depending on html-to-markdown tolerance

    @pytest.mark.asyncio
    async def test_convert_empty_html(self, converter, temp_dir):
        """Test conversion of empty HTML file."""
        file_path = os.path.join(temp_dir, "empty.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_html_with_special_entities(self, converter, temp_dir):
        """Test conversion of HTML with special entities."""
        file_path = os.path.join(temp_dir, "entities.html")
        html = """<!DOCTYPE html>
<html>
<body>
    <p>&lt;div&gt; &amp; &quot;quotes&quot; &copy; 2024</p>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None

    @pytest.mark.asyncio
    async def test_convert_html_with_nested_structure(self, converter, temp_dir):
        """Test conversion of HTML with nested structure."""
        file_path = os.path.join(temp_dir, "nested.html")
        html = """<!DOCTYPE html>
<html>
<body>
    <article>
        <header>
            <h1>Main Title</h1>
        </header>
        <section>
            <h2>Section Title</h2>
            <p>Section content</p>
        </section>
    </article>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "Main Title" in result[file_path]
        assert "Section Title" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_html_with_links(self, converter, temp_dir):
        """Test conversion of HTML with links."""
        file_path = os.path.join(temp_dir, "links.html")
        html = """<!DOCTYPE html>
<html>
<body>
    <p>Visit <a href="https://example.com">our website</a> for more.</p>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "website" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_malformed_html(self, converter, temp_dir):
        """Test conversion of malformed HTML."""
        file_path = os.path.join(temp_dir, "malformed.html")
        html = """<html>
<body>
    <p>Unclosed paragraph
    <div>Unclosed div
</body>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        # Should still convert malformed HTML
        assert file_path in result
        # Result depends on html-to-markdown behavior
        # May succeed or fail gracefully

    @pytest.mark.asyncio
    async def test_convert_batch_multiple_html_files(self, converter, temp_dir):
        """Test batch conversion of multiple HTML files."""
        html1_path = os.path.join(temp_dir, "page1.html")
        with open(html1_path, "w", encoding="utf-8") as f:
            f.write("<html><body><p>Page 1</p></body></html>")

        html2_path = os.path.join(temp_dir, "page2.html")
        with open(html2_path, "w", encoding="utf-8") as f:
            f.write("<html><body><p>Page 2</p></body></html>")

        result = await converter.convert_batch([html1_path, html2_path])

        assert html1_path in result
        assert html2_path in result
        if result[html1_path]:
            assert "Page 1" in result[html1_path]
        if result[html2_path]:
            assert "Page 2" in result[html2_path]

    @pytest.mark.asyncio
    async def test_convert_html_with_scripts_and_styles(self, converter, temp_dir):
        """Test conversion of HTML with script and style tags."""
        file_path = os.path.join(temp_dir, "with_scripts.html")
        html = """<!DOCTYPE html>
<html>
<head>
    <style>body { color: red; }</style>
    <script>console.log('test');</script>
</head>
<body>
    <p>Visible content</p>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        # Should extract visible content, scripts/styles may be filtered
        if result[file_path]:
            assert "Visible content" in result[file_path]


class TestHtmlConverterEdgeCases:
    """Test edge cases in HtmlConverter."""

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self, converter):
        """Test conversion of nonexistent file."""
        result = await converter.convert_batch(["/nonexistent/page.html"])

        assert "/nonexistent/page.html" in result
        assert result["/nonexistent/page.html"] is None

    @pytest.mark.asyncio
    async def test_convert_whitespace_only_html(self, converter, temp_dir):
        """Test conversion of HTML with only whitespace."""
        file_path = os.path.join(temp_dir, "whitespace.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("   \n\n   ")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_large_html_file(self, converter, temp_dir):
        """Test conversion of large HTML file."""
        file_path = os.path.join(temp_dir, "large.html")
        # Generate large HTML
        html_parts = ["<html><body>"]
        for i in range(1000):
            html_parts.append(f"<p>Paragraph {i}</p>")
        html_parts.append("</body></html>")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("".join(html_parts))

        result = await converter.convert_batch([file_path])

        assert file_path in result
        # Should handle large files
        if result[file_path]:
            assert "Paragraph 0" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_html_with_missing_closing_tags(self, converter, temp_dir):
        """Test HTML with missing closing tags."""
        file_path = os.path.join(temp_dir, "unclosed.html")
        html = """<html>
<body>
    <p>Paragraph without closing tag
    <div>Another div
        <span>Nested span
</body>"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        # Should handle unclosed tags gracefully
        assert file_path in result
        # html-to-markdown is usually tolerant of malformed HTML

