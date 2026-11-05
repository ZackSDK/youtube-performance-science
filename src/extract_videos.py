# ==============================================================================
# SCRIPT : extract_videos.py
# BUT    : Extraire toutes les vidéos publiées entre 2024 et 2025 pour les
#          64 chaînes cibles et les ingérer dans PostgreSQL (raw_api, videos, statistiques).
# ==============================================================================

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from functools import wraps

from dateutil import parser as date_parser
from googleapiclient.discovery import build
from sqlalchemy import create_engine, text

from src.config import DATABASE_URL, YOUTUBE_API_KEY

# Fenêtre temporelle d'étude (cohortes 2024-2025)
START_DATE = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DATE = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


def retry_with_backoff(max_retries=3, base_delay=2):
    """Décorateur de résilience avec backoff exponentiel pour les appels API Google."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"      [RETRY] Erreur API ({e}). Pause de {delay}s avant nouvel essai...")
                    time.sleep(delay)
                    delay *= 2
        return wrapper
    return decorator


def parse_iso8601_duration(duration_str: str) -> int:
    """Convertit une durée ISO 8601 (ex: 'PT15M33S') en secondes totales."""
    pattern = re.compile(
        r'P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?'
    )
    match = pattern.match(duration_str)
    if not match:
        return 0
    parts = match.groupdict()
    days = int(parts['days'] or 0)
    hours = int(parts['hours'] or 0)
    minutes = int(parts['minutes'] or 0)
    seconds = int(parts['seconds'] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


@retry_with_backoff(max_retries=3, base_delay=2)
def get_playlist_items(youtube, playlist_id, page_token=None):
    """Appel API pour lister les éléments d'une playlist (coût: 1 unité pour 50 vidéos)."""
    return youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=playlist_id,
        maxResults=50,
        pageToken=page_token
    ).execute()


@retry_with_backoff(max_retries=3, base_delay=2)
def get_videos_details(youtube, video_ids_chunk):
    """Appel API groupé pour obtenir les métadonnées et statistiques (coût: 1 unité pour 50 vidéos)."""
    return youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=",".join(video_ids_chunk)
    ).execute()


def extract_channel_videos(youtube, conn, channel_id, channel_title, playlist_id):
    """Parcourt la playlist d'une chaîne, filtre sur 2024-2025 et ingère les vidéos."""
    next_page_token = None
    target_video_ids = []
    stop_pagination = False

    # 1. Énumération chronologique inverse des vidéos via la playlist d'uploads
    while not stop_pagination:
        res = get_playlist_items(youtube, playlist_id, next_page_token)
        items = res.get("items", [])
        if not items:
            break

        for item in items:
            pub_date_raw = item["contentDetails"].get("videoPublishedAt") or item["snippet"].get("publishedAt")
            if not pub_date_raw:
                continue
            
            pub_date = date_parser.parse(pub_date_raw)

            # Arrêt anticipé : si la vidéo est antérieure à 2024, stop !
            if pub_date < START_DATE:
                stop_pagination = True
                break

            # Si la vidéo est dans la fenêtre 2024-2025, on conserve son ID
            if pub_date <= END_DATE:
                video_id = item["contentDetails"]["videoId"]
                target_video_ids.append(video_id)

        next_page_token = res.get("nextPageToken")
        if not next_page_token or stop_pagination:
            break

    if not target_video_ids:
        print(f"--> {channel_title[:25]:<25} | 0 vidéo publiée entre 2024 et 2025.")
        return 0

    # 2. Enrichissement par lots de 50 vidéos
    ingested_count = 0
    chunk_size = 50

    for i in range(0, len(target_video_ids), chunk_size):
        chunk = target_video_ids[i:i + chunk_size]
        details_res = get_videos_details(youtube, chunk)
        video_items = details_res.get("items", [])

        for v in video_items:
            v_id = v["id"]
            snippet = v["snippet"]
            content = v["contentDetails"]
            stats = v["statistics"]

            # Audit Data Lake : sauvegarde du JSON brut dans raw_api
            params_hash = hashlib.sha256(v_id.encode("utf-8")).hexdigest()
            conn.execute(
                text("""
                    INSERT INTO raw_api (endpoint, params_hash, payload)
                    VALUES (:endpoint, :params_hash, :payload)
                """),
                {
                    "endpoint": "videos",
                    "params_hash": params_hash,
                    "payload": json.dumps(v)
                }
            )

            # Parsing des métadonnées
            titre = snippet["title"]
            description = snippet.get("description", "")
            date_pub = snippet["publishedAt"]
            duree_sec = parse_iso8601_duration(content.get("duration", ""))
            tags = snippet.get("tags", [])

            # Compteurs statistiques
            vues = int(stats.get("viewCount", 0))
            likes = int(stats["likeCount"]) if "likeCount" in stats else None
            commentaires = int(stats["commentCount"]) if "commentCount" in stats else None

            # Ingestion idempotente dans 'videos'
            conn.execute(
                text("""
                    INSERT INTO videos (
                        id, chaine_id, titre, description, 
                        date_publication, duree_secondes, tags
                    )
                    VALUES (
                        :id, :chaine_id, :titre, :description, 
                        :date_publication, :duree_secondes, :tags
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        titre = EXCLUDED.titre,
                        description = EXCLUDED.description,
                        duree_secondes = EXCLUDED.duree_secondes,
                        tags = EXCLUDED.tags;
                """),
                {
                    "id": v_id,
                    "chaine_id": channel_id,
                    "titre": titre,
                    "description": description,
                    "date_publication": date_pub,
                    "duree_secondes": duree_sec,
                    "tags": tags
                }
            )

            # Snapshot temporel dans 'statistiques'
            conn.execute(
                text("""
                    INSERT INTO statistiques (video_id, vues, likes, commentaires)
                    VALUES (:video_id, :vues, :likes, :commentaires);
                """),
                {
                    "video_id": v_id,
                    "vues": vues,
                    "likes": likes,
                    "commentaires": commentaires
                }
            )
            ingested_count += 1

        conn.commit()

    print(f"[OK] {channel_title[:25]:<25} | {ingested_count:>3} vidéos (2024-2025) ingérées.")
    return ingested_count


def run_pipeline():
    engine = create_engine(DATABASE_URL)
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    print("--> Démarrage de l'extraction des vidéos (2024-2025)...\n")

    with engine.connect() as conn:
        channels = conn.execute(
            text("SELECT id, titre, uploads_playlist_id FROM chaines ORDER BY titre;")
        ).fetchall()

        print(f"--> {len(channels)} chaînes à traiter.\n")
        total_videos = 0

        for idx, (c_id, c_title, uploads_id) in enumerate(channels, 1):
            if not uploads_id:
                continue
            try:
                count = extract_channel_videos(youtube, conn, c_id, c_title, uploads_id)
                total_videos += count
            except Exception as e:
                print(f"[ERREUR] Échec sur la chaîne {c_title} : {e}")
                conn.rollback()

    print(f"\n=======================================================")
    print(f"Extraction terminée avec succès ! Total : {total_videos} vidéos.")
    print(f"=======================================================")


if __name__ == "__main__":
    run_pipeline()
