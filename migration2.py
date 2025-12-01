import pandas as pd
from sqlalchemy import create_engine, text
import os
import uuid

# --- CONFIGURATION ---
DB_CONNECTION = "mysql+pymysql://root:@localhost/montaxi31_db"
engine = create_engine(DB_CONNECTION)

MAPPING = {
    "chauffeurs.csv": "chauffeurs",
    "taxis.csv": "taxis",
    "depenses_flotte.csv": "depenses",
    "revenus_hebdo.csv": "revenus"
}

print("🚀 DÉBUT DE LA MIGRATION FORCÉE...")

for csv_file, table_name in MAPPING.items():
    if os.path.exists(csv_file):
        try:
            print(f"📂 Lecture de {csv_file}...")
            df = pd.read_csv(csv_file)

            # 1. Nettoyage et Renommage INTELLIGENT (Seulement si nécessaire)
            if table_name == "depenses":
                if "Total" in df.columns: df = df.rename(columns={"Total": "Montant_Total"})
                if "HT" in df.columns: df = df.rename(columns={"HT": "Montant_HT"})

            if table_name == "revenus":
                if "Total_Brut" not in df.columns and "Brut" in df.columns:
                    # Si le CSV a déjà le nouveau nom 'Brut', on peut le garder ou le renommer selon le standard SQL voulu
                    # Ici, on s'assure d'avoir les noms standards de l'application
                    df = df.rename(columns={"Brut": "Total_Brut"})
                if "A_Remettre" in df.columns: df = df.rename(columns={"A_Remettre": "Grand_Total_Remis"})
                if "Salaire" in df.columns: df = df.rename(columns={"Salaire": "Salaire_Chauffeur"})

            # 2. Ajout UUID si manquant
            if "UUID" not in df.columns:
                print(f"   -> Génération des UUIDs manquants...")
                df["UUID"] = [str(uuid.uuid4()) for _ in range(len(df))]

            # 3. Conversion de TOUT en texte pour éviter les erreurs de types SQL
            # (Streamlit convertira en chiffres lors de l'affichage)
            df = df.astype(str)

            # 4. ÉCRASEMENT DE LA TABLE SQL (C'est la clé du succès)
            # if_exists='replace' va supprimer la vieille table buggée et en recréer une parfaite
            print(f"   -> Écriture dans la table '{table_name}' (Mode REPLACE)...")
            df.to_sql(table_name, engine, if_exists='replace', index=False)

            print(f"✅ Succès : {len(df)} lignes migrées pour '{table_name}'.")

        except Exception as e:
            print(f"❌ ERREUR CRITIQUE sur {csv_file}: {e}")
    else:
        print(f"⚠️ Ignoré : {csv_file} introuvable.")

print("\n🏁 MIGRATION TERMINÉE. Vous pouvez lancer l'application !")