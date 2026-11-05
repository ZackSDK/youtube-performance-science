import hashlib
import json
from googleapiclient.discovery import build
from sqlalchemy import create_engine, text
from src.config import DATABASE_URL, YOUTUBE_API_KEY


def get_stratum(subscribers: int) -> str:
    if subscribers < 50_000:
        return "<50k"
    elif subscribers <= 500_000:
        return "50k-500k"
    else:
        return ">500k"


def enrich():
    engine = create_engine(DATABASE_URL)
    yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # 1. Nettoyage des chaînes fantômes / inactives (0 ou <= 2 vidéos)
    with engine.connect() as conn:
        deleted = conn.execute(
            text("""
                DELETE FROM chaines 
                WHERE id IN (
                    SELECT chaine_id FROM chaines_stats WHERE video_count <= 2
                )
                RETURNING id;
            """)
        ).fetchall()
        conn.commit()
        print(f"--> {len(deleted)} chaînes inactives (<= 2 vidéos) supprimées de la base.")

    # 2. Liste de chaînes vérifiées par handles ou IDs canoniques
    targets = [
        # IDs canoniques vérifiés
        {"type": "id", "val": "UCP46_MXP_WG_auH88FnfS1A"},  # Nota Bene (2.3M)
        {"type": "id", "val": "UCI7DUjUYcPOLZ0pRuk4klkw"},  # Marie Wild (109k)
        {"type": "id", "val": "UCOchT7ZJ4TXe3stdLW1Sfxw"},  # Dans Ton Corps (738k)
        {"type": "id", "val": "UCyJDHgrsUKuWLe05GvC2lng"},  # Stupid Economics (331k)
        {"type": "id", "val": "UCAiy7bY8nTQCWrkSRh6Wu9w"},  # Un Créatif (376k)
        {"type": "id", "val": "UCzabZYC0MYRR2MFkq62d6yQ"},  # Florent Garcia (278k)
        {"type": "id", "val": "UC-jcC3zw4pXOn8t3keKY__g"},  # Léa Bello (19.6k)
        {"type": "id", "val": "UCofQxJWd4qkqc7ZgaLkZfcw"},  # Linguisticae (459k)
        {"type": "id", "val": "UC2_OG1L8DLTzQ7UrZVOk7OA"},  # Axolot (659k)
        {"type": "id", "val": "UCAxljKT0ujiJZhGC8Ood7mw"},  # Zeste de science CNRS (46.7k)
        {"type": "id", "val": "UCMFcMhePnH4onVHt2-ItPZw"},  # Hygiène Mentale (402k)
        {"type": "id", "val": "UC0JUkXAVVA4qWH1BQRs5N3A"},  # Pause Process (106k)
        {"type": "id", "val": "UCKjDY4joMPcoRMmd-G1yz1Q"},  # C'est une autre histoire (725k)
        {"type": "id", "val": "UCO-YDXoZJNVJFmF1UJ17rEw"},  # La Brigade du Livre (35.8k)
        {"type": "id", "val": "UCvtMQXNgBROo1Sh2D3Qiulw"},  # L'Extracteur (24k)
        {"type": "id", "val": "UCY2w3Jdy5e65LZUepePht0g"},  # La mal biaisée (10.8k)
        {"type": "id", "val": "UCJ9kIKgFuAB23GkEko1hHDg"},  # Mycéliums (20.2k)
        {"type": "id", "val": "UC3tHYDnlFlcAY8fsGXGWFFg"},  # Le Biome Park (135k)
        {"type": "id", "val": "UCA434ZzIaqr510_7U8f2Z1Q"},  # Alt 236 (video essay / pop culture / art)
        
        # Handles vérifiés
        {"type": "handle", "val": "Fouloscopie"},
        {"type": "handle", "val": "poissonfecond42"},
        {"type": "handle", "val": "EvoSapiensFR"},
        {"type": "handle", "val": "ScienceClic"},
        {"type": "handle", "val": "questionsdhistoire"},
        {"type": "handle", "val": "StardustYT"},
        {"type": "handle", "val": "PrimumNonNocereVideo"},
        {"type": "handle", "val": "scienceinfuse"},
        {"type": "handle", "val": "LaStatSauvage"},
        {"type": "handle", "val": "Science4Allfr"},
        {"type": "handle", "val": "science_ethique"},
        {"type": "handle", "val": "curieux-fr"},
        {"type": "handle", "val": "professeur_feuillage"},
        {"type": "handle", "val": "charliedanger"},
        {"type": "handle", "val": "lepointscience"},
    ]

    added = 0
    with engine.connect() as conn:
        for t in targets:
            try:
                if t["type"] == "id":
                    req = yt.channels().list(
                        part="snippet,statistics,contentDetails",
                        id=t["val"]
                    )
                else:
                    req = yt.channels().list(
                        part="snippet,statistics,contentDetails",
                        forHandle=t["val"]
                    )
                res = req.execute()
                items = res.get("items", [])
                if not items:
                    print(f"[SKIP] Non trouvé : {t['val']}")
                    continue

                item = items[0]
                channel_id = item["id"]
                snippet = item["snippet"]
                stats = item["statistics"]
                content_details = item["contentDetails"]

                # Ignorer les chaînes avec <= 2 vidéos ou sans abonnés publics
                vids = int(stats.get("videoCount", 0))
                if vids <= 2 or stats.get("hiddenSubscriberCount", False) or "subscriberCount" not in stats:
                    print(f"[SKIP] {snippet['title']} a trop peu de vidéos ({vids})")
                    continue

                subs = int(stats["subscriberCount"])
                stratum = get_stratum(subs)
                uploads_id = content_details.get("relatedPlaylists", {}).get("uploads")

                # Ingestion idempotente
                conn.execute(
                    text("""
                        INSERT INTO chaines (
                            id, titre, custom_url, description, 
                            date_creation, uploads_playlist_id, stratum
                        )
                        VALUES (
                            :id, :titre, :custom_url, :description, 
                            :date_creation, :uploads_playlist_id, :stratum
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            titre = EXCLUDED.titre,
                            custom_url = EXCLUDED.custom_url,
                            description = EXCLUDED.description,
                            uploads_playlist_id = EXCLUDED.uploads_playlist_id,
                            stratum = EXCLUDED.stratum;
                    """),
                    {
                        "id": channel_id,
                        "titre": snippet["title"],
                        "custom_url": snippet.get("customUrl", ""),
                        "description": snippet.get("description", ""),
                        "date_creation": snippet["publishedAt"],
                        "uploads_playlist_id": uploads_id,
                        "stratum": stratum
                    }
                )

                conn.execute(
                    text("""
                        INSERT INTO chaines_stats (chaine_id, abonnes, vues_totales, video_count)
                        VALUES (:chaine_id, :abonnes, :vues_totales, :video_count);
                    """),
                    {
                        "chaine_id": channel_id,
                        "abonnes": subs,
                        "vues_totales": int(stats.get("viewCount", 0)),
                        "video_count": vids
                    }
                )

                conn.commit()
                added += 1
                print(f"[AJOUTÉ] {snippet['title'][:25]:<25} | {stratum:<8} | {subs:>9,} subs | {vids:>4} vids")

            except Exception as e:
                conn.rollback()
                print(f"[ERREUR] {t['val']} : {e}")

    print(f"\n--> Terminé : {added} chaînes ajoutées / mises à jour.")


if __name__ == "__main__":
    enrich()
