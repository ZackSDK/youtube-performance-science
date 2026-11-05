-- ==============================================================================
-- VUE SQL : features
-- BUT     : Feature engineering statistique pour l'analyse des déterminants
--           de la performance des vidéos (cohortes 2024-2025).
-- ==============================================================================

DROP VIEW IF EXISTS features;

CREATE OR REPLACE VIEW features AS
WITH chaines_medians AS (
    -- Calcul de la médiane des vues par chaîne sur les vidéos longues (>60s)
    SELECT 
        v.chaine_id,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY s.vues) AS median_vues_chaine,
        COUNT(*) AS nb_videos_chaine
    FROM videos v
    JOIN statistiques s ON v.id = s.video_id
    WHERE v.duree_secondes > 60
    GROUP BY v.chaine_id
)
SELECT 
    -- 1. IDENTIFIANTS & MÉTADONNÉES DE BASE
    v.id AS video_id,
    v.chaine_id,
    c.titre AS chaine_nom,
    c.stratum,
    v.titre,
    v.date_publication,
    
    -- 2. MÉTRIQUES BRUTES & VARIABLES CIBLES (TARGET VARIABLES)
    s.vues,
    s.likes,
    s.commentaires,
    cm.median_vues_chaine,
    
    -- Performance relative : Vues / Médiane de la chaîne (Target H1-H6)
    ROUND((s.vues::NUMERIC / NULLIF(cm.median_vues_chaine, 0))::NUMERIC, 4) AS perf_relative,
    
    -- Logarithme népérien des vues (pour régression OLS avec effets fixes chaîne)
    ROUND(LN(s.vues + 1)::NUMERIC, 4) AS log_vues,

    -- 3. VARIABLES EXPLICATIVES HYPOTHÈSES (H1 À H6)
    
    -- H1 : Durée en minutes
    ROUND((v.duree_secondes / 60.0)::NUMERIC, 2) AS duree_minutes,
    
    -- H2 : Présence d'un chiffre dans le titre (0 ou 1)
    (v.titre ~ '[0-9]')::INT AS has_number,
    
    -- H3 : Question dans le titre (Point d'interrogation ou mot interrogatif en début de titre)
    (
        v.titre ~ '\?' 
        OR v.titre ~* '^(pourquoi|comment|faut-il|peut-on|quel|quelle|quels|quelles|qui|est-ce|combien)\y'
    )::INT AS has_question,
    
    -- H4 : Biais de négativité (Lexique de risque, danger, mensonge ou catastrophe)
    -- Attention : En POSIX PostgreSQL, la limite de mot est \y (et non \b qui est le caractère backspace)
    (
        v.titre ~* '\y(erreur|erreurs|danger|dangers|mort|morts|pire|pires|jamais|faux|fausse|fausses|mensonge|mensonges|menace|menaces|crise|catastrophe|risque|risques|piège|pièges|drame|interdit|interdits)\y'
    )::INT AS has_negative_word,
    
    -- H5 : Timing de publication dans le fuseau de l'audience (Europe/Paris)
    EXTRACT(ISODOW FROM (v.date_publication AT TIME ZONE 'Europe/Paris'))::INT AS jour_semaine, -- 1=Lundi, 7=Dimanche
    EXTRACT(HOUR FROM (v.date_publication AT TIME ZONE 'Europe/Paris'))::INT AS heure_publication,
    (
        EXTRACT(ISODOW FROM (v.date_publication AT TIME ZONE 'Europe/Paris')) IN (3, 7) -- Mercredi ou Dimanche
        AND EXTRACT(HOUR FROM (v.date_publication AT TIME ZONE 'Europe/Paris')) BETWEEN 17 AND 20 -- Entre 17h00 et 20h59
    )::INT AS is_prime_time,
    
    -- H6 : Longueur du titre (caractères et mots)
    LENGTH(v.titre) AS title_char_count,
    ARRAY_LENGTH(REGEXP_SPLIT_TO_ARRAY(TRIM(v.titre), '\s+'), 1) AS title_word_count,
    
    -- 4. VARIABLES DE CONTRÔLE
    -- Ratios d'engagement
    ROUND(((s.likes::NUMERIC / NULLIF(s.vues, 0)) * 100)::NUMERIC, 3) AS like_ratio_pct,
    -- Âge de la vidéo en jours (contrôle de maturité)
    EXTRACT(DAY FROM ('2026-10-21'::TIMESTAMPTZ - v.date_publication))::INT AS age_jours

FROM videos v
JOIN statistiques s ON v.id = s.video_id
JOIN chaines c ON v.chaine_id = c.id
JOIN chaines_medians cm ON v.chaine_id = cm.chaine_id

-- FILTRAGE MÉTHODOLOGIQUE STRICT :
-- 1. Uniquement les vidéos longues (> 60 secondes, exclusion formelle des Shorts)
-- 2. Chaînes ayant au moins 5 vidéos longues pour garantir la stabilité statistique de la médiane
WHERE v.duree_secondes > 60 
  AND cm.nb_videos_chaine >= 5;
