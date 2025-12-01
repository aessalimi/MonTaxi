import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import os
import json
import uuid
import re
import pdfplumber
from pypdf import PdfReader
from datetime import datetime, timedelta
from tkcalendar import DateEntry
import sqlalchemy
from sqlalchemy import create_engine, text

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MonTaxi31", page_icon="🚖", layout="wide")

# --- CONNEXION SQL ---
DB_CONNECTION = "mysql+pymysql://root:@localhost/montaxi31_db"
try:
    engine = create_engine(DB_CONNECTION)
    with engine.connect() as conn:
        pass
except Exception as e:
    st.error(f"🚨 Erreur SQL : {e}. Vérifiez XAMPP.")
    st.stop()

# --- CONFIGURATION ---
FILE_CONFIG = "config_taxi.json"
DEFAULT_CONFIG = {
    "cout_appel": 1.05, "pct_chauf": 40.0, "taux_impot": 18.0,
    "tps": 5.0, "tvq": 9.975,
    "categories": ["Réparation mécanique", "Carrosserie", "Pneus", "Assurance", "SAAQ", "Admin", "Pièces", "Autre"]
}


# --- FONCTIONS UTILITAIRES ---
def safe_float(valeur):
    if not valeur: return 0.0
    try:
        return float(str(valeur).replace(',', '.').replace('$', '').replace(' ', '').strip())
    except:
        return 0.0


def charger_config():
    # 1. Chargement par défaut
    config = DEFAULT_CONFIG.copy()
    # 2. Tentative lecture fichier
    if os.path.exists(FILE_CONFIG):
        try:
            with open(FILE_CONFIG, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if "cats" in saved: saved["categories"] = saved.pop("cats")
            config.update(saved)
        except:
            pass

    # 3. Sécurité Clés manquantes (Force l'ajout si tps/tvq absents)
    for k, v in DEFAULT_CONFIG.items():
        if k not in config: config[k] = v

    # 4. Sauvegarde immédiate pour réparer le fichier
    with open(FILE_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)
    return config


def save_config(cfg):
    with open(FILE_CONFIG, 'w', encoding='utf-8') as f: json.dump(cfg, f, indent=4)


CONFIG = charger_config()


def verifier_tables_sql():
    schemas = {
        "taxis": ["Taxi_ID", "Immatriculation", "Chauffeur_Defaut", "UUID"],
        "chauffeurs": ["Nom", "Prenom", "License_ID", "Adresse", "Matricule", "Telephone", "Note", "UUID"],
        "depenses": ["Date", "Mois", "Annee", "Trimestre", "Taxi", "Chauffeur", "Categorie", "Details", "Montant_HT",
                     "TPS", "TVQ", "Montant_Total", "UUID"],
        "revenus": ["Date_Debut", "Date_Fin", "Mois", "Annee", "Trimestre", "Taxi", "Chauffeur",
                    "Meter_Deb", "Meter_Fin", "Meter_Total", "Fixe", "Total_Brut", "Nb_Appels",
                    "Redevance", "Base_Salaire", "Salaire_Chauffeur", "STS", "Credits", "Prix_Fixes",
                    "Visa", "Essence", "Lavage", "Divers", "Impot", "Grand_Total_Remis", "UUID"]
    }
    try:
        with engine.connect() as conn:
            for table, cols in schemas.items():
                try:
                    conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                except:
                    df = pd.DataFrame(columns=cols)
                    dtypes = {c: sqlalchemy.types.Text() for c in cols}
                    df.to_sql(table, engine, if_exists='fail', index=False, dtype=dtypes)
    except:
        pass


def load_data(table):
    try:
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
        if "UUID" not in df.columns: df["UUID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        cols_str = ["Nom", "Prenom", "Taxi", "Chauffeur", "Date_Debut", "Date", "License_ID", "Adresse", "Taxi_ID",
                    "Categorie"]
        for c in cols_str:
            if c in df.columns: df[c] = df[c].astype(str).replace('nan', '').replace('None', '')
        return df
    except:
        return pd.DataFrame()


def save_data(table, df):
    df = df.astype(str)
    df.to_sql(table, engine, if_exists='replace', index=False)


# --- INTELLIGENCE PDF (TRIPLE MOTEUR) ---
def analyser_pdf(uploaded_file):
    data = {}
    debug_log = "--- DIAGNOSTIC LECTURE ---\n"
    full_text = ""

    # 1. SAUVEGARDE TEMP (Contourne bug mémoire)
    with open("temp_scan.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())

    # MOTEUR A : PYPDF (Texte Brut)
    try:
        reader = PdfReader("temp_scan.pdf")
        for page in reader.pages: full_text += (page.extract_text() or "") + "\n"
        if len(full_text.strip()) > 10: debug_log += f"✅ PyPDF : {len(full_text)} chars lus.\n"
    except Exception as e:
        debug_log += f"❌ PyPDF : {e}\n"

    # MOTEUR B : PDFPLUMBER (Texte Layout + Tableaux)
    if len(full_text.strip()) < 10:
        try:
            with pdfplumber.open("temp_scan.pdf") as pdf:
                page = pdf.pages[0]
                full_text = page.extract_text(layout=True) or ""
                # Ajout contenu tableaux
                tables = page.extract_tables()
                for t in tables:
                    for r in t:
                        clean = " ".join([str(c) for c in r if c])
                        full_text += "\n" + clean
            if len(full_text.strip()) > 10: debug_log += f"✅ PDFPlumber : {len(full_text)} chars lus.\n"
        except Exception as e:
            debug_log += f"❌ PDFPlumber : {e}\n"

    # NETTOYAGE
    if os.path.exists("temp_scan.pdf"): os.remove("temp_scan.pdf")

    # DIAGNOSTIC FINAL
    if not full_text.strip():
        return None, debug_log + "\n🚨 RÉSULTAT : FICHIER VIDE OU IMAGE.\nCe PDF est un scan. Le logiciel ne peut pas lire les pixels.\nSolution : Saisissez les montants manuellement."

    # --- EXTRACTION DES DONNÉES ---
    # On remplace les sauts de ligne multiples par un espace pour faciliter la regex
    text_search = re.sub(r'\s+', ' ', full_text)

    def find(keywords):
        if isinstance(keywords, str): keywords = [keywords]
        for k in keywords:
            # Regex : Mot clé ... chiffres
            # On cherche un motif large : Mot clé + jusqu'à 100 caractères + un montant
            pattern = rf"{re.escape(k)}.*?(-?[\d\s]+[.,]\d{{2}})"
            match = re.search(pattern, text_search, re.IGNORECASE)
            if match:
                try:
                    val = float(match.group(1).replace(' ', '').replace(',', '.'))
                    debug_log += f"   [OK] {k} -> {val}\n"
                    return abs(val)
                except:
                    pass
        return 0.0

    data["Meter_Total"] = find(["TOTAL SEMAINE METER", "TOTAL METER", "TOTAL:"])
    data["Fixe"] = find(["MONTANTS FIXES", "MONTANT FIXE"])
    data["STS"] = find(["TOTAUX STS", "STS"])
    data["Credits"] = find(["TOTAUX CREDITS", "CREDITS"])
    data["Prix_Fixes"] = find(["TOTAUX PRIX FIXES", "PRIX FIXES"])
    data["Visa"] = find(["TOTAUX VISE", "TOTAUX VISA", "DEBIT"])
    data["Essence"] = find(["TOTAUX ESSENCE", "ESSENCE"])
    data["Lavage"] = find(["LAVAGE AUTO", "LAVAGE"])
    data["Divers"] = find(["DEPENSES"])
    data["Impot"] = find(["POUR IMPOT", "IMPOT"])

    # Appels (Entier)
    app_money = find(["NOMBRES D'APPELS X", "APPELS X"])
    if app_money > 0:
        data["Nb_Appels"] = int(round(app_money / CONFIG["cout_appel"]))
    else:
        m = re.search(r"NOMBRES D'APPELS.*?(\d+)", text_search, re.IGNORECASE)
        if m:
            data["Nb_Appels"] = int(m.group(1))
        else:
            data["Nb_Appels"] = 0

    # Date & Taxi
    # On cherche les motifs dans le texte brut original (avec sauts de ligne) pour la précision
    mt = re.search(r"NO[:\s]*(\d+)", full_text);
    if mt: data["Taxi"] = mt.group(1)

    mc = re.search(r"CHAUFFEUR[:\s]*(.+)", full_text)
    if mc:
        row = mc.group(1).split("NO:")[0]
        data["Chauffeur_Raw"] = row.strip()

    md = re.search(r"LUNDI[:\s]*(\d{1,2})[\s\n]+([a-zA-Zéû]+)", full_text, re.IGNORECASE)
    if md:
        try:
            d, m_txt = int(md.group(1)), md.group(2).lower()[:3]
            m_map = {"jan": 1, "fev": 2, "fév": 2, "mar": 3, "avr": 4, "mai": 5, "jui": 6, "juil": 7, "aou": 8,
                     "aoû": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12, "déc": 12}
            m_num = 4
            for k, v in m_map.items():
                if k in m_txt: m_num = v
            data["Date_Debut"] = datetime(datetime.now().year, m_num, d)
        except:
            pass

    return data, debug_log


# --- HELPERS ---
def get_liste_chauffeurs():
    return (load_data("chauffeurs")["Nom"] + " " + load_data("chauffeurs")["Prenom"]).tolist()


def get_liste_taxis():
    return sorted(load_data("taxis")["Taxi_ID"].unique().tolist())


def get_default_driver(taxi_id):
    df = load_data("taxis")
    res = df[df["Taxi_ID"].astype(str) == str(taxi_id)]
    if not res.empty: return res.iloc[0]["Chauffeur_Defaut"]
    return None


# --- INIT ---
verifier_tables_sql()

# --- SESSION STATE ---
keys_defaults = {
    "t_m_deb": 0.0, "t_m_fin": 0.0, "t_fixe": 0.0, "t_nb": 0,
    "t_sts": 0.0, "t_crd": 0.0, "t_visa": 0.0, "t_ess": 0.0,
    "t_lav": 0.0, "t_div": 0.0, "t_imp": 0.0, "t_pf": 0.0,
    "t_taxi": "", "t_chauf": ""
}
for k, v in keys_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'edit_id' not in st.session_state: st.session_state.edit_id = None
if 'form_data' not in st.session_state: st.session_state.form_data = {}
if 'form_date' not in st.session_state: st.session_state.form_date = datetime.now()
if 'form_taxi' not in st.session_state: st.session_state.form_taxi = ""
if 'form_chauf' not in st.session_state: st.session_state.form_chauf = ""
if 'debug_log' not in st.session_state: st.session_state.debug_log = ""


def update_session_data(data):
    st.session_state.form_data = data
    if "Date_Debut" in data:
        try:
            st.session_state.form_date = pd.to_datetime(data["Date_Debut"])
        except:
            pass
    if "Taxi" in data: st.session_state.form_taxi = str(data["Taxi"])
    if "Chauffeur" in data: st.session_state.form_chauf = str(data["Chauffeur"])

    if "Meter_Total" in data and data["Meter_Total"] > 0:
        st.session_state["t_m_deb"] = 0.0
        st.session_state["t_m_fin"] = safe_float(data["Meter_Total"])
    else:
        st.session_state["t_m_deb"] = safe_float(data.get("Meter_Deb", 0))
        st.session_state["t_m_fin"] = safe_float(data.get("Meter_Fin", 0))

    st.session_state["t_fixe"] = safe_float(data.get("Fixe", 0))
    st.session_state["t_nb"] = int(data.get("Nb_Appels", 0))
    st.session_state["t_sts"] = safe_float(data.get("STS", 0))
    st.session_state["t_crd"] = safe_float(data.get("Credits", 0))
    st.session_state["t_visa"] = safe_float(data.get("Visa", 0))
    st.session_state["t_ess"] = safe_float(data.get("Essence", 0))
    st.session_state["t_lav"] = safe_float(data.get("Lavage", 0))
    st.session_state["t_div"] = safe_float(data.get("Divers", 0))
    st.session_state["t_pf"] = safe_float(data.get("Prix_Fixes", 0))
    st.session_state["t_imp"] = safe_float(data.get("Impot", 0))

    if "Taxi" in data: st.session_state["t_taxi_wdg"] = str(data["Taxi"])


def reset_form():
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.form_data = {}
    st.session_state.form_date = datetime.now()
    st.session_state.form_taxi = ""
    st.session_state.form_chauf = ""
    st.session_state.debug_log = ""
    for k, v in keys_defaults.items(): st.session_state[k] = v


# --- MENU ---
selected_menu = option_menu(
    menu_title=None,
    options=["Transactions", "Dépenses", "Chauffeurs", "Flotte Taxis", "Synthèse", "Paramètres"],
    icons=["receipt", "wrench", "person-badge", "car-front", "graph-up", "gear"],
    menu_icon="cast", default_index=0, orientation="horizontal",
    styles={"container": {"padding": "0!important", "background-color": "#f0f2f6"},
            "nav-link-selected": {"background-color": "#008CBA"}}
)

# =============================================================================
# 1. TRANSACTIONS
# =============================================================================
if selected_menu == "Transactions":
    st.subheader("📒 Revenus Hebdomadaires")
    df_rev = load_data("revenus")
    l_taxis = [""] + get_liste_taxis()
    l_chauf = [""] + get_liste_chauffeurs()

    col_list, col_form = st.columns([1, 1])

    with col_list:
        st.info("👆 Historique")
        if not df_rev.empty:
            df_v = df_rev.copy()
            df_v["Grand_Total_Remis"] = pd.to_numeric(df_v["Grand_Total_Remis"], errors='coerce')
            df_display = df_v[["Date_Debut", "Taxi", "Chauffeur", "Grand_Total_Remis"]].rename(
                columns={"Grand_Total_Remis": "Net Perçu"}).sort_values("Date_Debut", ascending=False)

            event = st.dataframe(
                df_display, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row",
                column_config={"Net Perçu": st.column_config.NumberColumn(format="%.2f $")}
            )
            if event.selection.rows:
                idx = event.selection.rows[0];
                real_idx = df_display.index[idx];
                row_data = df_rev.loc[real_idx]
                if st.button("Charger la sélection"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = row_data["UUID"]
                    update_session_data(row_data.to_dict())
                    st.rerun()
        if st.button("Nouvelle Saisie (Vider)"): reset_form(); st.rerun()

    with col_form:
        # IMPORT PDF
        with st.expander("📂 IMPORTER PDF", expanded=True):
            uploaded_pdf = st.file_uploader("Glisser fichier ici", type="pdf")
            if uploaded_pdf is not None:
                if st.button("Analyser PDF", type="primary"):
                    data_pdf, debug_log = analyser_pdf(uploaded_pdf)
                    st.session_state.debug_log = debug_log

                    if data_pdf and (data_pdf.get("Meter_Total", 0) > 0 or data_pdf.get("Essence", 0) > 0):
                        if "Chauffeur_Raw" in data_pdf:
                            raw = str(data_pdf.get("Chauffeur_Raw", "")).lower()
                            for c in l_chauf:
                                if c and c.lower() in raw: data_pdf["Chauffeur"] = c; break
                        update_session_data(data_pdf)
                        st.success(f"Données extraites !");
                        st.rerun()
                    else:
                        st.error("Aucune donnée trouvée.")

            if st.session_state.debug_log:
                with st.expander("🔍 DIAGNOSTIC (Texte lu)"):
                    st.text_area("", st.session_state.debug_log, height=200)

        tit = "Modifier" if st.session_state.edit_mode else "Nouveau"
        st.markdown(f"### {tit}")

        with st.form("crud_rev"):
            c1, c2 = st.columns(2)
            d_in = c1.date_input("Date Début", value=st.session_state.form_date)

            val_t = st.session_state.form_taxi
            idx_t = l_taxis.index(str(val_t)) if str(val_t) in l_taxis else 0
            t_in = c2.selectbox("Taxi", l_taxis, index=idx_t, key="t_taxi_wdg")

            val_c = st.session_state.form_chauf
            idx_c = l_chauf.index(val_c) if val_c in l_chauf else 0
            ch_in = c1.selectbox("Chauffeur", l_chauf, index=idx_c, key="t_chauf_wdg")

            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            m_d = c1.number_input("Meter Déb", key="t_m_deb")
            m_f = c2.number_input("Meter Fin", key="t_m_fin")
            fixe = c3.number_input("Fixe", key="t_fixe")
            nb = c4.number_input("Nb Appels", step=1, key="t_nb")

            st.caption("Déductions")
            c1, c2, c3 = st.columns(3)
            sts = c1.number_input("STS", key="t_sts")
            cred = c2.number_input("Crédits", key="t_crd")
            visa = c3.number_input("Visa", key="t_visa")

            c1, c2, c3 = st.columns(3)
            ess = c1.number_input("Essence", key="t_ess")
            lav = c2.number_input("Lavage", key="t_lav")
            div = c3.number_input("Divers", key="t_div")
            c4 = c3.number_input("Prix Fixes (Deduc)", key="t_pf")

            c1, c2 = st.columns(2)
            imp = c1.number_input("Impôt (Manuel)", key="t_imp")

            c_s, c_d = st.columns([2, 1])
            sub = c_s.form_submit_button("Enregistrer", type="primary", use_container_width=True)
            dele = False
            if st.session_state.edit_mode: dele = c_d.form_submit_button("Supprimer", type="secondary")

            if sub:
                val_t_in = st.session_state.t_taxi_wdg
                val_ch_in = st.session_state.t_chauf_wdg

                if not val_t_in or not val_ch_in:
                    st.error("⚠️ Taxi et Chauffeur requis"); sub = False
                else:
                    dup = False
                    if not st.session_state.edit_mode and not df_rev.empty:
                        check = df_rev[(df_rev['Date_Debut'].astype(str) == str(d_in)) & (
                                    df_rev['Taxi'].astype(str) == str(val_t_in))]
                        if not check.empty: st.error("Doublon détecté !"); dup = True

                    if not dup:
                        mt = st.session_state.t_m_fin - st.session_state.t_m_deb
                        brut = mt + st.session_state.t_fixe
                        redev = st.session_state.t_nb * CONFIG["cout_appel"]
                        base = brut - redev
                        sal = base * (CONFIG["pct_chauf"] / 100)
                        imp_fin = st.session_state.t_imp if st.session_state.t_imp > 0 else sal * (
                                    CONFIG["taux_impot"] / 100)
                        ded = st.session_state.t_sts + st.session_state.t_crd + st.session_state.t_visa + st.session_state.t_ess + st.session_state.t_lav + st.session_state.t_div + st.session_state.t_pf
                        net = brut - sal - ded + imp_fin

                        row = {
                            "Date_Debut": d_in, "Date_Fin": d_in + timedelta(days=6), "Mois": d_in.strftime("%Y-%m"),
                            "Annee": str(d_in.year),
                            "Trimestre": f"T{(d_in.month - 1) // 3 + 1}", "Taxi": val_t_in, "Chauffeur": val_ch_in,
                            "Meter_Deb": st.session_state.t_m_deb, "Meter_Fin": st.session_state.t_m_fin,
                            "Meter_Total": mt,
                            "Fixe": st.session_state.t_fixe, "Total_Brut": brut, "Nb_Appels": st.session_state.t_nb,
                            "Redevance": redev, "Base_Salaire": base, "Salaire_Chauffeur": round(sal, 2),
                            "STS": st.session_state.t_sts, "Credits": st.session_state.t_crd,
                            "Prix_Fixes": st.session_state.t_pf, "Visa": st.session_state.t_visa,
                            "Essence": st.session_state.t_ess, "Lavage": st.session_state.t_lav,
                            "Divers": st.session_state.t_div,
                            "Impot": round(imp_fin, 2), "Grand_Total_Remis": round(net, 2),
                            "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())
                        }

                        if st.session_state.edit_mode: df_rev = df_rev[df_rev.UUID != st.session_state.edit_id]
                        df_rev = pd.concat([df_rev, pd.DataFrame([row])], ignore_index=True)
                        save_data("revenus", df_rev);
                        st.success(f"Enregistré ! Net: {net:.2f} $");
                        reset_form();
                        st.rerun()

            if dele:
                df_rev = df_rev[df_rev.UUID != st.session_state.edit_id]
                save_data("revenus", df_rev);
                st.warning("Supprimé");
                reset_form();
                st.rerun()

# =============================================================================
# 2. DEPENSES
# =============================================================================
elif selected_menu == "Dépenses":
    st.subheader("🔧 Dépenses Garage")
    df_dep = load_data("depenses");
    l_taxis = [""] + get_liste_taxis();
    l_chauf = [""] + get_liste_chauffeurs()

    if 'd_date' not in st.session_state: st.session_state.d_date = datetime.now()
    if 'd_taxi' not in st.session_state: st.session_state.d_taxi = ""
    if 'd_chauf' not in st.session_state: st.session_state.d_chauf = ""
    if 'd_cat' not in st.session_state: st.session_state.d_cat = CONFIG["categories"][0]
    if 'd_tot' not in st.session_state: st.session_state.d_tot = 0.0
    if 'd_det' not in st.session_state: st.session_state.d_det = ""


    def reset_dep():
        st.session_state.edit_mode = False;
        st.session_state.edit_id = None
        st.session_state.d_date = datetime.now();
        st.session_state.d_taxi = "";
        st.session_state.d_chauf = ""
        st.session_state.d_tot = 0.0;
        st.session_state.d_det = ""


    col_list, col_form = st.columns([1, 1])
    with col_list:
        st.info("Historique")
        if not df_dep.empty:
            df_v = df_dep.copy();
            df_v["Montant_Total"] = pd.to_numeric(df_v["Montant_Total"], errors='coerce')
            df_show = df_v[["Date", "Taxi", "Categorie", "Montant_Total"]].sort_values("Date", ascending=False)
            evt = st.dataframe(df_show, use_container_width=True, hide_index=True, on_select="rerun",
                               selection_mode="single-row",
                               column_config={"Montant_Total": st.column_config.NumberColumn(format="%.2f $")})
            if evt.selection.rows:
                idx = evt.selection.rows[0];
                rid = df_show.index[idx];
                r = df_dep.loc[rid]
                if st.button("Charger"):
                    st.session_state.edit_mode = True;
                    st.session_state.edit_id = r["UUID"]
                    try:
                        st.session_state.d_date = pd.to_datetime(r["Date"])
                    except:
                        pass
                    st.session_state.d_taxi = r["Taxi"];
                    st.session_state.d_chauf = r["Chauffeur"]
                    st.session_state.d_cat = r["Categorie"];
                    st.session_state.d_tot = safe_float(r["Montant_Total"])
                    st.session_state.d_det = r["Details"];
                    st.rerun()
        if st.button("Nouveau"): reset_dep(); st.rerun()

    with col_form:
        tit = "Modifier" if st.session_state.edit_mode else "Ajouter";
        st.markdown(f"**{tit}**")
        with st.form("crud_dep"):
            c1, c2 = st.columns(2)
            d1 = c1.date_input("Date", value=st.session_state.d_date)
            t_val = st.session_state.d_taxi;
            idx_t = l_taxis.index(str(t_val)) if str(t_val) in l_taxis else 0;
            t1 = c2.selectbox("Taxi", l_taxis, index=idx_t)
            c_val = st.session_state.d_chauf;
            idx_c = l_chauf.index(c_val) if c_val in l_chauf else 0;
            ch1 = c1.selectbox("Chauffeur", l_chauf, index=idx_c)
            cat_idx = 0
            if st.session_state.d_cat in CONFIG["categories"]: cat_idx = CONFIG["categories"].index(
                st.session_state.d_cat)
            cat1 = c2.selectbox("Catégorie", CONFIG["categories"], index=cat_idx)
            c1, c2 = st.columns(2);
            tot1 = c1.number_input("Total ($)", value=float(st.session_state.d_tot));
            tax = c2.checkbox("Taxes incluses ?");
            det1 = st.text_input("Détails", value=st.session_state.d_det)
            c_s, c_d = st.columns([2, 1]);
            sub = c_s.form_submit_button("Enregistrer", type="primary", use_container_width=True);
            dele = False
            if st.session_state.edit_mode: dele = c_d.form_submit_button("Supprimer", type="secondary")
            if sub:
                if not t1:
                    st.error("Taxi requis")
                else:
                    if tax:
                        div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100); ht = tot1 / div; tps = ht * (
                                    CONFIG["tps"] / 100); tvq = ht * (CONFIG["tvq"] / 100)
                    else:
                        ht, tps, tvq = tot1, 0.0, 0.0
                    row = {"Date": d1, "Mois": d1.strftime("%Y-%m"), "Annee": str(d1.year),
                           "Trimestre": f"T{(d1.month - 1) // 3 + 1}", "Taxi": t1, "Chauffeur": ch1, "Categorie": cat1,
                           "Details": det1, "Montant_HT": round(ht, 2), "TPS": round(tps, 2), "TVQ": round(tvq, 2),
                           "Montant_Total": tot1,
                           "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())}
                    if st.session_state.edit_mode: df_dep = df_dep[df_dep.UUID != st.session_state.edit_id]
                    df_dep = pd.concat([df_dep, pd.DataFrame([row])], ignore_index=True);
                    save_data("depenses", df_dep);
                    st.success("OK");
                    reset_dep();
                    st.rerun()
            if dele: df_dep = df_dep[df_dep.UUID != st.session_state.edit_id]; save_data("depenses",
                                                                                         df_dep); st.warning(
                "Supprimé"); reset_dep(); st.rerun()

# =============================================================================
# 3. CHAUFFEURS
# =============================================================================
elif selected_menu == "Chauffeurs":
    st.subheader("👨‍✈️ Gestion Chauffeurs")
    df_c = load_data("chauffeurs");
    col_list, col_form = st.columns([1, 1])
    for k in ["c_n", "c_p", "c_l", "c_a", "c_t", "c_m", "c_nt"]:
        if k not in st.session_state: st.session_state[k] = ""


    def reset_c():
        st.session_state.edit_mode = False;
        st.session_state.edit_id = None
        for k in ["c_n", "c_p", "c_l", "c_a", "c_t", "c_m", "c_nt"]: st.session_state[k] = ""


    with col_list:
        if not df_c.empty:
            evt = st.dataframe(df_c[["Nom", "Prenom", "License_ID"]], on_select="rerun", selection_mode="single-row",
                               use_container_width=True, hide_index=True)
            if evt.selection.rows:
                idx = evt.selection.rows[0];
                rid = df_c.index[idx];
                r = df_c.loc[rid]
                if st.button("Modifier"):
                    st.session_state.edit_mode = True;
                    st.session_state.edit_id = r["UUID"]
                    st.session_state.c_n = r["Nom"];
                    st.session_state.c_p = r["Prenom"];
                    st.session_state.c_l = r["License_ID"]
                    st.session_state.c_a = r["Adresse"];
                    st.session_state.c_t = r["Telephone"];
                    st.session_state.c_m = r["Matricule"];
                    st.session_state.c_nt = r["Note"]
                    st.rerun()
        if st.button("Nouveau"): reset_c(); st.rerun()
    with col_form:
        with st.form("crud_chauf"):
            n = st.text_input("Nom", value=st.session_state.c_n);
            p = st.text_input("Prénom", value=st.session_state.c_p);
            l = st.text_input("License", value=st.session_state.c_l)
            a = st.text_input("Adresse", value=st.session_state.c_a);
            t = st.text_input("Tel", value=st.session_state.c_t);
            m = st.text_input("Matricule", value=st.session_state.c_m);
            nt = st.text_area("Note", value=st.session_state.c_nt)
            c1, c2 = st.columns(2);
            sub = c1.form_submit_button("Enregistrer", type="primary");
            dele = False
            if st.session_state.edit_mode: dele = c2.form_submit_button("Supprimer")
            if sub and n:
                new = {"Nom": n, "Prenom": p, "License_ID": l, "Adresse": a, "Telephone": t, "Matricule": m, "Note": nt,
                       "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())}
                if st.session_state.edit_mode: df_c = df_c[df_c.UUID != st.session_state.edit_id]
                df_c = pd.concat([df_c, pd.DataFrame([new])], ignore_index=True);
                save_data("chauffeurs", df_c);
                st.success("OK");
                reset_c();
                st.rerun()
            if dele: df_c = df_c[df_c.UUID != st.session_state.edit_id]; save_data("chauffeurs", df_c); st.warning(
                "Supprimé"); reset_c(); st.rerun()

# =============================================================================
# 4. FLOTTE TAXIS
# =============================================================================
elif selected_menu == "Flotte Taxis":
    st.subheader("🚖 Gestion de la Flotte")
    df_t = load_data("taxis");
    l_chauf = [""] + get_liste_chauffeurs();
    col_list, col_form = st.columns([1, 1])
    if 't_id' not in st.session_state: st.session_state.t_id = ""
    if 't_im' not in st.session_state: st.session_state.t_im = ""
    if 't_cd' not in st.session_state: st.session_state.t_cd = ""


    def reset_t():
        st.session_state.edit_mode = False;
        st.session_state.edit_id = None;
        st.session_state.t_id = "";
        st.session_state.t_im = "";
        st.session_state.t_cd = ""


    with col_list:
        if not df_t.empty:
            event = st.dataframe(df_t[["Taxi_ID", "Chauffeur_Defaut"]], on_select="rerun", selection_mode="single-row",
                                 use_container_width=True, hide_index=True)
            if event.selection.rows:
                idx = event.selection.rows[0];
                real_idx = df_t.index[idx];
                r = df_t.loc[real_idx]
                if st.button("Modifier"):
                    st.session_state.edit_mode = True;
                    st.session_state.edit_id = r["UUID"]
                    st.session_state.t_id = r["Taxi_ID"];
                    st.session_state.t_im = r["Immatriculation"];
                    st.session_state.t_cd = r["Chauffeur_Defaut"]
                    st.rerun()
        if st.button("Ajouter"): reset_t(); st.rerun()
    with col_form:
        with st.form("crud_taxi"):
            tid = st.text_input("Numéro Taxi", value=st.session_state.t_id);
            imm = st.text_input("Immatriculation", value=st.session_state.t_im);
            idx_def = l_chauf.index(st.session_state.t_cd) if st.session_state.t_cd in l_chauf else 0;
            cd = st.selectbox("Chauffeur Défaut", l_chauf, index=idx_def)
            c1, c2 = st.columns(2);
            sub = c1.form_submit_button("Enregistrer", type="primary");
            dele = False
            if st.session_state.edit_mode: dele = c2.form_submit_button("Supprimer")
            if sub and tid:
                new = {"Taxi_ID": tid, "Immatriculation": imm, "Chauffeur_Defaut": cd,
                       "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())}
                if st.session_state.edit_mode: df_t = df_t[df_t.UUID != st.session_state.edit_id]
                df_t = pd.concat([df_t, pd.DataFrame([new])], ignore_index=True);
                save_data("taxis", df_t);
                st.success("OK");
                reset_t();
                st.rerun()
            if dele: df_t = df_t[df_t.UUID != st.session_state.edit_id]; save_data("taxis", df_t); st.warning(
                "Supprimé"); reset_t(); st.rerun()

# =============================================================================
# 5. SYNTHÈSE
# =============================================================================
elif selected_menu == "Synthèse":
    st.header("📊 Tableau de Bord")
    df_rev = load_data("revenus");
    df_dep = load_data("depenses")
    years = sorted(list(set(df_rev["Annee"].astype(str).tolist() + df_dep["Annee"].astype(str).tolist())), reverse=True)
    if not years: years = [str(datetime.now().year)]
    c1, c2 = st.columns(2);
    sel_y = c1.selectbox("Année", years);
    sel_v = c2.selectbox("Vue", ["Mois", "Trimestre", "Annuel"])

    df_r = df_rev[df_rev["Annee"].astype(str) == str(sel_y)].copy()
    for c in ["Salaire_Chauffeur", "Grand_Total_Remis", "Total_Brut", "Essence", "Lavage"]:
        if c in df_r.columns: df_r[c] = pd.to_numeric(df_r[c], errors='coerce').fillna(0)

    div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)
    df_r["Ess_TPS"] = ((df_r["Essence"] + df_r["Lavage"]) / div) * (CONFIG["tps"] / 100);
    df_r["Ess_TVQ"] = ((df_r["Essence"] + df_r["Lavage"]) / div) * (CONFIG["tvq"] / 100)
    grp = "Mois" if sel_v == "Mois" else ("Trimestre" if sel_v == "Trimestre" else "Annee")
    syn_r = df_r.groupby(grp)[["Total_Brut", "Salaire_Chauffeur", "Grand_Total_Remis", "Ess_TPS", "Ess_TVQ"]].sum()

    df_d = df_dep[df_dep["Annee"].astype(str) == str(sel_y)].copy()
    if sel_v == "Trimestre": df_d["Trimestre"] = "T" + ((pd.to_datetime(df_d["Date"]).dt.month - 1) // 3 + 1).astype(
        str)
    grp_d = "Mois" if sel_v == "Mois" else ("Trimestre" if sel_v == "Trimestre" else "Annee")
    for c in ["Montant_Total", "TPS", "TVQ"]:
        if c in df_d.columns: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').fillna(0)
    syn_d = df_d.groupby(grp_d)[["Montant_Total", "TPS", "TVQ"]].sum()

    final = syn_r.join(syn_d, lsuffix="_r", rsuffix="_d", how="outer").fillna(0)
    final["TPS à Recevoir"] = final.get("Ess_TPS", 0) + final.get("TPS", 0);
    final["TVQ à Recevoir"] = final.get("Ess_TVQ", 0) + final.get("TVQ", 0)
    final["PROFIT NET"] = final.get("Grand_Total_Remis", 0) - final.get("Montant_Total", 0)
    final = final.rename(
        columns={"Total_Brut": "Revenu BRUT", "Salaire_Chauffeur": "Salaire (40%)", "Grand_Total_Remis": "Net Perçu",
                 "Montant_Total": "Dépenses Garage"})

    k1, k2, k3 = st.columns(3);
    k1.metric("Revenu BRUT", f"{final['Revenu BRUT'].sum():.2f} $");
    k2.metric("Salaires", f"{final['Salaire (40%)'].sum():.2f} $");
    k3.metric("PROFIT NET", f"{final['PROFIT NET'].sum():.2f} $")
    k4, k5 = st.columns(2);
    k4.metric("Total TPS", f"{final['TPS à Recevoir'].sum():.2f} $");
    k5.metric("Total TVQ", f"{final['TVQ à Recevoir'].sum():.2f} $")
    st.divider()

    cols_m = ["Revenu BRUT", "Salaire (40%)", "Net Perçu", "Dépenses Garage", "TPS à Recevoir", "TVQ à Recevoir",
              "PROFIT NET"]
    cfg = {c: st.column_config.NumberColumn(format="%.2f $") for c in cols_m}
    st.dataframe(final[cols_m], column_config=cfg, use_container_width=True)

    st.divider();
    st.caption("Détail Taxes")
    aud = []
    for _, r in df_d.iterrows():
        if r.get("TPS", 0) > 0: aud.append(
            {"Date": r["Date"], "Type": "Dépense", "TPS": r["TPS"], "TVQ": r["TVQ"], "Total": r["Montant_Total"]})
    for _, r in df_r.iterrows():
        if r.get("Ess_TPS", 0) > 0: aud.append(
            {"Date": r["Date_Debut"], "Type": "Essence", "TPS": r["Ess_TPS"], "TVQ": r["Ess_TVQ"],
             "Total": r["Essence"] + r["Lavage"]})
    if aud: st.dataframe(pd.DataFrame(aud).sort_values("Date", ascending=False), use_container_width=True)

# =============================================================================
# 6. PARAMETRES
# =============================================================================
elif selected_menu == "Paramètres":
    st.header("⚙️ Configuration")
    with st.form("cfg"):
        c1, c2 = st.columns(2);
        nc = c1.number_input("Coût Appel", value=CONFIG["cout_appel"]);
        np = c2.number_input("% Salaire", value=CONFIG["pct_chauf"]);
        ni = c1.number_input("% Impôt", value=CONFIG["taux_impot"]);
        nt = c1.number_input("% TPS", value=CONFIG["tps"]);
        nv = c2.number_input("% TVQ", value=CONFIG["tvq"]);
        cat = st.text_area("Catégories", value="\n".join(CONFIG["categories"]))
        if st.form_submit_button("Sauvegarder"):
            save_config({"cout_appel": nc, "pct_chauf": np, "taux_impot": ni, "tps": nt, "tvq": nv,
                         "categories": [x.strip() for x in cat.split('\n') if x.strip()]});
            st.success("OK");
            st.rerun()

verifier_tables_sql()