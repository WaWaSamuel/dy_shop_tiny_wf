-- 初始化数据库
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 创建只读用户（用于读写分离扩展）
-- CREATE USER studio_reader WITH PASSWORD 'studio_reader_2024';
-- GRANT CONNECT ON DATABASE studio_main TO studio_reader;
-- GRANT USAGE ON SCHEMA public TO studio_reader;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO studio_reader;
