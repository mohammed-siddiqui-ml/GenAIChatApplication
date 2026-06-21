# Admin User Setup Guide

## Overview

This guide explains how to set up the admin user for accessing the admin portal after deploying the GenAI Chat Application.

## Prerequisites

- Docker and Docker Compose installed
- Application successfully deployed and running
- Database migrations completed (`alembic upgrade head`)

## Creating the Admin User

### Method 1: Using SQL (Recommended for Fresh Deployments)

After running migrations, create the admin user directly in the database:

```bash
# Connect to PostgreSQL container
docker exec -i knowledge_postgres psql -U user -d knowledge_db << 'EOF'

-- Create user_role enum (if not exists from migration)
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'user');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create users table (if not exists from migration)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role user_role DEFAULT 'user'::user_role NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Create audit_logs table (if not exists from migration)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INTEGER,
    changes JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create indexes for audit_logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);

-- Insert admin user
-- Password: admin123 (CHANGE THIS IN PRODUCTION!)
INSERT INTO users (email, password_hash, role, is_active)
VALUES (
    'admin@example.com',
    '$2b$12$saHjzVr839oftnwAgyQ.veBVG3rsiuPj6A0ccH1cob3NZuCq0ZT8W',
    'admin'::user_role,
    true
)
ON CONFLICT (email) DO UPDATE
SET password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role,
    updated_at = NOW();

-- Verify admin user was created
SELECT id, email, role, is_active FROM users WHERE email = 'admin@example.com';
EOF
```

### Method 2: Using Python Script

```bash
# Copy the script to the backend container
docker cp docs/scripts/create_admin.py knowledge_backend:/app/

# Run the script
docker exec knowledge_backend python3 /app/create_admin.py
```

## Default Credentials

**⚠️ IMPORTANT: Change these credentials in production!**

- **Email:** `admin@example.com`
- **Password:** `admin123`

## Accessing the Admin Portal

### Via Web Browser

1. Navigate to: `http://localhost:3000/login`
2. Enter the admin credentials
3. Click "Login"
4. You'll be redirected to the dashboard
5. Access admin portal at: `http://localhost:3000/admin`

### Via API (for testing)

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'

# Response includes access_token, refresh_token, and user info
```

## Changing the Admin Password

### Method 1: Through the UI
1. Log in to the admin portal
2. Navigate to user settings
3. Change password

### Method 2: Through the Database

```bash
# Generate a new bcrypt hash
docker exec knowledge_backend python3 << 'PYTHON'
import bcrypt
password = b"your_new_password"
hashed = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
print(hashed.decode('utf-8'))
PYTHON

# Update the database with the new hash
docker exec -i knowledge_postgres psql -U user -d knowledge_db << 'EOF'
UPDATE users 
SET password_hash = '<paste_hash_here>',
    updated_at = NOW()
WHERE email = 'admin@example.com';
EOF
```

## Security Best Practices

1. **Change default password immediately** after first login
2. **Use strong passwords** (minimum 12 characters, mixed case, numbers, symbols)
3. **Restrict admin access** to trusted IP addresses in production
4. **Enable 2FA** if implementing additional security features
5. **Regularly rotate credentials**
6. **Monitor audit logs** for suspicious admin activity

## Troubleshooting

### "Invalid email or password" Error

1. Verify the user exists:
```bash
docker exec knowledge_postgres psql -U user -d knowledge_db \
  -c "SELECT id, email, role, is_active FROM users WHERE email = 'admin@example.com';"
```

2. Check if the user is active:
```sql
UPDATE users SET is_active = true WHERE email = 'admin@example.com';
```

3. Reset the password using Method 2 above

### "Unauthorized" or "403 Forbidden" Error

- Verify the user has admin role:
```bash
docker exec knowledge_postgres psql -U user -d knowledge_db \
  -c "UPDATE users SET role = 'admin'::user_role WHERE email = 'admin@example.com';"
```

### Database Connection Issues

- Ensure PostgreSQL is running: `docker ps | grep postgres`
- Check database logs: `docker logs knowledge_postgres`
- Verify migrations: `docker exec knowledge_backend alembic current`

## See Also

- [Setup Guide](setup.md) - Complete application setup
- [Deployment Guide](deployment.md) - Production deployment
- [API Documentation](http://localhost:8000/api/v1/docs) - Interactive API docs
