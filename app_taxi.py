import streamlit as st
import pandas as pd
import os
import json
import uuid
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="MonTaxi31", page_icon="🚖", layout="wide")

# --- FICHIERS ---
FILES = {
    "depenses": "depenses_flotte.csv",
    "chauffeurs": "chauffeurs.csv",
    "revenus": "revenus_hebdo.csv",
    "config": "config_taxi.json"
}


# --- CHARGEMENT CONFIGURATION ---
def load_config():
    default = {
        "cout_appel": 1.05, "pct_chauf": 40.0, "taux_impot": 18.0,
        "tps": 5.0, "tvq": 9.975,
        "cats": ["Mécanique", "Carrosserie", "Pneus", "Assurance", "SAAQ", "Admin", "Pièces", "Autre"]
    }
    if os.path.exists(FILES["config"]):
        try:
            with open(FILES["config"], 'r') as f:
                return {**default, **json.load(f)}
        except:
            pass
    return default


def save_config(cfg):
    with open(FILES["config"], 'w') as f:
        json.dump(cfg, f, indent=4)


CONFIG = load_config()


# --- GESTION DES DONNÉES (PANDAS) ---
def load_data(key):
    # 1. Création si inexistant
    if not os.path.exists(FILES[key]):
        if key == "depenses":
            df = pd.DataFrame(
                columns=["Date", "Mois", "Annee", "Taxi", "Chauffeur", "Categorie", "Details", "Montant_HT", "TPS",
                         "TVQ", "Montant_Total", "UUID"])
        elif key == "chauffeurs":
            df = pd.DataFrame(columns=["Nom", "Prenom", "Matricule", "Telephone", "Note", "UUID"])
        elif key == "revenus":
            df = pd.DataFrame(columns=["Date_Debut", "Date_Fin", "Mois", "Annee", "Trimestre", "Taxi", "Chauffeur",
                                       "Meter_Deb", "Meter_Fin", "Meter_Total", "Fixe", "Total_Brut", "Nb_Appels",
                                       "Redevance", "Base_Salaire", "Salaire_Chauffeur", "STS", "Credits", "Prix_Fixes",
                                       "Visa", "Essence", "Lavage", "Divers", "Impot", "Grand_Total_Remis", "UUID"])
        df.to_csv(FILES[key], index=False)
        return df

    # 2. Lecture sécurisée
    try:
        df = pd.read_csv(FILES[key])

        # MIGRATION AUTO : Renommer les vieilles colonnes
        if key == "depenses" and "Total" in df.columns and "Montant_Total" not in df.columns:
            df = df.rename(columns={"Total": "Montant_Total", "HT": "Montant_HT"})
            save_data(key, df)

        # Conversion Types (SÉCURITÉ CONTRE L'ERREUR INT/STR)
        if key == "chauffeurs" and not df.empty:
            df["Nom"] = df["Nom"].astype(str);
            df["Prenom"] = df["Prenom"].astype(str)
        if key == "revenus" and not df.empty:
            df["Date_Debut"] = df["Date_Debut"].astype(str);
            df["Chauffeur"] = df["Chauffeur"].astype(str)

        return df
    except Exception as e:
        st.error(f"Erreur fichier {key}: {e}")
        return pd.DataFrame()


def save_data(key, df):
    df.to_csv(FILES[key], index=False)


# --- SIDEBAR ---
with st.sidebar:
    st.title("🚖 MonTaxi31")
    menu = st.radio("Navigation",
                    ["📒 Transactions", "🔧 Dépenses", "👨‍✈️ Chauffeurs", "📊 Analyse & Taxes", "⚙️ Paramètres"])
    st.markdown("---")
    st.caption(f"Taux: TPS {CONFIG['tps']}% | TVQ {CONFIG['tvq']}%")

# =============================================================================
# ONGLET 1 : TRANSACTIONS (Revenus)
# =============================================================================
if menu == "📒 Transactions":
    st.header("Saisie des Revenus Hebdo")

    df_rev = load_data("revenus")
    df_chauf = load_data("chauffeurs")

    liste_chauffeurs = []
    if not df_chauf.empty:
        liste_chauffeurs = (df_chauf["Nom"].astype(str) + " " + df_chauf["Prenom"].astype(str)).tolist()

    mode = st.radio("Mode", ["Nouvelle Semaine", "Modifier existant"], horizontal=True)

    default_vals = {}
    edit_uuid = None

    if mode == "Modifier existant" and not df_rev.empty:
        df_rev["Label"] = df_rev["Date_Debut"].astype(str) + " - " + df_rev["Chauffeur"].astype(str)
        selected_label = st.selectbox("Choisir transaction", df_rev["Label"].unique())

        if selected_label:
            row = df_rev[df_rev["Label"] == selected_label].iloc[0]
            edit_uuid = row["UUID"]
            for col in row.index:
                default_vals[col] = row[col]

    with st.form("form_trans"):
        c1, c2, c3 = st.columns(3)
        try:
            default_date = pd.to_datetime(default_vals.get("Date_Debut", datetime.now()))
        except:
            default_date = datetime.now()

        date_in = c1.date_input("Date Début (Lundi)", value=default_date)
        taxi_in = c2.text_input("Taxi #", value=default_vals.get("Taxi", ""))

        idx = 0
        if "Chauffeur" in default_vals and default_vals["Chauffeur"] in liste_chauffeurs:
            idx = liste_chauffeurs.index(default_vals["Chauffeur"])
        chauf_in = c3.selectbox("Chauffeur", liste_chauffeurs, index=idx)

        st.subheader("1. Calculs Meter")
        c1, c2, c3, c4 = st.columns(4)
        m_deb = c1.number_input("Meter Début", value=float(default_vals.get("Meter_Deb", 0.0)))
        m_fin = c2.number_input("Meter Fin", value=float(default_vals.get("Meter_Fin", 0.0)))
        fixe = c3.number_input("Montants Fixes", value=float(default_vals.get("Fixe", 0.0)))
        nb_app = c4.number_input("Nb Appels", value=int(default_vals.get("Nb_Appels", 0)), step=1)

        meter_tot = m_fin - m_deb
        brut = meter_tot + fixe
        redev = nb_app * CONFIG['cout_appel']
        base_sal = brut - redev
        salaire = base_sal * (CONFIG['pct_chauf'] / 100)

        st.info(
            f"📊 Meter Total: {meter_tot:.2f} $ | Brut: {brut:.2f} $ | Salaire ({CONFIG['pct_chauf']}%): **{salaire:.2f} $**")

        st.subheader("2. Déductions & Impôt")
        c1, c2, c3, c4 = st.columns(4)
        sts = c1.number_input("STS", value=float(default_vals.get("STS", 0.0)))
        cred = c2.number_input("Crédits", value=float(default_vals.get("Credits", 0.0)))
        pf = c3.number_input("Prix Fixes", value=float(default_vals.get("Prix_Fixes", 0.0)))
        visa = c4.number_input("Visa/Débit", value=float(default_vals.get("Visa", 0.0)))

        c1, c2, c3, c4 = st.columns(4)
        ess = c1.number_input("Essence", value=float(default_vals.get("Essence", 0.0)))
        lav = c2.number_input("Lavage", value=float(default_vals.get("Lavage", 0.0)))
        div = c3.number_input("Divers", value=float(default_vals.get("Divers", 0.0)))

        impot_auto = salaire * (CONFIG['taux_impot'] / 100)
        imp = c4.number_input(f"Impôt ({CONFIG['taux_impot']}%)", value=float(default_vals.get("Impot", impot_auto)))

        btn_text = "MODIFIER LA TRANSACTION" if edit_uuid else "ENREGISTRER LA SEMAINE"
        # CORRECTION ICI (ligne 172)
        submitted = st.form_submit_button(btn_text, type="primary")

        if submitted:
            deducs = sts + cred + pf + visa + ess + lav + div
            a_remettre = brut - salaire - deducs + imp

            d_fin = (date_in + timedelta(days=6))
            mois = date_in.strftime("%Y-%m")
            annee = str(date_in.year)
            trim = f"T{(date_in.month - 1) // 3 + 1}"

            # Utilisation des noms de colonnes exacts
            new_row = {
                "Date_Debut": date_in, "Date_Fin": d_fin, "Mois": mois, "Annee": annee, "Trimestre": trim,
                "Taxi": taxi_in, "Chauffeur": chauf_in,
                "Meter_Deb": m_deb, "Meter_Fin": m_fin, "Meter_Total": meter_tot, "Fixe": fixe,
                "Total_Brut": brut,
                "Nb_Appels": nb_app, "Redevance": redev, "Base_Salaire": base_sal,
                "Salaire_Chauffeur": salaire,
                "STS": sts, "Credits": cred, "Prix_Fixes": pf, "Visa": visa, "Essence": ess, "Lavage": lav,
                "Divers": div,
                "Impot": imp,
                "Grand_Total_Remis": a_remettre,
                "UUID": edit_uuid if edit_uuid else str(uuid.uuid4())
            }

            if edit_uuid:
                idx = df_rev.index[df_rev["UUID"] == edit_uuid].tolist()
                if idx:
                    for k, v in new_row.items(): df_rev.at[idx[0], k] = v
                    st.success(f"Modifié ! À Remettre : {a_remettre:.2f} $")
            else:
                df_rev = pd.concat([df_rev, pd.DataFrame([new_row])], ignore_index=True)
                st.success(f"Ajouté ! À Remettre : {a_remettre:.2f} $")

            if "Label" in df_rev.columns: df_rev = df_rev.drop(columns=["Label"])
            save_data("revenus", df_rev)

    st.divider()
    st.write("### Historique Récent")
    if not df_rev.empty:
        cols_exist = [c for c in
                      ["Date_Debut", "Taxi", "Chauffeur", "Total_Brut", "Salaire_Chauffeur", "Grand_Total_Remis",
                       "UUID"] if c in df_rev.columns]

        edited_rev = st.data_editor(
            df_rev[cols_exist],
            column_config={
                "UUID": None,
                "Grand_Total_Remis": st.column_config.NumberColumn("À Remettre ($)", format="%.2f $"),
                "Salaire_Chauffeur": st.column_config.NumberColumn("Salaire ($)", format="%.2f $"),
            },
            num_rows="dynamic",
            key="editor_rev"
        )
        if len(edited_rev) < len(df_rev):
            uuids_restants = edited_rev["UUID"].tolist()
            df_rev_new = df_rev[df_rev["UUID"].isin(uuids_restants)]
            save_data("revenus", df_rev_new)
            st.rerun()

# =============================================================================
# ONGLET 2 : DÉPENSES
# =============================================================================
elif menu == "🔧 Dépenses":
    st.header("Gestion Dépenses Garage")
    df_dep = load_data("depenses")
    df_chauf = load_data("chauffeurs")

    with st.expander("Ajouter une dépense", expanded=True):
        c1, c2 = st.columns(2)
        d_date = c1.date_input("Date")
        d_taxi = c2.text_input("Taxi")
        d_cat = c1.selectbox("Catégorie", CONFIG["cats"])

        liste_noms = ["Aucun"]
        if not df_chauf.empty:
            liste_noms += (df_chauf["Nom"].astype(str) + " " + df_chauf["Prenom"].astype(str)).tolist()

        d_chauf = c2.selectbox("Chauffeur lié", liste_noms)
        d_desc = st.text_input("Description")

        c1, c2, c3 = st.columns(3)
        d_total = c1.number_input("Montant TOTAL", min_value=0.0, step=0.01)
        tax_incl = c2.checkbox("Taxes Incluses (TPS/TVQ)?")

        if st.button("Ajouter Dépense", type="primary"):
            if tax_incl:
                div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)
                ht = d_total / div
                tps = ht * (CONFIG["tps"] / 100)
                tvq = ht * (CONFIG["tvq"] / 100)
            else:
                ht, tps, tvq = d_total, 0.0, 0.0

            new_dep = {
                "Date": d_date, "Mois": d_date.strftime("%Y-%m"), "Annee": str(d_date.year),
                "Taxi": d_taxi, "Chauffeur": d_chauf, "Categorie": d_cat, "Details": d_desc,
                "Montant_HT": round(ht, 2), "TPS": round(tps, 2), "TVQ": round(tvq, 2), "Montant_Total": d_total,
                "UUID": str(uuid.uuid4())
            }
            df_dep = pd.concat([df_dep, pd.DataFrame([new_dep])], ignore_index=True)
            save_data("depenses", df_dep)
            st.success("Enregistré !")
            st.rerun()

    st.write("### Liste des dépenses")
    if not df_dep.empty:
        edited_df = st.data_editor(
            df_dep,
            column_config={
                "UUID": None,
                "Montant_Total": st.column_config.NumberColumn("Total ($)", format="%.2f $"),
                "TPS": st.column_config.NumberColumn("TPS ($)", format="%.2f $"),
                "TVQ": st.column_config.NumberColumn("TVQ ($)", format="%.2f $"),
            },
            num_rows="dynamic",
            key="editor_dep"
        )
        if not edited_df.equals(df_dep):
            save_data("depenses", edited_df)
            st.rerun()

# =============================================================================
# ONGLET 3 : CHAUFFEURS
# =============================================================================
elif menu == "👨‍✈️ Chauffeurs":
    st.header("Base de données Chauffeurs")
    df_c = load_data("chauffeurs")

    with st.form("add_chauf"):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nom")
        prenom = c2.text_input("Prénom")
        mat = c1.text_input("Matricule")
        tel = c2.text_input("Téléphone")
        note = st.text_area("Note")
        if st.form_submit_button("Ajouter Chauffeur", type="primary"):
            if nom:
                new = {"Nom": nom, "Prenom": prenom, "Matricule": mat, "Telephone": tel, "Note": note,
                       "UUID": str(uuid.uuid4())}
                df_c = pd.concat([df_c, pd.DataFrame([new])], ignore_index=True)
                save_data("chauffeurs", df_c)
                st.success("Ajouté !")
                st.rerun()

    if not df_c.empty:
        st.data_editor(
            df_c,
            column_config={"UUID": None},
            num_rows="dynamic",
            key="editor_chauf",
            on_change=lambda: save_data("chauffeurs", st.session_state.editor_chauf)
        )

# =============================================================================
# ONGLET 4 : ANALYSE & SYNTHÈSE
# =============================================================================
elif menu == "📊 Analyse & Taxes":
    st.header("Tableau de Bord Financier")

    df_rev = load_data("revenus")
    df_dep = load_data("depenses")

    # --- FILTRES ---
    annees = []
    if not df_rev.empty: annees += df_rev["Annee"].astype(str).tolist()
    if not df_dep.empty: annees += df_dep["Annee"].astype(str).tolist()
    annees = sorted(list(set(annees)), reverse=True)
    if not annees: annees = [str(datetime.now().year)]

    c1, c2 = st.columns(2)
    annee_sel = c1.selectbox("Année", annees)
    vue = c2.selectbox("Regroupement", ["Mois", "Trimestre", "Annuel"])

    # --- CALCULS ---
    df_syn_rev = pd.DataFrame()
    df_syn_dep = pd.DataFrame()

    # 1. Revenus (Sommes strictes)
    if not df_rev.empty:
        df_rev_filt = df_rev[df_rev["Annee"].astype(str) == str(annee_sel)].copy()

        div_taxe = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)

        for col in ["Essence", "Lavage", "Total_Brut", "Salaire_Chauffeur", "Grand_Total_Remis"]:
            if col in df_rev_filt.columns:
                df_rev_filt[col] = pd.to_numeric(df_rev_filt[col], errors='coerce').fillna(0)
            else:
                df_rev_filt[col] = 0.0

        df_rev_filt["Taxes_Ess_Base"] = (df_rev_filt["Essence"] + df_rev_filt["Lavage"]) / div_taxe
        df_rev_filt["TPS_Ess"] = df_rev_filt["Taxes_Ess_Base"] * (CONFIG["tps"] / 100)
        df_rev_filt["TVQ_Ess"] = df_rev_filt["Taxes_Ess_Base"] * (CONFIG["tvq"] / 100)

        grp_col = "Mois" if vue == "Mois" else ("Trimestre" if vue == "Trimestre" else "Annee")
        # SOMMES GROUPÉES
        df_syn_rev = df_rev_filt.groupby(grp_col)[
            ["Total_Brut", "Salaire_Chauffeur", "Grand_Total_Remis", "TPS_Ess", "TVQ_Ess"]].sum()

    # 2. Dépenses (Sommes strictes)
    if not df_dep.empty:
        df_dep_filt = df_dep[df_dep["Annee"].astype(str) == str(annee_sel)].copy()

        if vue == "Trimestre":
            df_dep_filt["Trimestre"] = "T" + ((pd.to_datetime(df_dep_filt["Date"]).dt.month - 1) // 3 + 1).astype(str)

        col_dep_grp = "Trimestre" if vue == "Trimestre" else ("Mois" if vue == "Mois" else "Annee")

        # NOMS DE COLONNES CORRIGÉS
        for col in ["TPS", "TVQ", "Montant_Total"]:
            if col in df_dep_filt.columns:
                df_dep_filt[col] = pd.to_numeric(df_dep_filt[col], errors='coerce').fillna(0)
            else:
                df_dep_filt[col] = 0.0

        df_syn_dep = df_dep_filt.groupby(col_dep_grp)[["TPS", "TVQ", "Montant_Total"]].sum()

    # 3. FUSION & AFFICHAGE
    if not df_syn_rev.empty or not df_syn_dep.empty:
        df_final = df_syn_rev.join(df_syn_dep, lsuffix="_R", rsuffix="_D", how="outer").fillna(0)

        df_final["TPS à Recevoir"] = df_final.get("TPS_Ess", 0) + df_final.get("TPS", 0)
        df_final["TVQ à Recevoir"] = df_final.get("TVQ_Ess", 0) + df_final.get("TVQ", 0)
        df_final["PROFIT NET"] = df_final.get("Grand_Total_Remis", 0) - df_final.get("Montant_Total", 0)

        df_final = df_final.rename(columns={
            "Total_Brut": "Revenu BRUT",
            "Salaire_Chauffeur": "Salaire (40%)",
            "Grand_Total_Remis": "Net Perçu"
        })

        cols_final = ["Revenu BRUT", "Salaire (40%)", "Net Perçu", "TPS à Recevoir", "TVQ à Recevoir", "PROFIT NET"]
        cols_present = [c for c in cols_final if c in df_final.columns]

        st.subheader(f"Synthèse {annee_sel}")
        st.dataframe(df_final[cols_present].style.format("{:.2f} $"), use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total TPS à Recevoir", f"{df_final['TPS à Recevoir'].sum():.2f} $")
        c2.metric("Total TVQ à Recevoir", f"{df_final['TVQ à Recevoir'].sum():.2f} $")
        c3.metric("Profit Net Annuel", f"{df_final['PROFIT NET'].sum():.2f} $")

        st.divider()
        st.subheader("Audit des taxes (Détail)")

        audit_list = []
        if not df_dep.empty:
            for _, r in df_dep_filt.iterrows():
                if r.get("TPS", 0) > 0: audit_list.append(
                    {"Date": r["Date"], "Source": r["Categorie"], "TPS": r["TPS"], "TVQ": r["TVQ"],
                     "Total TTC": r["Montant_Total"]})
        if not df_rev.empty:
            for _, r in df_rev_filt.iterrows():
                if r.get("TPS_Ess", 0) > 0:
                    total_ess = r.get("Essence", 0) + r.get("Lavage", 0)
                    audit_list.append(
                        {"Date": r["Date_Debut"], "Source": "Essence/Lavage", "TPS": r["TPS_Ess"], "TVQ": r["TVQ_Ess"],
                         "Total TTC": total_ess})

        if audit_list:
            df_audit = pd.DataFrame(audit_list).sort_values("Date", ascending=False)
            st.dataframe(df_audit.style.format({"TPS": "{:.2f}", "TVQ": "{:.2f}", "Total TTC": "{:.2f}"}),
                         use_container_width=True)
    else:
        st.info("Aucune donnée pour cette année.")

# =============================================================================
# ONGLET 5 : PARAMÈTRES
# =============================================================================
elif menu == "⚙️ Paramètres":
    st.header("Configuration")

    with st.form("config_form"):
        c1, c2 = st.columns(2)
        new_cout = c1.number_input("Coût Appel ($)", value=CONFIG["cout_appel"])
        new_pct = c2.number_input("% Salaire Chauffeur", value=CONFIG["pct_chauf"])
        new_impot = c1.number_input("% Impôt", value=CONFIG["taux_impot"])
        new_tps = c1.number_input("% TPS", value=CONFIG["tps"])
        new_tvq = c2.number_input("% TVQ", value=CONFIG["tvq"])

        st.write("Catégories de Dépenses")
        cats_text = st.text_area("Une par ligne", value="\n".join(CONFIG["cats"]))

        if st.form_submit_button("Sauvegarder Configuration", type="primary"):
            new_conf = {
                "cout_appel": new_cout, "pct_chauf": new_pct, "taux_impot": new_impot,
                "tps": new_tps, "tvq": new_tvq,
                "cats": [c.strip() for c in cats_text.split('\n') if c.strip()]
            }
            save_config(new_conf)
            st.success("Sauvegardé ! Rechargez la page pour voir les nouvelles catégories Yes.")