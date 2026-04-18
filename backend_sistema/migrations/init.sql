-- Migración inicial: Crear base de datos y tablas
-- Ejecutar: psql -U postgres -f init.sql

-- Crear base de datos (ejecutar manualmente si no existe)
-- CREATE DATABASE encuestas;

-- Conectar a la base de datos
-- \c encuestas;

CREATE TABLE IF NOT EXISTS surveys (
    id SERIAL PRIMARY KEY,
    url VARCHAR(2048) NOT NULL,
    titulo VARCHAR(500) DEFAULT '',
    descripcion TEXT DEFAULT '',
    plataforma VARCHAR(50) DEFAULT 'google_forms',
    estructura JSONB NOT NULL DEFAULT '{}',
    total_preguntas INTEGER DEFAULT 0,
    requiere_login BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analysis_configs (
    id SERIAL PRIMARY KEY,
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    nombre VARCHAR(200) DEFAULT 'default',
    perfiles JSONB DEFAULT '[]',
    reglas_dependencia JSONB DEFAULT '[]',
    tendencias_escalas JSONB DEFAULT '[]',
    ai_provider_used VARCHAR(50) DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS executions (
    id SERIAL PRIMARY KEY,
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    analysis_config_id INTEGER REFERENCES analysis_configs(id),
    status VARCHAR(20) DEFAULT 'idle',
    mensaje VARCHAR(500) DEFAULT 'Listo',
    total INTEGER DEFAULT 0,
    progreso INTEGER DEFAULT 0,
    exitosas INTEGER DEFAULT 0,
    fallidas INTEGER DEFAULT 0,
    tiempo_transcurrido VARCHAR(50) DEFAULT '0s',
    tiempo_por_encuesta VARCHAR(50) DEFAULT '0s',
    headless BOOLEAN DEFAULT FALSE,
    excel_path VARCHAR(1024),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS responses (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    exito BOOLEAN DEFAULT FALSE,
    tiempo FLOAT DEFAULT 0.0,
    perfil VARCHAR(200) DEFAULT '',
    tendencia VARCHAR(200) DEFAULT '',
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_provider_configs (
    id SERIAL PRIMARY KEY,
    provider_name VARCHAR(50) NOT NULL,
    api_key VARCHAR(500) DEFAULT '',
    model VARCHAR(100) DEFAULT '',
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4000,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_surveys_created ON surveys(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_survey ON analysis_configs(survey_id, is_active);
CREATE INDEX IF NOT EXISTS idx_executions_survey ON executions(survey_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
CREATE INDEX IF NOT EXISTS idx_responses_execution ON responses(execution_id);
