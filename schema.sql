-- =======================================
-- Enable extensions
-- =======================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =======================================
-- USERS
-- =======================================
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,           -- telegram_id
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    company VARCHAR(255),
    role VARCHAR(255),
    linkedin_url VARCHAR(500),
    current_city VARCHAR(255) NOT NULL,
    current_lat DOUBLE PRECISION NOT NULL,
    current_lon DOUBLE PRECISION NOT NULL,
    planned_locations JSONB DEFAULT '[]',
    interests JSONB DEFAULT '[]',          -- ["AI", "startups", "SaaS"]
    budget_limit_ticket DOUBLE PRECISION DEFAULT 50.0,
    budget_limit_transport DOUBLE PRECISION DEFAULT 20.0,
    preferred_languages JSONB DEFAULT '["en"]',
    preferred_time VARCHAR(20) DEFAULT 'any',
    registration_data JSONB DEFAULT '{}',  -- all fields for auto-fill
    onboarding_complete BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =======================================
-- EVENTS
-- =======================================
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT REFERENCES users(user_id),
    source VARCHAR(20) NOT NULL,           -- "luma" | "meetup" | "other"
    source_id VARCHAR(255) NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    datetime_start TIMESTAMP NOT NULL,
    datetime_end TIMESTAMP,
    location_name VARCHAR(500),
    location_address TEXT,
    location_city VARCHAR(255),
    location_lat DOUBLE PRECISION,
    location_lon DOUBLE PRECISION,
    ticket_price DOUBLE PRECISION,         -- NULL = free
    currency VARCHAR(10) DEFAULT 'EUR',
    language VARCHAR(10),
    event_type VARCHAR(50),                -- conference, meetup, workshop, networking_dinner, other
    categories JSONB DEFAULT '[]',
    organizer_name VARCHAR(500),
    organizer_url TEXT,
    organizer_info TEXT,
    capacity INTEGER,
    requires_approval BOOLEAN DEFAULT FALSE,
    food_included BOOLEAN DEFAULT FALSE,
    dress_code VARCHAR(255),
    estimated_audience INTEGER,
    deterministic_score DOUBLE PRECISION DEFAULT 0,
    semantic_score DOUBLE PRECISION DEFAULT 0,
    total_score DOUBLE PRECISION DEFAULT 0,
    transport_mode VARCHAR(50),
    transport_cost DOUBLE PRECISION,
    transport_duration_min INTEGER,
    total_estimated_cost DOUBLE PRECISION,
    additional_costs_note TEXT,
    recommendation VARCHAR(50),
    recommendation_reason TEXT,
    status VARCHAR(30) DEFAULT 'discovered',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, source, source_id)
);

CREATE INDEX idx_events_user_status ON events(user_id, status);
CREATE INDEX idx_events_datetime ON events(datetime_start);

-- =======================================
-- EVENT RESULTS (debrief)
-- =======================================
CREATE TABLE event_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events(event_id),
    user_id BIGINT REFERENCES users(user_id),
    contacts_made JSONB DEFAULT '[]',      -- [{name, company, role, contact_info, value_score}]
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 10),
    actual_cost DOUBLE PRECISION DEFAULT 0,
    notes TEXT,
    roi_score DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =======================================
-- METHODOLOGIES (600+ records)
-- =======================================
CREATE TABLE methodologies (
    methodology_id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    full_text TEXT,
    category VARCHAR(255),
    event_types JSONB DEFAULT '["any"]',   -- ["meetup", "conference", ...]
    difficulty VARCHAR(20),                -- beginner, intermediate, advanced
    skills JSONB DEFAULT '[]',
    embedding vector(1536)
);

CREATE INDEX ON methodologies USING ivfflat (embedding vector_cosine_ops);

-- =======================================
-- CHALLENGES
-- =======================================
CREATE TABLE challenges (
    challenge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events(event_id),
    user_id BIGINT REFERENCES users(user_id),
    methodology_id INTEGER REFERENCES methodologies(methodology_id),
    methodology_name VARCHAR(500),
    description TEXT NOT NULL,
    success_metrics JSONB DEFAULT '[]',
    tips JSONB DEFAULT '[]',
    difficulty VARCHAR(20),                -- beginner, intermediate, advanced
    status VARCHAR(30) DEFAULT 'assigned', -- assigned, completed, partially_completed, failed, skipped
    user_feedback TEXT,
    coach_feedback TEXT,
    progress_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_challenges_user_status ON challenges(user_id, status);

-- =======================================
-- LEARNED PREFERENCES
-- =======================================
CREATE TABLE learned_preferences (
    preference_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    preference_type VARCHAR(50),           -- "time", "price", "type", "topic", "language"
    preference_value TEXT,
    confidence DOUBLE PRECISION DEFAULT 0.3,
    evidence_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_preferences_user ON learned_preferences(user_id);

-- =======================================
-- MEMORY EMBEDDINGS (semantic search)
-- =======================================
CREATE TABLE memory_embeddings (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    content TEXT,
    embedding vector(1536),
    memory_type VARCHAR(50),               -- 'conversation', 'preference', 'insight'
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON memory_embeddings USING ivfflat (embedding vector_cosine_ops);

-- =======================================
-- METHODOLOGY QUERY CACHE
-- =======================================
CREATE TABLE methodology_query_cache (
    query_hash VARCHAR(32) PRIMARY KEY,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- =======================================
-- CREW RUNS (monitoring)
-- =======================================
CREATE TABLE crew_runs (
    run_id SERIAL PRIMARY KEY,
    crew_name VARCHAR(50) NOT NULL,
    user_id BIGINT REFERENCES users(user_id),
    duration_sec DOUBLE PRECISION,
    status VARCHAR(20),                    -- "success" | "error"
    output TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_crew_runs_user ON crew_runs(user_id, created_at);
