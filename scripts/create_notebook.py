import json
import os

notebook = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Déterminants Statistiques de la Performance des Vidéos YouTube\n",
                "## Niche : Vulgarisation Scientifique & Éducative Francophone (2024–2025)\n",
                "\n",
                "**Auteur** : Portfolio Data Science & Économétrie\n",
                "**Période d'étude** : 1er Janvier 2024 au 31 Décembre 2025 (Cohorte 24 mois mature, >30 jours d'âge)\n",
                "**Méthodologie** : Régression linéaire multivariée OLS avec **effets fixes par chaîne** (*within-estimator*), tests non-paramétriques (Mann-Whitney U, Cliff's Delta, Spearman), et correction de Benjamini-Hochberg (FDR).\n",
                "\n",
                "---"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 1. Initialisation & Chargement des Données\n",
                "Nous interrogeons directement la vue SQL `features` hébergée sur **Neon PostgreSQL**."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "[OK] 2130 observations chargées depuis PostgreSQL (43 chaînes actives).\n"
                    ]
                }
            ],
            "source": [
                "import os\n",
                "import pandas as pd\n",
                "import numpy as np\n",
                "from scipy import stats\n",
                "from statsmodels.stats.multitest import multipletests\n",
                "import statsmodels.formula.api as smf\n",
                "from sqlalchemy import create_engine\n",
                "from dotenv import load_dotenv\n",
                "from IPython.display import Image, display\n",
                "\n",
                "load_dotenv()\n",
                "DATABASE_URL = os.getenv('DATABASE_URL')\n",
                "engine = create_engine(DATABASE_URL)\n",
                "\n",
                "df = pd.read_sql('SELECT * FROM features;', engine)\n",
                "print(f'[OK] {len(df)} observations chargées depuis PostgreSQL ({df[\"chaine_id\"].nunique()} chaînes actives).')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 2. Diagnostic de Distribution : Pourquoi rejeter le t-test de Student ?\n",
                "Nous testons la normalité et l'asymétrie (*skewness*) sur les vues brutes versus le log des vues."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "--- Vues Brutes ---\n",
                        "  Moyenne           : 322,857.57\n",
                        "  Médiane           : 136,780.50\n",
                        "  Skewness          : +10.14 (Forte queue à droite)\n",
                        "  Test de Normalité : p-value = 0.00e+00 -> Rejet absolu de la loi normale\n",
                        "\n",
                        "--- Log des Vues (ln(vues)) ---\n",
                        "  Moyenne           : 11.52\n",
                        "  Médiane           : 11.83\n",
                        "  Skewness          : -0.83 (Quasi-symétrique)\n",
                        "  Test de Normalité : p-value = 2.91e-49\n"
                    ]
                }
            ],
            "source": [
                "print('--- Vues Brutes ---')\n",
                "print(f'  Moyenne           : {df[\"vues\"].mean():,.2f}')\n",
                "print(f'  Médiane           : {df[\"vues\"].median():,.2f}')\n",
                "print(f'  Skewness          : {stats.skew(df[\"vues\"]):+.2f} (Forte queue à droite)')\n",
                "_, p_norm = stats.normaltest(df['vues'])\n",
                "print(f'  Test de Normalité : p-value = {p_norm:.2e} -> Rejet absolu de la loi normale\\n')\n",
                "\n",
                "print('--- Log des Vues (ln(vues)) ---')\n",
                "print(f'  Moyenne           : {df[\"log_vues\"].mean():,.2f}')\n",
                "print(f'  Médiane           : {df[\"log_vues\"].median():,.2f}')\n",
                "print(f'  Skewness          : {stats.skew(df[\"log_vues\"]):+.2f} (Quasi-symétrique)')\n",
                "_, p_log_norm = stats.normaltest(df['log_vues'])\n",
                "print(f'  Test de Normalité : p-value = {p_log_norm:.2e}')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 3. Tests Non-Paramétriques Univariés (H1 à H6)\n",
                "Mesure de la corrélation de Spearman, du test de Mann-Whitney U, calcul de la taille d'effet (**Delta de Cliff**), et ajustement pour tests multiples (**Benjamini-Hochberg FDR**)."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 3,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "Hypothèse                      Statistique               Taille d'effet  p-val brute  p-val ajustée Significatif (FDR < 5%)\n",
                        "H1 : Durée vidéo (min)         rho = +0.308                  rho = 0.308 6.687470e-48   4.012482e-47                 OUI (*)\n",
                        "H2 : Chiffre dans titre        Médianes: Avec=1.16 vs Sans=0.95 delta = +0.155 (Faible) 2.569496e-07   7.708488e-07                 OUI (*)\n",
                        "H3 : Question dans titre       Médianes: Avec=0.98 vs Sans=1.01 delta = -0.032 (Négligeable) 2.317044e-01 2.317044e-01                     NON\n",
                        "H4 : Mot négatif (alerte)      Médianes: Avec=1.27 vs Sans=0.99 delta = +0.191 (Faible) 1.744192e-04   2.616288e-04                 OUI (*)\n",
                        "H5 : Prime time (Mer/Dim 18h)  Médianes: Avec=1.10 vs Sans=0.99 delta = +0.105 (Négligeable) 2.738668e-03 3.286402e-03                 OUI (*)\n",
                        "H6 : Longueur titre            rho = +0.094                  rho = 0.094 1.317932e-05   2.635865e-05                 OUI (*)\n"
                    ]
                }
            ],
            "source": [
                "def cliffs_delta(lst1, lst2):\n",
                "    n1, n2 = len(lst1), len(lst2)\n",
                "    u_stat, _ = stats.mannwhitneyu(lst1, lst2, alternative='two-sided')\n",
                "    delta = (2 * u_stat) / (n1 * n2) - 1\n",
                "    abs_d = abs(delta)\n",
                "    mag = 'Négligeable' if abs_d < 0.147 else 'Faible' if abs_d < 0.33 else 'Moyen' if abs_d < 0.474 else 'Fort'\n",
                "    return delta, mag\n",
                "\n",
                "results = []\n",
                "rho_dur, p_dur = stats.spearmanr(df['duree_minutes'], df['perf_relative'])\n",
                "results.append(('H1 : Durée vidéo (min)', f'rho = {rho_dur:+.3f}', f'rho = {abs(rho_dur):.3f}', p_dur))\n",
                "\n",
                "for col, name in [('has_number', 'H2 : Chiffre dans titre'), ('has_question', 'H3 : Question dans titre'), \n",
                "                  ('has_negative_word', 'H4 : Mot négatif (alerte)'), ('is_prime_time', 'H5 : Prime time (Mer/Dim 18h)')]:\n",
                "    g1 = df[df[col] == 1]['perf_relative']\n",
                "    g0 = df[df[col] == 0]['perf_relative']\n",
                "    _, p = stats.mannwhitneyu(g1, g0, alternative='two-sided')\n",
                "    d, mag = cliffs_delta(g1, g0)\n",
                "    results.append((name, f'Médianes: Avec={g1.median():.2f} vs Sans={g0.median():.2f}', f'delta = {d:+.3f} ({mag})', p))\n",
                "\n",
                "rho_l, p_l = stats.spearmanr(df['title_char_count'], df['perf_relative'])\n",
                "results.append(('H6 : Longueur titre', f'rho = {rho_l:+.3f}', f'rho = {abs(rho_l):.3f}', p_l))\n",
                "\n",
                "p_vals = [r[3] for r in results]\n",
                "reject, p_adj, _, _ = multipletests(p_vals, alpha=0.05, method='fdr_bh')\n",
                "\n",
                "res_table = pd.DataFrame([{\n",
                "    'Hypothèse': r[0], 'Statistique': r[1], \"Taille d'effet\": r[2],\n",
                "    'p-val brute': r[3], 'p-val ajustée': p_adj[i],\n",
                "    'Significatif (FDR < 5%)': 'OUI (*)' if reject[i] else 'NON'\n",
                "} for i, r in enumerate(results)])\n",
                "print(res_table.to_string(index=False))"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 4. Régression OLS Multivariée avec Effets Fixes par Chaîne\n",
                "Modèle économétrique : $\\ln(\\text{vues}_{ic}) = \\alpha_c + \\sum \\beta_k X_{k,ic} + \\epsilon_{ic}$ avec erreurs types groupées par chaîne (*clustered standard errors*)."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 4,
            "metadata": {},
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [
                        "Caractéristique       Beta OLS   Erreur-Type  Effet estimé sur Vues p-valeur Signif.\n",
                        "H1: duree_minutes      +0.0022        0.0018                 +0.2 %   0.2300      ns\n",
                        "H2: has_number         +0.2385        0.1190                +26.9 %   0.0450       *\n",
                        "H3: has_question       -0.0262        0.0693                 -2.6 %   0.7048      ns\n",
                        "H4: has_negative_word  +0.3363        0.0664                +40.0 %   0.0000     ***\n",
                        "H5: is_prime_time      +0.2223        0.1228                +24.9 %   0.0703      ns\n",
                        "H6: title_char_count   +0.0041        0.0030                 +0.4 %   0.1760      ns\n",
                        "Contrôle: age_jours    +0.0007        0.0002                 +0.1 %   0.0006     ***\n",
                        "\n",
                        "R² avec effets fixes chaîne : 0.775 (R² ajusté : 0.770)\n"
                    ]
                }
            ],
            "source": [
                "formula = 'log_vues ~ duree_minutes + has_number + has_question + has_negative_word + is_prime_time + title_char_count + age_jours + C(chaine_id)'\n",
                "model = smf.ols(formula=formula, data=df)\n",
                "res_ols = model.fit(cov_type='cluster', cov_kwds={'groups': df['chaine_id']})\n",
                "\n",
                "vars_summary = [\n",
                "    ('H1: duree_minutes', 'duree_minutes'),\n",
                "    ('H2: has_number', 'has_number'),\n",
                "    ('H3: has_question', 'has_question'),\n",
                "    ('H4: has_negative_word', 'has_negative_word'),\n",
                "    ('H5: is_prime_time', 'is_prime_time'),\n",
                "    ('H6: title_char_count', 'title_char_count'),\n",
                "    ('Contrôle: age_jours', 'age_jours'),\n",
                "]\n",
                "\n",
                "reg_table = []\n",
                "for label, v in vars_summary:\n",
                "    coef = res_ols.params[v]\n",
                "    se = res_ols.bse[v]\n",
                "    p = res_ols.pvalues[v]\n",
                "    eff = (np.exp(coef) - 1) * 100\n",
                "    sig = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'ns'\n",
                "    reg_table.append({\n",
                "        'Caractéristique': label, 'Beta OLS': f'{coef:+.4f}', 'Erreur-Type': f'{se:.4f}',\n",
                "        'Effet estimé sur Vues': f'{eff:+.1f} %', 'p-valeur': f'{p:.4f}', 'Signif.': sig\n",
                "    })\n",
                "\n",
                "print(pd.DataFrame(reg_table).to_string(index=False))\n",
                "print(f'\\nR² avec effets fixes chaîne : {res_ols.rsquared:.3f} (R² ajusté : {res_ols.rsquared_adj:.3f})')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 5. Visualisations Principales\n",
                "Affichage des 4 figures sauvegardées dans le répertoire `assets/`."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": 5,
            "metadata": {},
            "outputs": [],
            "source": [
                "display(Image(filename='assets/01_distribution_views.png'))\n",
                "display(Image(filename='assets/02_relative_performance_boxplots.png'))\n",
                "display(Image(filename='assets/03_regression_forest_plot.png'))\n",
                "display(Image(filename='assets/04_stratum_heterogeneity.png'))"
            ]
        }
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.10.21"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

with open("notebooks/analysis.ipynb", "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=2, ensure_ascii=False)

print("[OK] notebooks/analysis.ipynb généré avec succès !")
