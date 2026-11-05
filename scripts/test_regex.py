from sqlalchemy import create_engine, text
from src.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    c_b = conn.execute(text("SELECT count(*) FROM videos WHERE titre ~* '\\b(erreur|danger|mort|pire|faux)\\b';")).scalar()
    c_y = conn.execute(text("SELECT count(*) FROM videos WHERE titre ~* '\\y(erreur|erreurs|danger|dangers|mort|morts|pire|pires|jamais|faux|fausse|mensonge|mensonges|menace|menaces|crise|catastrophe|risque|risques|piège|pièges|drame|interdit)\\y';")).scalar()
    print("Avec \\b (backspace) :", c_b)
    print("Avec \\y (PostgreSQL word boundary) :", c_y)
