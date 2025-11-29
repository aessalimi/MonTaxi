import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import os
import json
import uuid
from datetime import datetime, timedelta

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MonTaxi31", page_icon="🚖", layout="wide")

# --- FICHIERS ---
FILES = {
    "dep": "depenses_flotte.csv",
    "chauf": "chauffeurs.csv",
    "rev": "revenus_hebdo.csv",
    "conf": "config_taxi.json"
}


# --- CHARGEMENT CONFIG ---
def load_config():
    default = {
        "cout_appel": 1.05, "pct_chauf": 40.0, "taux_impot": 18.0,
        "tps": 5.0, "tvq": 9.975,
        "cats": ["Mécanique", "Carrosserie", "Pneus", "Assurance", "SAAQ", "Admin", "Pièces", "Autre"]
    }
    if os.path.exists(FILES["conf"]):
        try:
            with open(FILES["conf"], 'r') as f:
                return {**default, **json.load(f)}
        except:
            pass
    return default


def save_config(cfg):
    with open(FILES["conf"], 'w') as f: json.dump(cfg, f, indent=4)


CONFIG = load_config()


# --- GESTION DONNÉES (BLINDÉE) ---
def load_data(key):
    # Définition des colonnes attendues (Nouvelle version)
    cols_expected = []
    if key == "dep":
        cols_expected = ["Date", "Mois", "Annee", "Trimestre", "Taxi", "Chauffeur", "Categorie", "Details", "HT", "TPS",
                         "TVQ", "Total", "UUID"]
    elif key == "chauf":
        cols_expected = ["Nom", "Prenom", "Matricule", "Telephone", "Note", "UUID"]
    elif key == "rev":
        cols_expected = ["Date_Debut", "Date_Fin", "Mois", "Annee", "Trimestre", "Taxi", "Chauffeur",
                         "Meter_Deb", "Meter_Fin", "Meter_Total", "Fixe", "Brut", "Nb_Appels",
                         "Redevance", "Base_Salaire", "Salaire", "STS", "Credits", "Prix_Fixes",
                         "Visa", "Essence", "Lavage", "Divers", "Impot", "A_Remettre", "UUID"]

    if not os.path.exists(FILES[key]):
        df = pd.DataFrame(columns=cols_expected)
        df.to_csv(FILES[key], index=False)
        return df

    try:
        df = pd.read_csv(FILES[key])

        # --- MIGRATION AUTOMATIQUE DES ANCIENS NOMS ---
        # Si on trouve les anciens noms, on les renomme vers les nouveaux
        rename_map = {}
        if key == "rev":
            rename_map = {
                "Grand_Total_Remis": "A_Remettre",
                "Total_Brut": "Brut",
                "Salaire_Chauffeur": "Salaire"
            }
        elif key == "dep":
            rename_map = {
                "Montant_Total": "Total",
                "Montant_HT": "HT"
            }

        # Appliquer le renommage si nécessaire
        df = df.rename(columns=rename_map)

        # --- AJOUT DES COLONNES MANQUANTES ---
        # Si une colonne manque (ex: UUID dans un vieux fichier), on l'ajoute
        for col in cols_expected:
            if col not in df.columns:
                df[col] = "" if col == "UUID" else 0.0
                # Générer des UUIDs s'ils manquent
                if col == "UUID":
                    df["UUID"] = [str(uuid.uuid4()) for _ in range(len(df))]

        # --- SÉCURISATION DES TYPES ---
        # Force conversion texte
        for col in ["Nom", "Prenom", "Taxi", "Chauffeur", "Date_Debut", "Date", "Mois", "Annee", "Trimestre", "UUID"]:
            if col in df.columns: df[col] = df[col].astype(str)

        # Force conversion numérique
        num_cols = ["Total", "TPS", "TVQ", "Brut", "Salaire", "A_Remettre", "Essence", "Lavage"]
        for col in num_cols:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # Sauvegarder la version "propre" tout de suite
        df = df[cols_expected]  # Réordonner proprement
        df.to_csv(FILES[key], index=False)

        return df
    except Exception as e:
        st.error(f"Erreur fichier {key} : {e}")
        return pd.DataFrame(columns=cols_expected)


def save_data(key, df):
    df.to_csv(FILES[key], index=False)


# --- MENU STYLE SITE WEB ---
selected_menu = option_menu(
    menu_title=None,
    options=["Transactions", "Dépenses", "Chauffeurs", "Synthèse", "Paramètres"],
    icons=["receipt", "wrench", "person-badge", "graph-up", "gear"],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#f0f2f6"},
        "icon": {"color": "orange", "font-size": "18px"},
        "nav-link": {"font-size": "16px", "text-align": "center", "margin": "0px", "--hover-color": "#eee"},
        "nav-link-selected": {"background-color": "#008CBA"},
    }
)

# --- SESSION STATE ---
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'edit_id' not in st.session_state: st.session_state.edit_id = None
if 'form_data' not in st.session_state: st.session_state.form_data = {}


def reset_form():
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.form_data = {}


# =============================================================================
# 1. TRANSACTIONS (CRUD)
# =============================================================================
if selected_menu == "Transactions":
    st.subheader("📒 Gestion des Revenus Hebdomadaires")

    df_rev = load_data("rev")
    df_chauf = load_data("chauf")
    l_chauf = (df_chauf["Nom"] + " " + df_chauf["Prenom"]).tolist() if not df_chauf.empty else []

    # --- LISTE (READ) ---
    col_list, col_form = st.columns([1, 1])

    with col_list:
        st.info("👆 Sélectionnez une ligne pour modifier")

        # Sécurisation si le tableau est vide
        if not df_rev.empty:
            # On affiche uniquement les colonnes pertinentes
            display_df = df_rev[["Date_Debut", "Taxi", "Chauffeur", "A_Remettre"]].sort_values("Date_Debut",
                                                                                               ascending=False)

            event = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            if event.selection.rows:
                # Récupération intelligente de la ligne
                idx_displayed = event.selection.rows[0]
                # Retrouver l'index réel dans le dataframe complet
                real_index = display_df.index[idx_displayed]
                row_data = df_rev.loc[real_index]

                if st.button("Charger la sélection"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = row_data["UUID"]
                    st.session_state.form_data = row_data.to_dict()
                    st.rerun()
        else:
            st.warning("Aucune transaction enregistrée.")

        if st.button("Vider / Nouvelle Saisie"):
            reset_form()
            st.rerun()

    # --- FORMULAIRE (CREATE/UPDATE) ---
    with col_form:
        f_title = f"✏️ Modifier Transaction" if st.session_state.edit_mode else "➕ Nouvelle Transaction"
        mode_color = "orange" if st.session_state.edit_mode else "green"
        st.markdown(f":{mode_color}[**{f_title}**]")

        fd = st.session_state.form_data

        with st.form("crud_trans_form"):
            c1, c2 = st.columns(2)
            try:
                d_val = pd.to_datetime(fd.get("Date_Debut", datetime.now()))
            except:
                d_val = datetime.now()

            d_in = c1.date_input("Date Début", value=d_val)
            t_in = c2.text_input("Taxi", value=fd.get("Taxi", ""))

            c_idx = 0
            if fd.get("Chauffeur") in l_chauf: c_idx = l_chauf.index(fd.get("Chauffeur"))
            ch_in = c1.selectbox("Chauffeur", l_chauf, index=c_idx) if l_chauf else c1.text_input("Chauffeur (Nom)",
                                                                                                  value=fd.get(
                                                                                                      "Chauffeur", ""))

            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            m_d = c1.number_input("Meter Déb", value=float(fd.get("Meter_Deb", 0.0)))
            m_f = c2.number_input("Meter Fin", value=float(fd.get("Meter_Fin", 0.0)))
            fixe = c3.number_input("Fixe", value=float(fd.get("Fixe", 0.0)))
            nb = c4.number_input("Nb Appels", value=int(fd.get("Nb_Appels", 0)))

            st.caption("Déductions")
            c1, c2, c3 = st.columns(3)
            sts = c1.number_input("STS", value=float(fd.get("STS", 0.0)))
            cred = c2.number_input("Crédits", value=float(fd.get("Credits", 0.0)))
            visa = c3.number_input("Visa", value=float(fd.get("Visa", 0.0)))

            c1, c2, c3 = st.columns(3)
            ess = c1.number_input("Essence", value=float(fd.get("Essence", 0.0)))
            lav = c2.number_input("Lavage", value=float(fd.get("Lavage", 0.0)))
            div = c3.number_input("Divers", value=float(fd.get("Divers", 0.0)))

            # Action Buttons
            c_save, c_del = st.columns([2, 1])
            save_label = "Mettre à jour" if st.session_state.edit_mode else "Enregistrer"
            submit = c_save.form_submit_button(save_label, type="primary", use_container_width=True)
            delete = False
            if st.session_state.edit_mode:
                delete = c_del.form_submit_button("Supprimer", type="primary", use_container_width=True)

            if submit:
                # Verif Doublons (Date + Taxi) en mode création
                is_dup = False
                if not st.session_state.edit_mode:
                    if not df_rev.empty:
                        check = df_rev[(df_rev['Date_Debut'] == str(d_in)) & (df_rev['Taxi'] == str(t_in))]
                        if not check.empty:
                            st.error("⛔ Doublon détecté (Date + Taxi) !")
                            is_dup = True

                if not is_dup:
                    mt = m_f - m_d
                    brut = mt + fixe
                    redev = nb * CONFIG["cout_appel"]
                    base = brut - redev
                    sal = base * (CONFIG["pct_chauf"] / 100)
                    imp = sal * (CONFIG["taux_impot"] / 100)
                    deducs = sts + cred + visa + ess + lav + div
                    # On garde Prix_Fixes s'il existait en mémoire, sinon 0
                    pf = float(fd.get("Prix_Fixes", 0.0))
                    net = brut - sal - deducs + imp

                    row_data = {
                        "Date_Debut": d_in, "Date_Fin": d_in + timedelta(days=6),
                        "Mois": d_in.strftime("%Y-%m"), "Annee": str(d_in.year),
                        "Trimestre": f"T{(d_in.month - 1) // 3 + 1}",
                        "Taxi": t_in, "Chauffeur": ch_in,
                        "Meter_Deb": m_d, "Meter_Fin": m_f, "Meter_Total": mt,
                        "Fixe": fixe, "Brut": brut, "Nb_Appels": nb, "Redevance": redev,
                        "Base_Salaire": base, "Salaire": round(sal, 2),
                        "STS": sts, "Credits": cred, "Prix_Fixes": pf, "Visa": visa,
                        "Essence": ess, "Lavage": lav, "Divers": div, "Impot": round(imp, 2),
                        "A_Remettre": round(net, 2),
                        "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())
                    }

                    if st.session_state.edit_mode:
                        df_rev = df_rev[df_rev.UUID != st.session_state.edit_id]

                    df_rev = pd.concat([df_rev, pd.DataFrame([row_data])], ignore_index=True)
                    save_data("rev", df_rev)
                    st.success("Enregistré !")
                    reset_form()
                    st.rerun()

            if delete:
                df_rev = df_rev[df_rev.UUID != st.session_state.edit_id]
                save_data("rev", df_rev)
                st.warning("Supprimé !")
                reset_form()
                st.rerun()

# =============================================================================
# 2. DEPENSES (CRUD)
# =============================================================================
elif selected_menu == "Dépenses":
    st.subheader("🔧 Dépenses Garage")
    df_dep = load_data("dep")
    df_chauf = load_data("chauf")

    col_list, col_form = st.columns([1, 1])

    with col_list:
        st.info("Sélectionnez une dépense")
        if not df_dep.empty:
            sorted_df = df_dep.sort_values("Date", ascending=False)
            event = st.dataframe(sorted_df[["Date", "Taxi", "Categorie", "Total"]], use_container_width=True,
                                 hide_index=True, on_select="rerun", selection_mode="single-row")

            if event.selection.rows:
                idx = event.selection.rows[0]
                real_idx = sorted_df.index[idx]
                row_data = df_dep.loc[real_idx]
                if st.button("Charger Dépense"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = row_data["UUID"]
                    st.session_state.form_data = row_data.to_dict()
                    st.rerun()
        else:
            st.warning("Aucune dépense.")

        if st.button("Nouvelle Dépense"): reset_form(); st.rerun()

    with col_form:
        f_title = f"✏️ Modifier" if st.session_state.edit_mode else "➕ Ajouter"
        st.markdown(f"**{f_title}**")
        fd = st.session_state.form_data

        with st.form("crud_dep"):
            c1, c2 = st.columns(2)
            try:
                d_val = pd.to_datetime(fd.get("Date", datetime.now()))
            except:
                d_val = datetime.now()

            d_date = c1.date_input("Date", value=d_val)
            d_taxi = c2.text_input("Taxi", value=fd.get("Taxi", ""))

            cat_idx = 0
            if fd.get("Categorie") in CONFIG["cats"]: cat_idx = CONFIG["cats"].index(fd.get("Categorie"))
            d_cat = c1.selectbox("Catégorie", CONFIG["cats"], index=cat_idx)

            c1, c2 = st.columns(2)
            d_tot = c1.number_input("Total ($)", value=float(fd.get("Total", 0.0)))
            # Checkbox: Si TPS > 0, on coche par défaut
            is_taxed = float(fd.get("TPS", 0.0)) > 0
            tax_in = c2.checkbox("Taxes Incluses?", value=is_taxed)

            c_s, c_d = st.columns(2)
            sub = c_s.form_submit_button("Sauvegarder", type="primary")
            dele = False
            if st.session_state.edit_mode: dele = c_d.form_submit_button("Supprimer")

            if sub:
                if tax_in:
                    div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)
                    ht = d_tot / div
                    tps = ht * (CONFIG["tps"] / 100)
                    tvq = ht * (CONFIG["tvq"] / 100)
                else:
                    ht, tps, tvq = d_tot, 0.0, 0.0

                row = {
                    "Date": d_date, "Mois": d_date.strftime("%Y-%m"), "Annee": str(d_date.year),
                    "Trimestre": f"T{(d_date.month - 1) // 3 + 1}", "Taxi": d_taxi,
                    "Chauffeur": fd.get("Chauffeur", ""),
                    "Categorie": d_cat, "Details": fd.get("Details", ""),
                    "HT": round(ht, 2), "TPS": round(tps, 2), "TVQ": round(tvq, 2), "Total": d_tot,
                    "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())
                }

                if st.session_state.edit_mode: df_dep = df_dep[df_dep.UUID != st.session_state.edit_id]
                df_dep = pd.concat([df_dep, pd.DataFrame([row])], ignore_index=True)
                save_data("dep", df_dep)
                st.success("Sauvegardé");
                reset_form();
                st.rerun()

            if dele:
                df_dep = df_dep[df_dep.UUID != st.session_state.edit_id]
                save_data("dep", df_dep)
                st.success("Supprimé");
                reset_form();
                st.rerun()

# =============================================================================
# 3. CHAUFFEURS (CRUD)
# =============================================================================
elif selected_menu == "Chauffeurs":
    st.subheader("👨‍✈️ Gestion Chauffeurs")
    df_c = load_data("chauf")

    col_list, col_form = st.columns([1, 1])
    with col_list:
        if not df_c.empty:
            event = st.dataframe(df_c[["Nom", "Prenom", "Telephone"]], on_select="rerun", selection_mode="single-row",
                                 use_container_width=True, hide_index=True)
            if event.selection.rows:
                idx = event.selection.rows[0]
                # Fix pour retrouver la bonne ligne
                real_idx = df_c.index[idx]
                row_data = df_c.loc[real_idx]
                if st.button("Modifier Chauffeur"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = row_data["UUID"]
                    st.session_state.form_data = row_data.to_dict()
                    st.rerun()
        if st.button("Nouveau Chauffeur"): reset_form(); st.rerun()

    with col_form:
        fd = st.session_state.form_data
        with st.form("crud_chauf"):
            n = st.text_input("Nom", value=fd.get("Nom", ""))
            p = st.text_input("Prénom", value=fd.get("Prenom", ""))
            t = st.text_input("Téléphone", value=fd.get("Telephone", ""))

            c1, c2 = st.columns(2)
            sub = c1.form_submit_button("Sauvegarder", type="primary")
            dele = False
            if st.session_state.edit_mode: dele = c2.form_submit_button("Supprimer")

            if sub:
                new = {"Nom": n, "Prenom": p, "Telephone": t, "Matricule": fd.get("Matricule", ""),
                       "Note": fd.get("Note", ""),
                       "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())}
                if st.session_state.edit_mode: df_c = df_c[df_c.UUID != st.session_state.edit_id]
                df_c = pd.concat([df_c, pd.DataFrame([new])], ignore_index=True)
                save_data("chauf", df_c)
                reset_form();
                st.rerun()

            if dele:
                df_c = df_c[df_c.UUID != st.session_state.edit_id]
                save_data("chauf", df_c)
                reset_form();
                st.rerun()

# =============================================================================
# 4. SYNTHÈSE (CORRIGÉE)
# =============================================================================
elif selected_menu == "Synthèse":
    st.header("📊 Tableau de Bord Financier")
    df_rev = load_data("rev")
    df_dep = load_data("dep")

    # Filtres
    years = sorted(list(set(df_rev["Annee"].astype(str).tolist() + df_dep["Annee"].astype(str).tolist())), reverse=True)
    if not years: years = [str(datetime.now().year)]

    c1, c2 = st.columns(2)
    sel_y = c1.selectbox("Année", years)
    sel_v = c2.selectbox("Regroupement", ["Mois", "Trimestre", "Annuel"])

    # --- CALCULS ---
    df_r = df_rev[df_rev["Annee"].astype(str) == str(sel_y)].copy()
    df_d = df_dep[df_dep["Annee"].astype(str) == str(sel_y)].copy()

    # Taxes implicites
    div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)
    df_r["Ess_TPS"] = ((df_r["Essence"] + df_r["Lavage"]) / div) * (CONFIG["tps"] / 100)
    df_r["Ess_TVQ"] = ((df_r["Essence"] + df_r["Lavage"]) / div) * (CONFIG["tvq"] / 100)

    grp = "Mois" if sel_v == "Mois" else ("Trimestre" if sel_v == "Trimestre" else "Annee")

    # Groupement REVENUS
    syn_r = pd.DataFrame()
    if not df_r.empty:
        syn_r = df_r.groupby(grp)[["Brut", "Salaire", "A_Remettre", "Ess_TPS", "Ess_TVQ"]].sum()

    # Groupement DEPENSES
    syn_d = pd.DataFrame()
    if not df_d.empty:
        if sel_v == "Trimestre":
            df_d["Trimestre"] = "T" + ((pd.to_datetime(df_d["Date"]).dt.month - 1) // 3 + 1).astype(str)
        col_grp_d = "Trimestre" if sel_v == "Trimestre" else ("Mois" if sel_v == "Mois" else "Annee")
        syn_d = df_d.groupby(col_grp_d)[["Total", "TPS", "TVQ"]].sum()

    # Fusion
    final = syn_r.join(syn_d, lsuffix="_r", rsuffix="_d", how="outer").fillna(0)

    final["TPS à Recevoir"] = final.get("Ess_TPS", 0) + final.get("TPS", 0)
    final["TVQ à Recevoir"] = final.get("Ess_TVQ", 0) + final.get("TVQ", 0)
    final["PROFIT NET"] = final.get("A_Remettre", 0) - final.get("Total", 0)

    final = final.rename(columns={"Brut": "Revenu Brut", "Salaire": "Salaire (40%)", "A_Remettre": "Net Perçu",
                                  "Total": "Dépenses Garage"})
    cols = ["Revenu Brut", "Salaire (40%)", "Net Perçu", "Dépenses Garage", "TPS à Recevoir", "TVQ à Recevoir",
            "PROFIT NET"]

    st.subheader(f"Synthèse {sel_y}")
    # On affiche seulement les colonnes qui existent
    cols_present = [c for c in cols if c in final.columns]
    st.dataframe(final[cols_present].style.format("{:.2f} $"), use_container_width=True)

    c1, c2, c3 = st.columns(3)
    if not final.empty:
        c1.metric("TPS à Recevoir", f"{final['TPS à Recevoir'].sum():.2f} $")
        c2.metric("TVQ à Recevoir", f"{final['TVQ à Recevoir'].sum():.2f} $")
        c3.metric("Profit Net", f"{final['PROFIT NET'].sum():.2f} $")

    st.divider()
    st.subheader("Détail Audit Taxes")
    audit = []
    if not df_d.empty:
        for _, r in df_d.iterrows():
            if r.get("TPS", 0) > 0: audit.append(
                {"Date": r["Date"], "Source": r["Categorie"], "TPS": r["TPS"], "TVQ": r["TVQ"], "Total": r["Total"]})
    if not df_r.empty:
        for _, r in df_r.iterrows():
            if r.get("Ess_TPS", 0) > 0: audit.append(
                {"Date": r["Date_Debut"], "Source": "Essence/Lavage", "TPS": r["Ess_TPS"], "TVQ": r["Ess_TVQ"],
                 "Total": r["Essence"] + r["Lavage"]})
    if audit:
        st.dataframe(pd.DataFrame(audit).sort_values("Date", ascending=False).style.format("{:.2f} $"),
                     use_container_width=True)

# =============================================================================
# 5. PARAMETRES
# =============================================================================
elif selected_menu == "Paramètres":
    st.header("⚙️ Configuration")
    with st.form("cfg"):
        c1, c2 = st.columns(2)
        nc = c1.number_input("Coût Appel", value=CONFIG["cout_appel"])
        np = c2.number_input("% Salaire", value=CONFIG["pct_chauf"])
        ni = c1.number_input("% Impôt", value=CONFIG["taux_impot"])
        nt = c1.number_input("% TPS", value=CONFIG["tps"])
        nv = c2.number_input("% TVQ", value=CONFIG["tvq"])
        cats = st.text_area("Catégories", value="\n".join(CONFIG["cats"]))
        if st.form_submit_button("Sauvegarder"):
            save_config({"cout_appel": nc, "pct_chauf": np, "taux_impot": ni, "tps": nt, "tvq": nv,
                         "cats": [x.strip() for x in cats.split('\n') if x.strip()]})
            st.success("Sauvegardé !");
            st.rerun()