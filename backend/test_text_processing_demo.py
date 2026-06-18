#!/usr/bin/env python3
"""
Quick demonstration script for text processing utilities.
This script shows basic usage of the text processing module.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.text_processing import (
    chunk_text,
    clean_html,
    extract_markdown_text,
    count_tokens,
    normalize_text,
    chunk_documents,
)


def demo_normalize():
    """Demo text normalization."""
    print("=" * 60)
    print("DEMO: Text Normalization")
    print("=" * 60)
    
    messy_text = "  Hello    world!  \n\n\n\n  Multiple   spaces   \r\nand  line breaks  "
    normalized = normalize_text(messy_text)
    
    print(f"Original: {repr(messy_text)}")
    print(f"Normalized: {repr(normalized)}")
    print()


def demo_html_cleaning():
    """Demo HTML cleaning."""
    print("=" * 60)
    print("DEMO: HTML Cleaning")
    print("=" * 60)
    
    html = """
    <html>
        <head>
            <script>alert('remove me');</script>
            <style>body { color: red; }</style>
        </head>
        <body>
            <h1>Important Title</h1>
            <p>This is <strong>important</strong> content.</p>
            <!-- This is a comment -->
        </body>
    </html>
    """
    
    clean = clean_html(html)
    print(f"HTML Input (truncated): {html[:100]}...")
    print(f"Cleaned Text: {clean}")
    print()


def demo_markdown_extraction():
    """Demo Markdown text extraction."""
    print("=" * 60)
    print("DEMO: Markdown Text Extraction")
    print("=" * 60)
    
    markdown = """
# Main Title

This is **bold** and this is *italic*.

## Subtitle

Here's a [link](https://example.com) and an image ![alt](image.png).

```python
# This code block should be removed
print("hello")
```

- List item 1
- List item 2
    """
    
    extracted = extract_markdown_text(markdown)
    print("Markdown Input:")
    print(markdown)
    print("\nExtracted Text:")
    print(extracted)
    print()


def demo_token_counting():
    """Demo token counting."""
    print("=" * 60)
    print("DEMO: Token Counting")
    print("=" * 60)
    
    texts = [
        "Hello, world!",
        "This is a longer sentence with more tokens.",
        "A" * 1000,  # Long repetitive text
    ]
    
    for text in texts:
        count = count_tokens(text)
        display = text if len(text) < 50 else text[:47] + "..."
        print(f"Text: {repr(display)}")
        print(f"Tokens: {count}")
        print()


def demo_chunking():
    """Demo text chunking."""
    print("=" * 60)
    print("DEMO: Text Chunking")
    print("=" * 60)
    
    # Create a long text
    long_text = " ".join([f"This is sentence number {i}." for i in range(200)])
    
    chunks = chunk_text(long_text, chunk_size=100, chunk_overlap=20)
    
    print(f"Original text length: {len(long_text)} characters")
    print(f"Original token count: {count_tokens(long_text)}")
    print(f"Number of chunks: {len(chunks)}")
    print()
    
    for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
        print(f"Chunk {i + 1} (tokens: {count_tokens(chunk)}):")
        print(f"  {chunk[:100]}...")
        print()


def demo_document_chunking():
    """Demo document batch chunking."""
    print("=" * 60)
    print("DEMO: Document Batch Chunking")
    print("=" * 60)
    
    docs = [
        {
            'content': " ".join([f"Document 1 sentence {i}." for i in range(100)]),
            'source': 'confluence',
            'page_id': '12345',
        },
        {
            'content': " ".join([f"Document 2 sentence {i}." for i in range(80)]),
            'source': 'jira',
            'issue_key': 'PROJ-456',
        },
    ]
    
    chunked = chunk_documents(docs, chunk_size=50, chunk_overlap=10)
    
    print(f"Original documents: {len(docs)}")
    print(f"Total chunks: {len(chunked)}")
    print()
    
    for chunk in chunked[:2]:  # Show first 2 chunks
        print(f"Chunk from {chunk['source']}:")
        print(f"  Metadata: chunk {chunk['chunk_index'] + 1}/{chunk['total_chunks']}")
        print(f"  Content preview: {chunk['content'][:80]}...")
        print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("TEXT PROCESSING UTILITIES DEMONSTRATION")
    print("=" * 60 + "\n")
    
    demo_normalize()
    demo_html_cleaning()
    demo_markdown_extraction()
    demo_token_counting()
    demo_chunking()
    demo_document_chunking()
    
    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
