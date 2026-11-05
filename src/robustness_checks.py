# ==============================================================================
# SCRIPT : robustness_checks.py
# BUT    : Tests de robustesse économétrique
#          1. Impact de la fuite des Shorts sur les coefficients
#          2. Hétérogénéité des effets selon la strate d'abonnés
# ==============================================================================

import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
from sqlalchemy import create_engine

from src.config import DATABASE_URL


def load_full_dataset() -> pd.DataFrame:
    """Charge la totalité des 3 346 vidéos (y compris les Shorts) depuis PostgreSQL."""
    engine = create_engine(DATABASE_URL)
    sql = """
    SELECT 
        v.id AS video_id,
        v.chaine_id,
        c.stratum,
        v.titre,
        v.duree_secondes,
        ROUND((v.duree_secondes / 60.0)::numeric, 2) AS duree_minutes,
        (v.titre ~ '[0-9]')::int AS has_number,
        (
            v.titre ~ '\?' 
            OR v.titre ~* '^(pourquoi|comment|faut-il|peut-on|quel|quelle|quels|quelles|qui|est-ce|combien)\y'
        )::int AS has_question,
        (
            v.titre ~* '\y(erreur|erreurs|danger|dangers|mort|morts|pire|pires|jamais|faux|fausse|fausses|mensonge|mensonges|menace|menaces|crise|catastrophe|risque|risques|piège|pièges|drame|interdit|interdits)\y'
        )::int AS has_negative_word,
        (
            EXTRACT(ISODOW FROM (v.date_publication AT TIME ZONE 'Europe/Paris')) IN (3, 7)
            AND EXTRACT(HOUR FROM (v.date_publication AT TIME ZONE 'Europe/Paris')) BETWEEN 17 AND 20
        )::int AS is_prime_time,
        LENGTH(v.titre) AS title_char_count,
        EXTRACT(DAY FROM ('2026-10-21'::timestamptz - v.date_publication))::int AS age_jours,
        ROUND(LN(s.vues + 1)::numeric, 4) AS log_vues,
        CASE WHEN v.duree_secondes <= 60 THEN 1 ELSE 0 END AS is_short
    FROM videos v
    JOIN statistiques s ON v.id = s.video_id
    JOIN chaines c ON v.chaine_id = c.id;
    """
    df = pd.read_sql(sql, engine)
    return df


def test_shorts_leakage(df: pd.DataFrame):
    """
    Test 1 : Que se passe-t-il si un analyste mélange les Shorts et les vidéos longues ?
    Compare le modèle propre (>60s) au modèle pollué (toutes vidéos).
    """
    print("\n" + "=" * 80)
    print(" TEST DE ROBUSTESSE 1 : IMPACT DE LA POLLUTION PAR LES SHORTS")
    print("=" * 80)

    formula = (
        "log_vues ~ duree_minutes + has_number + has_question + "
        "has_negative_word + is_prime_time + title_char_count + "
        "age_jours + C(chaine_id)"
    )

    # Échantillon propre (Long-form > 60s)
    df_clean = df[df["is_short"] == 0]
    res_clean = smf.ols(formula, data=df_clean).fit(cov_type='cluster', cov_kwds={'groups': df_clean['chaine_id']})

    # Échantillon pollué (Tous formats)
    res_polluted = smf.ols(formula, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['chaine_id']})

    variables = ["duree_minutes", "has_number", "has_negative_word", "title_char_count"]
    comparison = []

    for var in variables:
        b_clean = res_clean.params[var]
        p_clean = res_clean.pvalues[var]
        b_poll = res_polluted.params[var]
        p_poll = res_polluted.pvalues[var]

        comparison.append({
            "Variable": var,
            "Beta Propre (>60s)": f"{b_clean:+.4f} (p={p_clean:.3f})",
            "Beta Pollué (Tous)": f"{b_poll:+.4f} (p={p_poll:.3f})",
            "Évolution de l'effet": f"{((np.exp(b_poll) - 1) - (np.exp(b_clean) - 1)) * 100:+.1f} pts"
        })

    comp_df = pd.DataFrame(comparison)
    print(comp_df.to_string(index=False))
    print(f"\nObservations Propres  : {len(df_clean)} vidéos")
    print(f"Observations Polluées : {len(df)} vidéos (+{len(df) - len(df_clean)} Shorts réinjectés)")


def test_stratum_heterogeneity(df: pd.DataFrame):
    """
    Test 2 : Est-ce que les déterminants fonctionnent de la même manière
    selon la taille de la chaîne (<500k vs >500k) ?
    """
    print("\n" + "=" * 80)
    print(" TEST DE ROBUSTESSE 2 : HÉTÉROGÉNÉITÉ PAR TAILLE DE CHAÎNE")
    print("=" * 80)

    df_clean = df[df["is_short"] == 0]
    formula = (
        "log_vues ~ has_number + has_negative_word + duree_minutes + "
        "age_jours + C(chaine_id)"
    )

    df_mid = df_clean[df_clean["stratum"].isin(["<50k", "50k-500k"])]
    df_big = df_clean[df_clean["stratum"] == ">500k"]

    res_mid = smf.ols(formula, data=df_mid).fit(cov_type='cluster', cov_kwds={'groups': df_mid['chaine_id']})
    res_big = smf.ols(formula, data=df_big).fit(cov_type='cluster', cov_kwds={'groups': df_big['chaine_id']})

    variables = ["has_number", "has_negative_word"]
    subgroup_res = []

    for var in variables:
        b_mid = res_mid.params[var]
        p_mid = res_mid.pvalues[var]
        eff_mid = (np.exp(b_mid) - 1) * 100

        b_big = res_big.params[var]
        p_big = res_big.pvalues[var]
        eff_big = (np.exp(b_big) - 1) * 100

        subgroup_res.append({
            "Caractéristique": var,
            "Chaînes <500k (N=" + str(len(df_mid)) + ")": f"{eff_mid:+.1f} % (p={p_mid:.3f})",
            "Chaînes >500k (N=" + str(len(df_big)) + ")": f"{eff_big:+.1f} % (p={p_big:.3f})"
        })

    sub_df = pd.DataFrame(subgroup_res)
    print(sub_df.to_string(index=False))


if __name__ == "__main__":
    full_df = load_full_dataset()
    test_shorts_leakage(full_df)
    test_stratum_heterogeneity(full_df)
