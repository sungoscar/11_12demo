
-- 使用者資料表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(10) NOT NULL
        CHECK (role IN ('author', 'editor')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 投稿文章資料表
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES users(id),
    category VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'editing'
        CHECK (status IN ('editing', 'reviewing', 'approved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 加快作者稿件與待審清單查詢
CREATE INDEX IF NOT EXISTS idx_articles_author
ON articles(author_id);

CREATE INDEX IF NOT EXISTS idx_articles_status
ON articles(status);

