-- Enums
CREATE TYPE content_type_enum AS ENUM ('text', 'image', 'table');
CREATE TYPE upload_status_enum AS ENUM ('pending', 'processing', 'completed', 'failed');
CREATE TYPE storage_provider_enum AS ENUM ('cloudinary', 's3', 'gcs');
CREATE TYPE study_plan_status_enum AS ENUM ('draft', 'active', 'completed', 'archived');
CREATE TYPE session_status_enum AS ENUM ('active', 'paused', 'completed', 'pending');
CREATE TYPE message_role_enum AS ENUM ('user', 'ai', 'tool');
CREATE TYPE section_progress_status_enum AS ENUM ('pending', 'in_progress', 'completed', 'skipped');

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_superuser BOOLEAN NOT NULL DEFAULT false,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    storage_provider storage_provider_enum NOT NULL DEFAULT 'cloudinary',
    storage_url VARCHAR(1024) NOT NULL,
    storage_public_id VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(128),
    size_bytes INTEGER,
    pages INTEGER,
    title VARCHAR(255),
    status upload_status_enum NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Document Chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    bbox_x0 FLOAT,
    bbox_y0 FLOAT,
    bbox_x1 FLOAT,
    bbox_y1 FLOAT,
    content_type content_type_enum NOT NULL DEFAULT 'text',
    text_content TEXT,
    blob_url VARCHAR(1024),
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Study Plans table
CREATE TABLE IF NOT EXISTS study_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE NOT NULL,
    plan JSONB NOT NULL,
    title VARCHAR(255),
    version INTEGER NOT NULL DEFAULT 1,
    status study_plan_status_enum NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Study Plan Sections table
CREATE TABLE IF NOT EXISTS study_plan_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_plan_id UUID REFERENCES study_plans(id) ON DELETE CASCADE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    "order" INTEGER NOT NULL,
    estimated_minutes INTEGER,
    content JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Learning Sessions table
CREATE TABLE IF NOT EXISTS learning_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    study_plan_id UUID REFERENCES study_plans(id) ON DELETE SET NULL,
    status session_status_enum NOT NULL DEFAULT 'active',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Section Progress table
CREATE TABLE IF NOT EXISTS section_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES learning_sessions(id) ON DELETE CASCADE NOT NULL,
    section_id UUID REFERENCES study_plan_sections(id) ON DELETE CASCADE NOT NULL,
    status section_progress_status_enum NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Session Messages table
CREATE TABLE IF NOT EXISTS session_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES learning_sessions(id) ON DELETE CASCADE NOT NULL,
    role message_role_enum NOT NULL,
    content TEXT,
    tool_called VARCHAR(128),
    latency_ms INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_usd_millis INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Tool Calls table
CREATE TABLE IF NOT EXISTS tool_calls (
    id SERIAL PRIMARY KEY,
    session_message_id UUID REFERENCES session_messages(id),
    tool_name VARCHAR(255),
    params JSONB,
    response JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Add a sample user for testing
INSERT INTO users (id, email, hashed_password, is_active, is_superuser, is_verified)
VALUES (gen_random_uuid(), 'test@example.com', 'hashed_password', true, false, true)
ON CONFLICT (email) DO NOTHING;
