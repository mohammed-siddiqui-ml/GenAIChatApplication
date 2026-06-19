# API Documentation

## Table of Contents
- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Authentication](#authentication-endpoints)
  - [Chat](#chat-endpoints)
  - [Admin](#admin-endpoints)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

## Overview

The GenAI Knowledge Retrieval System provides a RESTful API with real-time WebSocket support for chat functionality. The API uses JWT tokens for authentication and returns JSON responses.

### API Version
- **Current Version**: v1
- **Base Path**: `/api/v1`
- **Interactive Documentation**: http://localhost:8000/api/v1/docs
- **OpenAPI Schema**: http://localhost:8000/api/v1/openapi.json

## Base URL

### Development
```
http://localhost:8000/api/v1
```

### Production
```
https://yourdomain.com/api/v1
```

## Authentication

The API uses JWT (JSON Web Token) based authentication with HTTP-only cookies.

### Authentication Flow

1. **Register** a new user account
2. **Login** to receive access and refresh tokens
3. Include **access token** in subsequent requests via:
   - Cookie (set automatically)
   - OR `Authorization: Bearer <token>` header

### Token Expiration
- **Access Token**: 24 hours
- **Refresh Token**: 7 days

## API Endpoints

### Authentication Endpoints

#### 1. Register User

Create a new user account.

**Endpoint**: `POST /api/v1/auth/register`

**Request Body**:
```json
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "SecureP@ss123"
}
```

**Response**: `201 Created`
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "johndoe",
  "is_active": true,
  "is_admin": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "johndoe",
    "password": "SecureP@ss123"
  }'
```

#### 2. Login

Authenticate and receive JWT tokens.

**Endpoint**: `POST /api/v1/auth/login`

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "SecureP@ss123"
}
```

**Response**: `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecureP@ss123"
  }'
```

#### 3. Logout

Invalidate current session.

**Endpoint**: `POST /api/v1/auth/logout`

**Headers**: 
- `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "message": "Successfully logged out"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 4. Get Current User

Retrieve authenticated user profile.

**Endpoint**: `GET /api/v1/auth/me`

**Headers**: 
- `Authorization: Bearer <access_token>`

**Response**: `200 OK`
```json
{
  "id": 1,
  "email": "user@example.com",
  "username": "johndoe",
  "is_active": true,
  "is_admin": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Example**:
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Chat Endpoints

#### 1. Create Session

Create a new chat session.

**Endpoint**: `POST /api/v1/chat/session`

**Headers**: 
- `Authorization: Bearer <access_token>` (optional for non-authenticated users)

**Request Body** (optional):
```json
{
  "metadata": {
    "source": "web",
    "user_agent": "Mozilla/5.0..."
  }
}
```

**Response**: `201 Created`
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/chat/session \
  -H "Content-Type: application/json"
```

#### 2. Query Chat

Send a query and receive AI-generated response with RAG.

**Endpoint**: `POST /api/v1/chat/query`

**Headers**:
- `X-Session-Token: <session_token>` (required)

**Request Body**:
```json
{
  "query": "How do I reset my password?",
  "stream": false,
  "top_k": 5
}
```

**Response**: `200 OK`
```json
{
  "content": "To reset your password, follow these steps:\n1. Go to login page\n2. Click 'Forgot Password'\n3. Enter your email...",
  "sources": [
    {
      "id": 123,
      "title": "Password Reset Guide",
      "similarity": 0.92,
      "url": "https://confluence.example.com/docs/password-reset"
    }
  ],
  "metadata": {
    "tokens_used": 450,
    "duration_ms": 1200
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": 42
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "query": "How do I reset my password?",
    "stream": false
  }'
```

### Admin Endpoints

All admin endpoints require authentication with admin privileges.

**Headers Required**:
- `Authorization: Bearer <admin_access_token>`

#### 1. Get System Metrics

Retrieve system metrics and statistics.

**Endpoint**: `GET /api/v1/admin/metrics`

**Response**: `200 OK`
```json
{
  "total_documents": 15234,
  "sessions": {
    "active_sessions": 23,
    "total_sessions": 8901
  },
  "queries": {
    "total_today": 1456,
    "avg_response_time_ms": 1250
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE"
}
```

### HTTP Status Codes

- `200 OK`: Success
- `201 Created`: Resource created
- `400 Bad Request`: Invalid request
- `401 Unauthorized`: Authentication failed
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Rate Limiting

- **API Endpoints**: 30 requests/second per IP
- **Login Endpoint**: 5 requests/minute per IP
- **Chat Query**: 10 requests/minute per session

## Support

- **Interactive Docs**: http://localhost:8000/api/v1/docs
- **GitHub Issues**: https://github.com/your-org/your-repo/issues
