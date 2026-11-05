import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests
import statsmodels.formula.api as smf
from sqlalchemy import create_engine
import statsmodels.formula.api as smf

from src.config import DATABASE_URL


def load_dataset() -> pd.DataFrame:
    """Charge la vue SQL features directement depuis Neon dans Pandas."""
    engine = create_engine(DATABASE_URL)
    df = pd.read_sql("SELECT * FROM features;", engine)
    return df


def check_distributions(df: pd.DataFrame):
    """
    Étape 7.1 : Diagnostic de normalité et d'asymétrie.
    Justifie mathématiquement le rejet des tests paramétriques (t-test / Pearson).
    """
    print("=" * 80)
    print(" ÉTAPE 7.1 : DIAGNOSTIC DE DISTRIBUTION ET DE NORMALITÉ")
    print("=" * 80)
    
    variables_to_check = [
        ("Vues Brutes (vues)", df["vues"]),
        ("Performance Relative (perf_relative)", df["perf_relative"]),
        ("Log des Vues (log_vues)", df["log_vues"])
    ]
    
    for name, series in variables_to_check:
        mean_val = series.mean()
        median_val = series.median()
        skew_val = stats.skew(series)
        stat_norm, p_val = stats.normaltest(series)
        
        is_normal = "OUI (Normal)" if p_val > 0.05 else "NON (Rejet formel)"
        
        print(f"\n--- {name} ---")
        print(f"  Moyenne           : {mean_val:,.2f}")
        print(f"  Médiane           : {median_val:,.2f}")
        print(f"  Ratio Moy/Médiane : {mean_val / median_val:.2f}x")
        print(f"  Skewness          : {skew_val:.2f} (0 = symétrique, >1 = forte queue à droite)")
        print(f"  Test de Normalité : p-value = {p_val:.2e} -> Normalité : {is_normal}")


def cliffs_delta(lst1, lst2) -> tuple[float, str]:
    """
    Calcule le Delta de Cliff (taille d'effet non-paramétrique).
    Retourne la valeur du delta et son interprétation clinique.
    """
    n1, n2 = len(lst1), len(lst2)
    u_stat, _ = stats.mannwhitneyu(lst1, lst2, alternative='two-sided')
    delta = (2 * u_stat) / (n1 * n2) - 1
    
    abs_d = abs(delta)
    if abs_d < 0.147:
        magnitude = "Négligeable"
    elif abs_d < 0.33:
        magnitude = "Faible"
    elif abs_d < 0.474:
        magnitude = "Moyen"
    else:
        magnitude = "Fort"
        
    return delta, magnitude


def run_univariate_tests(df: pd.DataFrame) -> pd.DataFrame:
    """
    Étape 7.2 : Tests non-paramétriques sur H1 à H6 sur la variable perf_relative
    avec calcul de taille d'effet et correction de Benjamini-Hochberg.
    """
    print("\n" + "=" * 80)
    print(" ÉTAPE 7.2 : TESTS STATISTIQUES NON-PARAMÉTRIQUES (H1 À H6)")
    print(" Cible : Performance Relative (vues / médiane de la chaîne)")
    print("=" * 80)

    raw_results = []

    # H1 : Durée (Continue)
    rho_dur, p_dur = stats.spearmanr(df["duree_minutes"], df["perf_relative"])
    raw_results.append({
        "Hypothèse": "H1 : Durée vidéo (min)",
        "Type": "Continue (Spearman)",
        "Statistique": f"rho = {rho_dur:+.3f}",
        "p-val brute": p_dur,
        "Taille d'effet": f"rho = {abs(rho_dur):.3f}",
        "Détail": f"Médiane: {df['duree_minutes'].median():.1f} min"
    })

    # H2 : Chiffre dans le titre (Binaire)
    g_num_yes = df[df["has_number"] == 1]["perf_relative"]
    g_num_no = df[df["has_number"] == 0]["perf_relative"]
    _, p_num = stats.mannwhitneyu(g_num_yes, g_num_no, alternative='two-sided')
    delta_num, mag_num = cliffs_delta(g_num_yes, g_num_no)
    raw_results.append({
        "Hypothèse": "H2 : Chiffre dans titre",
        "Type": "Binaire (Mann-Whitney)",
        "Statistique": f"Médianes: Avec={g_num_yes.median():.2f} vs Sans={g_num_no.median():.2f}",
        "p-val brute": p_num,
        "Taille d'effet": f"delta = {delta_num:+.3f} ({mag_num})",
        "Détail": f"N: {len(g_num_yes)} vs {len(g_num_no)}"
    })

    # H3 : Question dans le titre (Binaire)
    g_q_yes = df[df["has_question"] == 1]["perf_relative"]
    g_q_no = df[df["has_question"] == 0]["perf_relative"]
    _, p_q = stats.mannwhitneyu(g_q_yes, g_q_no, alternative='two-sided')
    delta_q, mag_q = cliffs_delta(g_q_yes, g_q_no)
    raw_results.append({
        "Hypothèse": "H3 : Question dans titre",
        "Type": "Binaire (Mann-Whitney)",
        "Statistique": f"Médianes: Avec={g_q_yes.median():.2f} vs Sans={g_q_no.median():.2f}",
        "p-val brute": p_q,
        "Taille d'effet": f"delta = {delta_q:+.3f} ({mag_q})",
        "Détail": f"N: {len(g_q_yes)} vs {len(g_q_no)}"
    })

    # H4 : Mot négatif dans le titre (Binaire)
    g_neg_yes = df[df["has_negative_word"] == 1]["perf_relative"]
    g_neg_no = df[df["has_negative_word"] == 0]["perf_relative"]
    _, p_neg = stats.mannwhitneyu(g_neg_yes, g_neg_no, alternative='two-sided')
    delta_neg, mag_neg = cliffs_delta(g_neg_yes, g_neg_no)
    raw_results.append({
        "Hypothèse": "H4 : Mot négatif",
        "Type": "Binaire (Mann-Whitney)",
        "Statistique": f"Médianes: Avec={g_neg_yes.median():.2f} vs Sans={g_neg_no.median():.2f}",
        "p-val brute": p_neg,
        "Taille d'effet": f"delta = {delta_neg:+.3f} ({mag_neg})",
        "Détail": f"N: {len(g_neg_yes)} vs {len(g_neg_no)}"
    })

    # H5 : Prime Time (Binaire : Mer/Dim 17h-21h)
    g_pt_yes = df[df["is_prime_time"] == 1]["perf_relative"]
    g_pt_no = df[df["is_prime_time"] == 0]["perf_relative"]
    _, p_pt = stats.mannwhitneyu(g_pt_yes, g_pt_no, alternative='two-sided')
    delta_pt, mag_pt = cliffs_delta(g_pt_yes, g_pt_no)
    raw_results.append({
        "Hypothèse": "H5 : Prime time",
        "Type": "Binaire (Mann-Whitney)",
        "Statistique": f"Médianes: Avec={g_pt_yes.median():.2f} vs Sans={g_pt_no.median():.2f}",
        "p-val brute": p_pt,
        "Taille d'effet": f"delta = {delta_pt:+.3f} ({mag_pt})",
        "Détail": f"N: {len(g_pt_yes)} vs {len(g_pt_no)}"
    })

    # H6 : Longueur du titre (Continue)
    rho_len, p_len = stats.spearmanr(df["title_char_count"], df["perf_relative"])
    raw_results.append({
        "Hypothèse": "H6 : Longueur titre (caractères)",
        "Type": "Continue (Spearman)",
        "Statistique": f"rho = {rho_len:+.3f}",
        "p-val brute": p_len,
        "Taille d'effet": f"rho = {abs(rho_len):.3f}",
        "Détail": f"Médiane: {df['title_char_count'].median():.0f} cars"
    })

    # Correction Benjamini-Hochberg
    p_values = [r["p-val brute"] for r in raw_results]
    reject, p_adjusted, _, _ = multipletests(p_values, alpha=0.05, method='fdr_bh')

    for i, r in enumerate(raw_results):
        r["p-val ajustée"] = p_adjusted[i]
        r["Significatif (FDR < 5%)"] = "OUI (*)" if reject[i] else "NON"

    res_df = pd.DataFrame(raw_results)
    cols = ["Hypothèse", "Statistique", "Taille d'effet", "p-val brute", "p-val ajustée", "Significatif (FDR < 5%)"]
    print(res_df[cols].to_string(index=False))
    return res_df


def run_multivariate_regression(df: pd.DataFrame):
    """
    Étape 7.3 : Régression OLS multivariée avec effets fixes chaîne (Within-estimator)
    et erreurs types groupées par chaîne (Clustered Standard Errors).
    Modèle : ln(vues) ~ H1 + H2 + H3 + H4 + H5 + H6 + age_jours + C(chaine_id)
    """
    print("\n" + "=" * 80)
    print(" ÉTAPE 7.3 : RÉGRESSION MULTIVARIÉE AVEC EFFETS FIXES CHAÎNE (OLS)")
    print(" Variable Dépendante : ln(vues)")
    print(" Contrôles : Effets fixes par chaîne C(chaine_id) + Âge de la vidéo")
    print("=" * 80)

    formula = (
        "log_vues ~ duree_minutes + has_number + has_question + "
        "has_negative_word + is_prime_time + title_char_count + "
        "age_jours + C(chaine_id)"
    )

    model = smf.ols(formula=formula, data=df)
    results = model.fit(cov_type='cluster', cov_kwds={'groups': df['chaine_id']})

    hypotheses_vars = [
        ("H1: duree_minutes", "duree_minutes"),
        ("H2: has_number", "has_number"),
        ("H3: has_question", "has_question"),
        ("H4: has_negative_word", "has_negative_word"),
        ("H5: is_prime_time", "is_prime_time"),
        ("H6: title_char_count", "title_char_count"),
        ("Contrôle: age_jours", "age_jours"),
    ]

    summary_rows = []
    for label, var in hypotheses_vars:
        coef = results.params[var]
        se = results.bse[var]
        p_val = results.pvalues[var]
        pct_effect = (np.exp(coef) - 1) * 100

        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"

        summary_rows.append({
            "Caractéristique": label,
            "Coef (Beta)": f"{coef:+.4f}",
            "Erreur-Type": f"{se:.4f}",
            "Effet estimé sur Vues": f"{pct_effect:+.1f} %",
            "p-valeur": f"{p_val:.4f}",
            "Signif.": sig
        })

    reg_summary_df = pd.DataFrame(summary_rows)
    print(reg_summary_df.to_string(index=False))
    print(f"\nR² du modèle (avec effets fixes) : {results.rsquared:.3f}")
    print(f"R² ajusté                        : {results.rsquared_adj:.3f}")
    print(f"Nombre d'observations             : {int(results.nobs)}")
    print(f"Nombre de clusters (chaînes)     : {df['chaine_id'].nunique()}")
    print("\nSignificativité : *** p<0.001, ** p<0.01, * p<0.05, ns = non significatif")
    
    return results


if __name__ == "__main__":
    df = load_dataset()
    check_distributions(df)
    run_univariate_tests(df)
    run_multivariate_regression(df)
