# ==============================================================================
# SCRIPT : resolve_channels.py
# BUT    : Récupérer les métadonnées officielles des chaînes YouTube cibles,
#          déterminer leur strate d'abonnés et les insérer dans PostgreSQL.
# ==============================================================================

# --- IMPORTS DE LA BIBLIOTHÈQUE STANDARD PYTHON ---
import csv       # Pour lire facilement notre fichier seed_channels.csv ligne par ligne
import hashlib   # Pour créer une empreinte numérique (hash SHA-256) unique par requête
import json      # Pour sérialiser (convertir) les dictionnaires Python en texte JSON
from datetime import datetime

# --- IMPORTS DES BIBLIOTHÈQUES TIERCES ---
# googleapiclient : SDK officiel Google pour interagir avec l'API YouTube Data v3
from googleapiclient.discovery import build

# sqlalchemy : Bibliothèque standard en Python pour communiquer avec PostgreSQL
# create_engine : Gère le pool de connexions vers Neon
# text : Permet d'écrire des requêtes SQL brutes sécurisées avec injection de paramètres (:param)
from sqlalchemy import create_engine, text

# Import de nos identifiants sécurisés validés en Phase 1
from src.config import DATABASE_URL, YOUTUBE_API_KEY


def get_stratum(subscribers: int) -> str:
    """
    RÈGLE MÉTHODOLOGIQUE : Stratification par taille de chaîne.
    Permet de classifier objectivement la chaîne en fonction de son audience réelle.
    
    Arguments:
        subscribers (int): Le nombre officiel d'abonnés renvoyé par l'API YouTube.
    
    Retourne:
        str: Le libellé exact de la strate ('<50k', '50k-500k', ou '>500k').
    """
    if subscribers < 50_000:
        return "<50k"        # Micro-créateurs / niches spécialisées
    elif subscribers <= 500_000:
        return "50k-500k"    # Créateurs établis
    else:
        return ">500k"       # Poids lourds du secteur scientifique


def resolve_and_ingest():
    """
    Fonction principale du pipeline de résolution :
    1. Lit les handles cibles dans data/seed_channels.csv.
    2. Interroge l'API YouTube Data v3 (endpoint channels.list).
    3. Sauvegarde la réponse brute dans la table raw_api (Data Lake / Audit log).
    4. Extrait les champs métier et injecte dans 'chaines' et 'chaines_stats'.
    """
    
    # 1. Initialisation des clients de connexion
    # --------------------------------------------------------------------------
    engine = create_engine(DATABASE_URL)
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # 2. Lecture du fichier source de départ (Seed List)
    # --------------------------------------------------------------------------
    handles_to_process = []
    with open("data/seed_channels.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            handle = row["handle"].strip()
            if handle:
                handles_to_process.append(handle)

    print(f"--> {len(handles_to_process)} chaînes à interroger depuis seed_channels.csv...\n")

    resolved_count = 0

    # 3. Traitement des chaînes avec gestion de transaction SQL
    # --------------------------------------------------------------------------
    with engine.connect() as conn:
        for handle in handles_to_process:
            try:
                clean_handle = handle.lstrip("@")
                
                # --- APPEL API YOUTUBE (Coût : 1 unité par chaîne) ---
                request = youtube.channels().list(
                    part="snippet,statistics,contentDetails",
                    forHandle=clean_handle
                )
                response = request.execute()
                items = response.get("items", [])

                if not items:
                    print(f"[SKIP] Chaîne introuvable sur YouTube pour le handle : {handle}")
                    continue

                item = items[0]
                channel_id = item["id"]
                snippet = item["snippet"]
                stats = item["statistics"]
                content_details = item["contentDetails"]

                # --- ÉTAPE A : SAUVEGARDE DANS LE DATA LAKE (raw_api) ---
                params_hash = hashlib.sha256(handle.encode("utf-8")).hexdigest()
                conn.execute(
                    text("""
                        INSERT INTO raw_api (endpoint, params_hash, payload)
                        VALUES (:endpoint, :params_hash, :payload)
                    """),
                    {
                        "endpoint": "channels",
                        "params_hash": params_hash,
                        "payload": json.dumps(item)
                    }
                )

                # --- ÉTAPE B : EXTRACTION ET CONTRÔLE QUALITÉ DES DONNÉES ---
                titre = snippet["title"]
                custom_url = snippet.get("customUrl", handle)
                description = snippet.get("description", "")
                date_creation = snippet["publishedAt"]
                uploads_playlist_id = content_details.get("relatedPlaylists", {}).get("uploads")
                
                hidden_subs = stats.get("hiddenSubscriberCount", False)
                if hidden_subs or "subscriberCount" not in stats:
                    print(f"[SKIP] {titre} masque son nombre d'abonnés.")
                    continue

                abonnes = int(stats["subscriberCount"])
                vues_totales = int(stats.get("viewCount", 0))
                video_count = int(stats.get("videoCount", 0))
                stratum = get_stratum(abonnes)

                # --- ÉTAPE C : INSERTION IDEMPOTENTE DANS LA TABLE 'chaines' ---
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
                        "titre": titre,
                        "custom_url": custom_url,
                        "description": description,
                        "date_creation": date_creation,
                        "uploads_playlist_id": uploads_playlist_id,
                        "stratum": stratum
                    }
                )

                # --- ÉTAPE D : HISTORISATION DANS LA TABLE 'chaines_stats' ---
                conn.execute(
                    text("""
                        INSERT INTO chaines_stats (chaine_id, abonnes, vues_totales, video_count)
                        VALUES (:chaine_id, :abonnes, :vues_totales, :video_count);
                    """),
                    {
                        "chaine_id": channel_id,
                        "abonnes": abonnes,
                        "vues_totales": vues_totales,
                        "video_count": video_count
                    }
                )

                conn.commit()
                resolved_count += 1
                print(f"[OK] {titre[:25]:<25} | {stratum:<8} | {abonnes:>9,} abonnés | uploads: {uploads_playlist_id}")

            except Exception as e:
                print(f"[ERREUR] Échec sur {handle} : {e}")
                conn.rollback()

    print(f"\n--> Terminé : {resolved_count}/{len(handles_to_process)} chaînes résolues et ingérées.")


if __name__ == "__main__":
    resolve_and_ingest()
