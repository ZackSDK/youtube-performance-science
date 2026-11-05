from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.config import DATABASE_URL, YOUTUBE_API_KEY


def test_youtube():
    print("--> Test de connexion YouTube Data API v3...")
    try:
        # Construction du client RPC YouTube
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        
        # Requête légère : 1 seule chaîne, 1 unité de quota consommée
        request = youtube.channels().list(
            part="snippet",
            id="UCaNlbnghtwlsGF-KzAFThqA"  # Chaîne ScienceÉtonnante
        )
        response = request.execute()
        
        items = response.get("items", [])
        if not items:
            print("[FAIL] Réponse vide de YouTube. Clé valide mais ressource non trouvée.")
            return False
            
        channel_title = items[0]["snippet"]["title"]
        print(f"[OK] YouTube connecté avec succès ! Chaîne testée : '{channel_title}'")
        return True

    except HttpError as e:
        print(f"[FAIL] Erreur API YouTube (HTTP {e.resp.status}) : {e.content}")
        return False
    except Exception as e:
        print(f"[FAIL] Erreur inattendue sur YouTube : {e}")
        return False


def test_database():
    print("\n--> Test de connexion Neon PostgreSQL...")
    try:
        # Création du pool de connexion
        engine = create_engine(DATABASE_URL)
        
        # Le bloc 'with' garantit que la connexion est relâchée au pool même en cas d'erreur
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.scalar()
            
        print("[OK] PostgreSQL connecté avec succès !")
        print(f"     Version : {version}")
        return True

    except SQLAlchemyError as e:
        print(f"[FAIL] Erreur de connexion PostgreSQL : {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Erreur inattendue sur la base de données : {e}")
        return False


if __name__ == "__main__":
    yt_ok = test_youtube()
    db_ok = test_database()
    
    if yt_ok and db_ok:
        print("\n=== TOUTES LES CONNEXIONS SONT VALIDES (Phase 1 validée) ===")
    else:
        print("\n=== ÉCHEC DU TEST : Corrige les erreurs ci-dessus ===")