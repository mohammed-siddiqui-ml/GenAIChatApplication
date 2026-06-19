"""
Text Processing Utilities

This module provides text processing utilities for document chunking, cleaning,
and tokenization. Supports different content types (HTML, Markdown, plain text).
"""

import re
import logging
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import tiktoken

# Logger
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CHUNK_SIZE = 500  # tokens
DEFAULT_CHUNK_OVERLAP = 50  # tokens
DEFAULT_ENCODING_MODEL = "cl100k_base"  # Compatible with GPT-4, GPT-3.5-turbo


class TextProcessingError(Exception):
    """Custom exception for text processing errors."""
    pass


def count_tokens(text: str, model: str = DEFAULT_ENCODING_MODEL) -> int:
    """
    Count tokens in text using tiktoken library.

    Args:
        text: Text to count tokens for
        model: Encoding model name (default: cl100k_base)

    Returns:
        int: Number of tokens in the text

    Raises:
        TextProcessingError: If token counting fails
    """
    try:
        encoding = tiktoken.get_encoding(model)
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        logger.error(f"Token counting failed: {e}")
        raise TextProcessingError(f"Failed to count tokens: {e}")


def normalize_text(text: str) -> str:
    """
    Normalize text by cleaning whitespace and special characters.

    - Replaces multiple whitespace with single space
    - Removes leading/trailing whitespace
    - Normalizes line breaks
    - Removes control characters

    Args:
        text: Text to normalize

    Returns:
        str: Normalized text
    """
    if not text:
        return ""

    # Remove control characters (except newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Normalize line breaks (convert \r\n and \r to \n)
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)

    # Replace multiple newlines with maximum two newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    # Remove leading/trailing whitespace from entire text
    text = text.strip()

    return text


def clean_html(html_content: str) -> str:
    """
    Clean HTML content and extract plain text.

    - Removes script and style tags
    - Removes HTML comments
    - Extracts text content
    - Normalizes whitespace

    Args:
        html_content: HTML content to clean

    Returns:
        str: Cleaned plain text

    Raises:
        TextProcessingError: If HTML cleaning fails
    """
    try:
        # Parse HTML with BeautifulSoup (using built-in html.parser for better test compatibility)
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(['script', 'style', 'noscript']):
            script.decompose()

        # Remove HTML comments
        for comment in soup.find_all(text=lambda text: isinstance(text, str) and text.strip().startswith('<!--')):
            comment.extract()

        # Get text content
        text = soup.get_text(separator=' ', strip=True)

        # Normalize the extracted text
        text = normalize_text(text)

        return text

    except Exception as e:
        logger.error(f"HTML cleaning failed: {e}")
        raise TextProcessingError(f"Failed to clean HTML: {e}")


def extract_markdown_text(markdown_content: str) -> str:
    """
    Extract plain text from Markdown content.

    - Removes Markdown formatting (headers, bold, italic, links, etc.)
    - Preserves text content
    - Normalizes whitespace

    Args:
        markdown_content: Markdown content to process

    Returns:
        str: Plain text extracted from Markdown
    """
    if not markdown_content:
        return ""

    text = markdown_content

    # Remove code blocks (```...```)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Remove inline code (`...`)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Remove images (![alt](url))
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # Remove links but keep text ([text](url))
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove headers (### Header)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic (**text** or __text__ or *text* or _text_)
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Remove horizontal rules (---, ***, ___)
    text = re.sub(r'^[\-\*_]{3,}$', '', text, flags=re.MULTILINE)

    # Remove blockquotes (> text)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # Remove list markers (-, *, +, 1.)
    text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    # Normalize the extracted text
    text = normalize_text(text)

    return text


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    encoding_model: str = DEFAULT_ENCODING_MODEL,
) -> List[str]:
    """
    Split text into chunks with token-based sizing and overlap.

    Uses recursive character-based splitting to maintain context between chunks.
    Chunks are sized based on token count, not character count.

    Args:
        text: Text to chunk
        chunk_size: Maximum tokens per chunk (default: 500)
        chunk_overlap: Number of tokens to overlap between chunks (default: 50)
        encoding_model: Tiktoken encoding model (default: cl100k_base)

    Returns:
        List[str]: List of text chunks

    Raises:
        TextProcessingError: If chunking fails
        ValueError: If chunk_size or chunk_overlap are invalid
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")

    if not text or not text.strip():
        return []

    try:
        encoding = tiktoken.get_encoding(encoding_model)

        # Normalize the input text
        text = normalize_text(text)

        # Split by common separators (in order of preference)
        separators = ['\n\n', '\n', '. ', '! ', '? ', '; ', ', ', ' ', '']

        chunks = _recursive_split_text(
            text=text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            encoding=encoding,
            separators=separators,
        )

        logger.info(f"Split text into {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")
        return chunks

    except Exception as e:
        logger.error(f"Text chunking failed: {e}")
        raise TextProcessingError(f"Failed to chunk text: {e}")


def _recursive_split_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    encoding: Any,
    separators: List[str],
) -> List[str]:
    """
    Recursively split text using separators with token-based sizing.

    Args:
        text: Text to split
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Number of tokens to overlap
        encoding: Tiktoken encoding instance
        separators: List of separators to try (in order)

    Returns:
        List[str]: List of text chunks
    """
    final_chunks = []

    # Base case: if text is small enough, return as single chunk
    token_count = len(encoding.encode(text))
    if token_count <= chunk_size:
        return [text] if text.strip() else []

    # Try each separator
    separator = separators[0] if separators else ''

    if separator:
        splits = text.split(separator)
    else:
        splits = [text]

    # Merge splits into chunks
    good_splits = []
    current_chunk = []
    current_tokens = 0

    for split in splits:
        if not split.strip():
            continue

        split_tokens = len(encoding.encode(split))

        # If adding this split would exceed chunk size, finalize current chunk
        if current_tokens + split_tokens > chunk_size and current_chunk:
            # Join current chunk with separator
            chunk_text = separator.join(current_chunk) if separator else ''.join(current_chunk)
            good_splits.append(chunk_text)

            # Start new chunk with overlap
            # Calculate how many splits to keep for overlap
            overlap_chunks = []
            overlap_tokens = 0
            for prev_split in reversed(current_chunk):
                prev_tokens = len(encoding.encode(prev_split))
                if overlap_tokens + prev_tokens <= chunk_overlap:
                    overlap_chunks.insert(0, prev_split)
                    overlap_tokens += prev_tokens
                else:
                    break

            current_chunk = overlap_chunks
            current_tokens = overlap_tokens

        # Add split to current chunk
        current_chunk.append(split)
        current_tokens += split_tokens

    # Add remaining chunk
    if current_chunk:
        chunk_text = separator.join(current_chunk) if separator else ''.join(current_chunk)
        good_splits.append(chunk_text)

    # Recursively split any chunks that are still too large
    for split in good_splits:
        split_tokens = len(encoding.encode(split))
        if split_tokens > chunk_size and len(separators) > 1:
            # Try next separator
            sub_chunks = _recursive_split_text(
                text=split,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                encoding=encoding,
                separators=separators[1:],
            )
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(split)

    return final_chunks


def chunk_documents(
    documents: List[Dict[str, Any]],
    content_key: str = 'content',
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    preserve_metadata: bool = True,
) -> List[Dict[str, Any]]:
    """
    Chunk multiple documents while preserving metadata.

    Args:
        documents: List of document dictionaries with content and metadata
        content_key: Key in document dict containing text content (default: 'content')
        chunk_size: Maximum tokens per chunk (default: 500)
        chunk_overlap: Number of tokens to overlap (default: 50)
        preserve_metadata: Whether to copy metadata to each chunk (default: True)

    Returns:
        List[Dict[str, Any]]: List of chunked documents with metadata

    Example:
        >>> docs = [
        ...     {'content': 'Long text...', 'source': 'doc1.txt', 'page': 1},
        ...     {'content': 'More text...', 'source': 'doc2.txt', 'page': 2}
        ... ]
        >>> chunks = chunk_documents(docs)
        >>> # Each chunk will have: content, source, page, chunk_index, total_chunks
    """
    chunked_documents = []

    for doc in documents:
        if content_key not in doc:
            logger.warning(f"Document missing '{content_key}' key, skipping")
            continue

        content = doc[content_key]

        # Chunk the content
        chunks = chunk_text(
            text=content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # Create chunk documents
        for idx, chunk in enumerate(chunks):
            chunk_doc = {content_key: chunk}

            # Preserve metadata if requested
            if preserve_metadata:
                for key, value in doc.items():
                    if key != content_key:
                        chunk_doc[key] = value

                # Add chunking metadata
                chunk_doc['chunk_index'] = idx
                chunk_doc['total_chunks'] = len(chunks)

            chunked_documents.append(chunk_doc)

    logger.info(f"Chunked {len(documents)} documents into {len(chunked_documents)} chunks")
    return chunked_documents


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF file.

    NOTE: This is a stub implementation for testing.
    In production, use PyPDF2, pdfplumber, or pypdf.

    Args:
        pdf_path: Path to PDF file

    Returns:
        str: Extracted text content

    Raises:
        TextProcessingError: If PDF extraction fails
    """
    logger.warning(f"PDF extraction using stub implementation: {pdf_path}")

    # Stub implementation - returns placeholder text
    # In production, would use:
    # import PyPDF2
    # with open(pdf_path, 'rb') as file:
    #     reader = PyPDF2.PdfReader(file)
    #     text = ""
    #     for page in reader.pages:
    #         text += page.extract_text()
    #     return text

    return f"Extracted text from PDF: {pdf_path}\n\nThis is placeholder content from stub implementation."


def parse_markdown(markdown_content: str) -> Dict[str, Any]:
    """
    Parse Markdown content into structured data.

    NOTE: This is a simplified implementation for testing.
    In production, use markdown library or mistune for full parsing.

    Args:
        markdown_content: Markdown text to parse

    Returns:
        dict: Parsed content with metadata (content, headings, links)
    """
    if not markdown_content:
        return {
            "content": "",
            "headings": [],
            "links": []
        }

    # Extract plain text using existing function
    plain_text = extract_markdown_text(markdown_content)

    # Extract headings (lines starting with #)
    headings = []
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    for match in heading_pattern.finditer(markdown_content):
        level = len(match.group(1))
        text = match.group(2)
        headings.append({"level": level, "text": text})

    # Extract links ([text](url))
    links = []
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
    for match in link_pattern.finditer(markdown_content):
        links.append({
            "text": match.group(1),
            "url": match.group(2)
        })

    return {
        "content": plain_text,
        "headings": headings,
        "links": links
    }

