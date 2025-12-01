import pandas as pd
from sqlalchemy import create_engine
import os
import uuid

# Connexion à votre base XAMPP
engine = create_engine("mysql+pymysql://root:@localhost/montaxi31_db")

# Liste des fichiers à migrer et leur table de destination
MAPPING = {
    "chauffeurs.csv": "chauffeurs",
    "taxis.csv": "taxis",
    "depenses_flotte.csv": "depenses",
    "revenus_hebdo.csv": "revenus"
}

print("--- DÉBUT DE LA MIGRATION ---")

for csv_file, table_name in MAPPING.items():
    if os.path.exists(csv_file):
        try:
            print(f"Traitement de {csv_file}...")
            df = pd.read_csv(csv_file)

            # 1. Correction des noms de colonnes (Ancien -> Nouveau)
            if table_name == "depenses":
                df = df.rename(columns={"Total": "Montant_Total", "HT": "Montant_HT"})
            if table_name == "revenus":
                df = df.rename(
                    columns={"Total_Brut": "Brut", "Salaire_Chauffeur": "Salaire", "Grand_Total_Remis": "A_Remettre"})

            # 2. Ajout UUID si manquant
            if "UUID" not in df.columns:
                df["UUID"] = [str(uuid.uuid4()) for _ in range(len(df))]

            # 3. Nettoyage des types (Tout en string pour éviter les erreurs SQL)
            df = df.astype(str)

            # 4. Envoi vers MySQL (append = ajoute à la suite)
            df.to_sql(table_name, engine, if_exists='append', index=False)
            print(f"✅ {len(df)} lignes importées dans la table '{table_name}'.")

        except Exception as e:
            print(f"❌ Erreur sur {csv_file}: {e}")
    else:
        print(f"⚠️ Fichier {csv_file} introuvable (Ignoré).")

print("--- TERMINÉ ---")