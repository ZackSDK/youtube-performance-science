CREATE TABLE IF NOT EXISTS raw_api(
    id SERIAL PRIMARY KEY,
    endpoint VARCHAR(50) NOT NULL,
    params_hash VARCHAR(64),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS chaines(
    id VARCHAR(32) PRIMARY KEY,
    titre VARCHAR(255) NOT NULL,
    custom_url VARCHAR(100),
    description TEXT,
    date_creation TIMESTAMPTZ NOT NULL,
    uploads_playlist_id VARCHAR(34),
    stratum VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS chaines_stats(
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chaine_id VARCHAR(32) REFERENCES chaines(id) ON DELETE CASCADE,
    abonnes BIGINT,
    vues_totales BIGINT,
    video_count INTEGER,
    date_releve TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS videos(
    id VARCHAR(16) PRIMARY KEY,
    chaine_id VARCHAR(32) REFERENCES chaines(id) ON DELETE CASCADE,
    titre TEXT NOT NULL,
    description TEXT,
    date_publication TIMESTAMPTZ NOT NULL,
    duree_secondes INTEGER NOT NULL,
    tags TEXT [],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS statistiques(
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(16) REFERENCES videos(id) ON DELETE CASCADE,
    vues BIGINT NOT NULL,
    likes BIGINT,
    commentaires BIGINT,
    date_releve TIMESTAMPTZ DEFAULT NOW()
);
-- Index pour améliorer les recherches par chaîne
CREATE INDEX IF NOT EXISTS idx_videos_chaine_id ON videos(chaine_id);
CREATE INDEX IF NOT EXISTS idx_videos_date_pub ON videos(date_publication);
-- Index pour les statistiques
CREATE INDEX IF NOT EXISTS idx_stats_video_id ON statistiques(video_id);
CREATE INDEX IF NOT EXISTS idx_chaines_stats_chaine_id ON chaines_stats(chaine_id);