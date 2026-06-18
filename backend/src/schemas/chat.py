"""
Chat Request/Response Schemas

This module defines Pydantic schemas for chat API endpoints including
request validation and response models for chat sessions and queries.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    """
    Request schema for chat query endpoint.
    
    Validates user query with optional parameters for RAG pipeline configuration.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's natural language query",
        examples=["How do I reset my password?"]
    )
    stream: bool = Field(
        default=True,
        description="Whether to stream the response using Server-Sent Events",
        examples=[True, False]
    )
    top_k: Optional[int] = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of similar document chunks to retrieve",
        examples=[10]
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response generation (0.0 = deterministic, 2.0 = creative)",
        examples=[0.7]
    )
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "How do I reset my password?",
                    "stream": True,
                    "top_k": 10,
                    "temperature": 0.7
                }
            ]
        }
    }


class SourceCitation(BaseModel):
    """Source citation for RAG response."""
    id: int = Field(..., description="Source document ID")
    title: str = Field(..., description="Document title")
    url: Optional[str] = Field(None, description="Document URL")
    type: str = Field(..., description="Content type (confluence, issue_tracker, onboarding)")
    similarity: float = Field(..., description="Similarity score (0.0 to 1.0)")
    chunk_index: int = Field(..., description="Chunk index in source document")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional source metadata")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 123,
                    "title": "Password Reset Guide",
                    "url": "https://confluence.example.com/password-reset",
                    "type": "confluence",
                    "similarity": 0.92,
                    "chunk_index": 2,
                    "metadata": {"author": "admin", "updated_at": "2024-01-15"}
                }
            ]
        }
    }


class QueryResponse(BaseModel):
    """
    Response schema for non-streaming chat query.
    
    Contains the generated response, source citations, and metadata.
    """
    content: str = Field(..., description="Generated response content")
    sources: List[SourceCitation] = Field(default_factory=list, description="Source citations")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata (tokens, duration, etc.)"
    )
    session_id: UUID = Field(..., description="Chat session ID")
    message_id: int = Field(..., description="Message ID in database")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "To reset your password, go to Settings > Security > Reset Password...",
                    "sources": [
                        {
                            "id": 123,
                            "title": "Password Reset Guide",
                            "url": "https://confluence.example.com/password-reset",
                            "type": "confluence",
                            "similarity": 0.92,
                            "chunk_index": 2,
                            "metadata": {}
                        }
                    ],
                    "metadata": {
                        "tokens_used": 450,
                        "duration_ms": 1200,
                        "num_sources": 3
                    },
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "message_id": 42
                }
            ]
        }
    }


class SessionResponse(BaseModel):
    """Response schema for session creation."""
    session_id: UUID = Field(..., description="Unique session identifier")
    session_token: str = Field(..., description="Session token for authentication")
    created_at: datetime = Field(..., description="Session creation timestamp")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "session_token": "abc123def456...",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            ]
        }
    }
