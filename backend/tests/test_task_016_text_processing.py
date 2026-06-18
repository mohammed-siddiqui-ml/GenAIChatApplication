"""
Test suite for Text Processing Utilities (task-016)

Tests all functions in src/utils/text_processing.py according to the test plan:
- Token counting (count_tokens)
- Text normalization (normalize_text)
- HTML cleaning (clean_html)
- Markdown extraction (extract_markdown_text)
- Text chunking (chunk_text)
- Document batch processing (chunk_documents)
"""

import pytest
import sys
from pathlib import Path

# Add src directory to path
backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))

from utils.text_processing import (
    count_tokens,
    normalize_text,
    clean_html,
    extract_markdown_text,
    chunk_text,
    chunk_documents,
    TextProcessingError,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
)


class TestTokenCounting:
    """Test Group A: Token Counting"""

    def test_count_tokens_simple_text(self):
        """TC-A1: Count tokens for simple text"""
        result = count_tokens("Hello, world!")
        assert isinstance(result, int)
        assert result > 0
        assert 2 <= result <= 6  # Reasonable range for this text

    def test_count_tokens_empty_string(self):
        """TC-A2: Count tokens for empty string"""
        result = count_tokens("")
        assert result == 0

    def test_count_tokens_special_characters(self):
        """TC-A3: Count tokens with special characters"""
        text = "Hello! How are you? #test @user $100"
        result = count_tokens(text)
        assert isinstance(result, int)
        assert result > 0

    def test_count_tokens_unicode(self):
        """TC-A4: Count tokens for multi-language text"""
        text = "Hello 你好 مرحبا שלום 🌍"
        result = count_tokens(text)
        assert isinstance(result, int)
        assert result > 0

    def test_count_tokens_invalid_model(self):
        """TC-A5: Invalid encoding model raises error"""
        with pytest.raises(TextProcessingError) as exc_info:
            count_tokens("test", model="invalid_model_name_12345")
        assert "encoding" in str(exc_info.value).lower() or "token" in str(exc_info.value).lower()


class TestNormalization:
    """Test Group B: Text Normalization"""

    def test_normalize_multiple_spaces(self):
        """TC-B1: Normalize text with multiple spaces"""
        result = normalize_text("Hello    world   test")
        assert result == "Hello world test"

    def test_normalize_control_characters(self):
        """TC-B2: Normalize text with control characters"""
        text = "Hello\x00\x01\x02World"
        result = normalize_text(text)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "Hello" in result
        assert "World" in result

    def test_normalize_mixed_line_endings(self):
        """TC-B3: Normalize mixed line endings"""
        text = "Line1\r\nLine2\rLine3\nLine4"
        result = normalize_text(text)
        assert "\r\n" not in result
        assert "\r" not in result
        assert result == "Line1\nLine2\nLine3\nLine4"

    def test_normalize_excessive_newlines(self):
        """TC-B4: Limit consecutive newlines"""
        text = "Para1\n\n\n\n\nPara2"
        result = normalize_text(text)
        assert "\n\n\n" not in result  # Max 2 newlines
        assert result == "Para1\n\nPara2"

    def test_normalize_empty_string(self):
        """TC-B5: Handle empty and whitespace-only strings"""
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""
        assert normalize_text("\n\n\n") == ""


class TestHTMLCleaning:
    """Test Group C: HTML Cleaning"""

    def test_clean_html_script_tags(self):
        """TC-C1: Clean HTML with script tags"""
        html = "<html><script>alert('x')</script><p>Content</p></html>"
        result = clean_html(html)
        assert "Content" in result
        assert "alert" not in result
        assert "<script>" not in result

    def test_clean_html_style_tags(self):
        """TC-C2: Clean HTML with style tags"""
        html = "<html><style>.class { color: red; }</style><p>Content</p></html>"
        result = clean_html(html)
        assert "Content" in result
        assert "color" not in result
        assert "<style>" not in result

    def test_clean_html_comments(self):
        """TC-C3: Clean HTML comments"""
        html = "<div>Text<!-- Comment -->More</div>"
        result = clean_html(html)
        assert "Text" in result
        assert "More" in result
        # Comments should be removed (BeautifulSoup handles this)

    def test_clean_html_complex_nested(self):
        """TC-C4: Clean complex nested HTML structure"""
        html = """
        <html>
            <head><title>Test</title></head>
            <body>
                <div class="container">
                    <h1>Header</h1>
                    <p>Paragraph <strong>bold</strong> text</p>
                    <ul><li>Item 1</li><li>Item 2</li></ul>
                </div>
            </body>
        </html>
        """
        result = clean_html(html)
        assert "Header" in result
        assert "Paragraph" in result
        assert "bold" in result
        assert "Item 1" in result
        assert "<div>" not in result

    def test_clean_html_malformed(self):
        """TC-C5: Handle malformed HTML"""
        html = "<div><p>Unclosed paragraph<div>Content</div>"
        result = clean_html(html)
        assert "Unclosed paragraph" in result
        assert "Content" in result

    def test_clean_html_empty_and_plain_text(self):
        """TC-C6: Handle empty HTML and plain text"""
        assert clean_html("") == ""
        result = clean_html("Plain text no HTML")
        assert "Plain text no HTML" in result


class TestMarkdownExtraction:
    """Test Group D: Markdown Extraction"""

    def test_extract_markdown_headers(self):
        """TC-D1: Extract text from headers"""
        markdown = "# Title\n## Subtitle\nContent"
        result = extract_markdown_text(markdown)
        assert "Title" in result
        assert "Subtitle" in result
        assert "Content" in result
        assert "#" not in result

    def test_extract_markdown_bold_italic(self):
        """TC-D2: Extract bold/italic text"""
        markdown = "This is **bold** and *italic* and ***both*** text"
        result = extract_markdown_text(markdown)
        assert "bold" in result
        assert "italic" in result
        assert "both" in result
        assert "**" not in result
        assert "*" not in result.replace("bold", "").replace("italic", "")

    def test_extract_markdown_links_images(self):
        """TC-D3: Extract link and image text"""
        markdown = "[link text](http://url.com) and ![alt text](image.png)"
        result = extract_markdown_text(markdown)
        assert "link text" in result
        assert "alt text" in result
        assert "http://url.com" not in result
        assert "image.png" not in result

    def test_extract_markdown_code_blocks(self):
        """TC-D4: Remove code blocks"""
        markdown = "Text before\n```python\ncode here\n```\nText after"
        result = extract_markdown_text(markdown)
        assert "Text before" in result
        assert "Text after" in result
        assert "code here" not in result
        assert "```" not in result

    def test_extract_markdown_lists(self):
        """TC-D5: Handle lists"""
        markdown = "- Item 1\n- Item 2\n\n1. First\n2. Second"
        result = extract_markdown_text(markdown)
        assert "Item 1" in result
        assert "Item 2" in result
        assert "First" in result
        assert "Second" in result
        assert "- " not in result
        assert "1. " not in result

    def test_extract_markdown_blockquotes(self):
        """TC-D6: Handle blockquotes"""
        markdown = "> This is a quote\n> Second line\n\nRegular text"
        result = extract_markdown_text(markdown)
        assert "This is a quote" in result
        assert "Second line" in result
        assert "Regular text" in result
        assert "> " not in result

    def test_extract_markdown_complex(self):
        """TC-D7: Handle complex mixed Markdown"""
        markdown = """
# Main Title

This is **bold** and *italic*.

- List item 1
- List item 2

[Link](http://example.com)

```python
def test():
    pass
```

> Quote text

Regular paragraph.
        """
        result = extract_markdown_text(markdown)
        assert "Main Title" in result
        assert "bold" in result
        assert "italic" in result
        assert "List item 1" in result
        assert "Link" in result
        assert "Quote text" in result
        assert "Regular paragraph" in result
        assert "def test():" not in result
        assert "#" not in result


class TestTextChunking:
    """Test Group E: Text Chunking (Core Functionality)"""

    def test_single_chunk_text(self):
        """TC-E1: Chunk text that fits in single chunk"""
        text = "This is a short text that will fit in one chunk."
        result = chunk_text(text, chunk_size=500, chunk_overlap=50)
        assert len(result) == 1
        assert result[0].strip() == text.strip()
        assert count_tokens(result[0]) < 500

    def test_multi_chunk_with_paragraphs(self):
        """TC-E2: Chunk text requiring multiple chunks with paragraph breaks"""
        # Create text with paragraph breaks
        paragraphs = [f"Paragraph {i}. " + "Word " * 30 for i in range(10)]
        text = "\n\n".join(paragraphs)
        result = chunk_text(text, chunk_size=100, chunk_overlap=10)

        assert len(result) > 1
        for chunk in result:
            tokens = count_tokens(chunk)
            assert tokens <= 100, f"Chunk has {tokens} tokens, expected <= 100"

    def test_verify_overlap(self):
        """TC-E3: Verify chunk overlap"""
        # Create text that will require multiple chunks
        text = "Word " * 200  # Simple repeated text
        result = chunk_text(text, chunk_size=100, chunk_overlap=20)

        assert len(result) >= 2
        # Check that consecutive chunks have some overlap
        for i in range(len(result) - 1):
            chunk1 = result[i]
            chunk2 = result[i + 1]
            # Simple check: some words from end of chunk1 should appear in chunk2
            chunk1_words = chunk1.split()[-10:]  # Last 10 words
            chunk2_words = chunk2.split()[:10]   # First 10 words
            overlap_count = len(set(chunk1_words) & set(chunk2_words))
            assert overlap_count > 0, "Expected some overlap between consecutive chunks"

    def test_token_based_sizing(self):
        """TC-E4: Verify token-based chunk sizing"""
        # Create text with known token count
        text = "Test " * 600  # Should create text requiring multiple chunks
        result = chunk_text(text, chunk_size=500, chunk_overlap=50)

        assert len(result) >= 2
        for chunk in result:
            tokens = count_tokens(chunk)
            assert tokens <= 500, f"Chunk exceeded size limit: {tokens} tokens"

    def test_invalid_chunk_parameters(self):
        """TC-E8: Invalid parameters raise ValueError"""
        text = "Test text"

        # chunk_size = 0
        with pytest.raises(ValueError) as exc:
            chunk_text(text, chunk_size=0)
        assert "chunk_size" in str(exc.value).lower()

        # chunk_size < 0
        with pytest.raises(ValueError) as exc:
            chunk_text(text, chunk_size=-10)
        assert "chunk_size" in str(exc.value).lower()

        # chunk_overlap >= chunk_size
        with pytest.raises(ValueError) as exc:
            chunk_text(text, chunk_size=100, chunk_overlap=100)
        assert "overlap" in str(exc.value).lower()

        with pytest.raises(ValueError) as exc:
            chunk_text(text, chunk_size=100, chunk_overlap=150)
        assert "overlap" in str(exc.value).lower()

    def test_empty_text_input(self):
        """TC-E9: Empty text input returns empty list"""
        result = chunk_text("", chunk_size=500, chunk_overlap=50)
        assert result == []

        result = chunk_text("   ", chunk_size=500, chunk_overlap=50)
        assert result == []


class TestDocumentBatching:
    """Test Group F: Document Batch Processing"""

    def test_batch_with_metadata_preservation(self):
        """TC-F1: Chunk multiple documents with metadata preservation"""
        documents = [
            {'content': 'Short text', 'source': 'jira', 'issue_key': 'PROJ-1'},
            {'content': 'Word ' * 300, 'source': 'confluence', 'page_id': '123'}
        ]

        result = chunk_documents(documents, chunk_size=100, chunk_overlap=10)

        assert len(result) > 0
        # Check metadata preservation
        for chunk in result:
            assert 'source' in chunk
            assert 'content' in chunk
            # Check that original metadata is preserved
            if chunk['source'] == 'jira':
                assert 'issue_key' in chunk
            elif chunk['source'] == 'confluence':
                assert 'page_id' in chunk

    def test_chunk_index_metadata(self):
        """TC-F2: Verify chunk_index and total_chunks metadata"""
        documents = [
            {'content': 'Word ' * 300}  # Will create multiple chunks
        ]

        result = chunk_documents(documents, chunk_size=100, chunk_overlap=10)

        assert len(result) > 1
        total = result[0]['total_chunks']

        for i, chunk in enumerate(result):
            assert chunk['chunk_index'] == i
            assert chunk['total_chunks'] == total

    def test_missing_content_key(self):
        """TC-F3: Handle documents missing content key"""
        documents = [
            {'source': 'test', 'data': 'no content key here'}
        ]

        # Should return empty list and log warning (not crash)
        result = chunk_documents(documents)
        assert result == []

    def test_mixed_document_sizes(self):
        """TC-F4: Handle mixed document sizes"""
        documents = [
            {'content': 'Short'},
            {'content': 'Word ' * 300},  # Long, will chunk
            {'content': 'Also short'}
        ]

        result = chunk_documents(documents, chunk_size=100, chunk_overlap=10)

        assert len(result) > 3  # At least 3 (one long doc will be chunked)
        # Verify all have metadata
        for chunk in result:
            assert 'chunk_index' in chunk
            assert 'total_chunks' in chunk

    def test_custom_content_key(self):
        """TC-F5: Custom content key parameter"""
        documents = [
            {'text': 'Content here', 'source': 'test'}
        ]

        result = chunk_documents(documents, content_key='text', chunk_size=100)

        assert len(result) == 1
        assert result[0]['text'] == 'Content here'
        assert result[0]['source'] == 'test'
