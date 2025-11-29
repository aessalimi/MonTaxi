import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import os
import json
import uuid
from datetime import datetime, timedelta
from tkcalendar import DateEntry

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MonTaxi31", page_icon="🚖", layout="wide")

# --- FICHIERS ---
FILES = {
    "dep": "depenses_flotte.csv",
    "chauf": "chauffeurs.csv",
    "taxis": "taxis.csv",
    "rev": "revenus_hebdo.csv",
    "conf": "config_taxi.json"
}

BG_JAUNE = "#FFFFE0"

# CONFIGURATION PAR DÉFAUT (Noms de variables corrigés)
DEFAULT_CONFIG = {
    "cout_appel": 1.05,
    "pct_chauf": 40.0,
    "taux_impot": 18.0,
    "tps": 5.0,  # Corrigé (était taux_tps)
    "tvq": 9.975,  # Corrigé (était taux_tvq)
    "categories": ["Réparation mécanique", "Carrosserie", "Pneus", "Assurance", "SAAQ", "Admin", "Pièces", "Autre"]
}


# --- GESTION PARAMÈTRES (RÉPARATION AUTOMATIQUE) ---
def charger_config():
    config = DEFAULT_CONFIG.copy()
    file_changed = False

    if os.path.exists(FILES["conf"]):
        try:
            with open(FILES["conf"], 'r', encoding='utf-8') as f:
                saved = json.load(f)

            # Migration des anciens noms de clés si nécessaire
            if "taux_tps" in saved: saved["tps"] = saved.pop("taux_tps"); file_changed = True
            if "taux_tvq" in saved: saved["tvq"] = saved.pop("taux_tvq"); file_changed = True
            if "cats" in saved: saved["categories"] = saved.pop("cats"); file_changed = True

            config.update(saved)
        except:
            pass

    # Vérification que toutes les clés existent, sinon on les ajoute
    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v
            file_changed = True

    # Sauvegarde immédiate si réparation effectuée
    if file_changed:
        with open(FILES["conf"], 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

    return config


def save_config(cfg):
    with open(FILES["conf"], 'w', encoding='utf-8') as f: json.dump(cfg, f, indent=4)


CONFIG = charger_config()


# --- UTILITAIRES ---
def safe_float(valeur):
    if not valeur: return 0.0
    try:
        return float(str(valeur).replace(',', '.').replace('$', '').replace(' ', ''))
    except:
        return 0.0


def verifier_fichiers():
    # Définitions des colonnes
    cols_schema = {
        "dep": ["Date", "Mois", "Annee", "Trimestre", "Taxi", "Chauffeur", "Categorie", "Details", "HT", "TPS", "TVQ",
                "Montant_Total", "UUID"],
        "chauf": ["Nom", "Prenom", "License_ID", "Adresse", "Matricule", "Telephone", "Note", "UUID"],
        "taxis": ["Taxi_ID", "Immatriculation", "Chauffeur_Defaut", "UUID"],
        "rev": ["Date_Debut", "Date_Fin", "Mois", "Annee", "Trimestre", "Taxi", "Chauffeur",
                "Meter_Deb", "Meter_Fin", "Meter_Total", "Fixe", "Total_Brut", "Nb_Appels",
                "Redevance", "Base_Salaire", "Salaire_Chauffeur", "STS", "Credits", "Prix_Fixes",
                "Visa", "Essence", "Lavage", "Divers", "Impot", "Grand_Total_Remis", "UUID"]
    }

    for key, cols in cols_schema.items():
        if not os.path.exists(FILES[key]):
            pd.DataFrame(columns=cols).to_csv(FILES[key], index=False)
        else:
            try:
                df = pd.read_csv(FILES[key])
                changed = False
                for c in cols:
                    if c not in df.columns:
                        df[c] = "" if c != "UUID" else [str(uuid.uuid4()) for _ in range(len(df))]
                        changed = True
                if changed: df.to_csv(FILES[key], index=False)
            except:
                pass


def load_data(key):
    try:
        df = pd.read_csv(FILES[key])
        if "UUID" not in df.columns:
            df["UUID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        cols_txt = ["Nom", "Prenom", "Taxi", "Chauffeur", "Date_Debut", "Date", "License_ID", "Adresse", "Taxi_ID",
                    "Categorie"]
        for c in cols_txt:
            if c in df.columns: df[c] = df[c].astype(str).replace('nan', '')
        return df
    except:
        return pd.DataFrame()


def save_data(key, df):
    df.to_csv(FILES[key], index=False)


def get_liste_chauffeurs():
    df = load_data("chauf")
    return (df["Nom"] + " " + df["Prenom"]).tolist() if not df.empty else []


def get_liste_taxis():
    df = load_data("taxis")
    return sorted(df["Taxi_ID"].unique().tolist()) if not df.empty else []


def get_annees_disponibles():
    years = set();
    years.add(datetime.now().strftime("%Y"))
    if os.path.exists(FILES["rev"]):
        for r in csv.DictReader(open(FILES["rev"])):
            if r['Annee']: years.add(r['Annee'])
    return sorted(list(years), reverse=True)


# --- SESSION STATE ---
if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
if 'edit_id' not in st.session_state: st.session_state.edit_id = None
if 'form_data' not in st.session_state: st.session_state.form_data = {}


def reset_form():
    st.session_state.edit_mode = False
    st.session_state.edit_id = None
    st.session_state.form_data = {}


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
    df_rev = load_data("rev")

    l_taxis = [""] + get_liste_taxis()
    l_chauf = [""] + get_liste_chauffeurs()

    col_list, col_form = st.columns([1, 1])

    # LISTE
    with col_list:
        st.info("👆 Historique (Sélectionnez pour modifier)")
        if not df_rev.empty:
            df_display = df_rev[["Date_Debut", "Taxi", "Chauffeur", "Grand_Total_Remis"]].rename(
                columns={"Grand_Total_Remis": "Net Perçu"}).sort_values("Date_Debut", ascending=False)

            event = st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={"Net Perçu": st.column_config.NumberColumn(format="%.2f $")}
            )

            if event.selection.rows:
                idx = event.selection.rows[0]
                real_idx = df_display.index[idx]
                row_data = df_rev.loc[real_idx]
                if st.button("Charger la sélection"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = row_data["UUID"]
                    st.session_state.form_data = row_data.to_dict()
                    st.rerun()
        if st.button("Nouvelle Saisie (Vider)"): reset_form(); st.rerun()

    # FORMULAIRE
    with col_form:
        f_title = f"✏️ Modifier" if st.session_state.edit_mode else "➕ Nouvelle Transaction"
        st.markdown(f"**{f_title}**")
        fd = st.session_state.form_data

        with st.form("crud_trans"):
            c1, c2 = st.columns(2)
            try:
                d_val = pd.to_datetime(fd.get("Date_Debut", datetime.now()))
            except:
                d_val = datetime.now()
            d_in = c1.date_input("Date Début", value=d_val)

            val_taxi = fd.get("Taxi", "")
            idx_t = l_taxis.index(val_taxi) if val_taxi in l_taxis else 0
            t_in = c2.selectbox("Taxi", l_taxis, index=idx_t)

            val_chauf = fd.get("Chauffeur", "")
            idx_c = l_chauf.index(val_chauf) if val_chauf in l_chauf else 0
            ch_in = c1.selectbox("Chauffeur", l_chauf, index=idx_c)

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

            c_s, c_d = st.columns([2, 1])
            sub = c_s.form_submit_button("Enregistrer/Modifier", type="primary", use_container_width=True)
            dele = False
            if st.session_state.edit_mode: dele = c_d.form_submit_button("Supprimer", type="secondary",
                                                                         use_container_width=True)

            if sub:
                if t_in == "":
                    st.error("⚠️ Taxi requis"); sub = False
                elif ch_in == "":
                    st.error("⚠️ Chauffeur requis"); sub = False

                if sub:
                    is_dup = False
                    if not st.session_state.edit_mode and not df_rev.empty:
                        check = df_rev[
                            (df_rev['Date_Debut'].astype(str) == str(d_in)) & (df_rev['Taxi'].astype(str) == str(t_in))]
                        if not check.empty: st.error("⛔ Doublon détecté (Date + Taxi) !"); is_dup = True

                    if not is_dup:
                        mt = m_f - m_d;
                        brut = mt + fixe
                        redev = nb * CONFIG["cout_appel"]
                        base = brut - redev
                        sal = base * (CONFIG["pct_chauf"] / 100)
                        imp = sal * (CONFIG["taux_impot"] / 100)
                        deducs = sts + cred + visa + ess + lav + div + float(fd.get("Prix_Fixes", 0.0))
                        net = brut - sal - deducs + imp

                        row = {
                            "Date_Debut": d_in, "Date_Fin": d_in + timedelta(days=6), "Mois": d_in.strftime("%Y-%m"),
                            "Annee": str(d_in.year),
                            "Trimestre": f"T{(d_in.month - 1) // 3 + 1}", "Taxi": t_in, "Chauffeur": ch_in,
                            "Meter_Deb": m_d, "Meter_Fin": m_f, "Meter_Total": mt, "Fixe": fixe, "Total_Brut": brut,
                            "Nb_Appels": nb,
                            "Redevance": redev, "Base_Salaire": base, "Salaire_Chauffeur": round(sal, 2),
                            "STS": sts, "Credits": cred, "Prix_Fixes": float(fd.get("Prix_Fixes", 0.0)), "Visa": visa,
                            "Essence": ess, "Lavage": lav, "Divers": div, "Impot": round(imp, 2),
                            "Grand_Total_Remis": round(net, 2),
                            "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())
                        }
                        if st.session_state.edit_mode: df_rev = df_rev[df_rev.UUID != st.session_state.edit_id]
                        df_rev = pd.concat([df_rev, pd.DataFrame([row])], ignore_index=True)
                        save_data("rev", df_rev);
                        st.success("Enregistré");
                        reset_form();
                        st.rerun()

            if dele:
                df_rev = df_rev[df_rev.UUID != st.session_state.edit_id]
                save_data("rev", df_rev);
                st.warning("Supprimé");
                reset_form();
                st.rerun()

# =============================================================================
# 2. DEPENSES
# =============================================================================
elif selected_menu == "Dépenses":
    st.subheader("🔧 Dépenses Garage")
    df_dep = load_data("dep");
    l_taxis = [""] + get_liste_taxis();
    l_chauf = [""] + get_liste_chauffeurs()

    col_list, col_form = st.columns([1, 1])
    with col_list:
        st.info("Sélectionnez pour modifier")
        if not df_dep.empty:
            df_show = df_dep[["Date", "Taxi", "Categorie", "Montant_Total"]].sort_values("Date", ascending=False)
            event = st.dataframe(
                df_show,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={"Montant_Total": st.column_config.NumberColumn(format="%.2f $")}
            )
            if event.selection.rows:
                idx = event.selection.rows[0];
                real_idx = df_show.index[idx];
                row_data = df_dep.loc[real_idx]
                if st.button("Charger Dépense"):
                    st.session_state.edit_mode = True;
                    st.session_state.edit_id = row_data["UUID"];
                    st.session_state.form_data = row_data.to_dict();
                    st.rerun()
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

            t_val = fd.get("Taxi", "");
            t_idx = l_taxis.index(t_val) if t_val in l_taxis else 0
            d_taxi = c2.selectbox("Taxi", l_taxis, index=t_idx)

            c_val = fd.get("Chauffeur", "");
            c_idx = l_chauf.index(c_val) if c_val in l_chauf else 0
            d_chauf = c1.selectbox("Chauffeur", l_chauf, index=c_idx)

            cat_idx = 0
            if fd.get("Categorie") in CONFIG["categories"]: cat_idx = CONFIG["categories"].index(fd.get("Categorie"))
            d_cat = c2.selectbox("Catégorie", CONFIG["categories"], index=cat_idx)

            c1, c2 = st.columns(2)
            mt_val = float(fd.get("Montant_Total", 0.0)) if "Montant_Total" in fd else float(fd.get("Total", 0.0))
            d_tot = c1.number_input("Total ($)", value=mt_val)
            tax_in = c2.checkbox("Taxes Incluses?", value=(float(fd.get("TPS", 0.0)) > 0))
            d_det = st.text_input("Détails", value=fd.get("Details", ""))

            c_s, c_d = st.columns([2, 1])
            sub = c_s.form_submit_button("Sauvegarder", type="primary", use_container_width=True)
            dele = False;
            if st.session_state.edit_mode: dele = c_d.form_submit_button("Supprimer", type="secondary")

            if sub:
                if d_taxi == "": st.error("Taxi requis"); sub = False
                if sub:
                    if tax_in:
                        div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)
                        ht = d_tot / div;
                        tps = ht * (CONFIG["tps"] / 100);
                        tvq = ht * (CONFIG["tvq"] / 100)
                    else:
                        ht, tps, tvq = d_tot, 0.0, 0.0

                    row = {"Date": d_date, "Mois": d_date.strftime("%Y-%m"), "Annee": str(d_date.year),
                           "Trimestre": f"T{(d_date.month - 1) // 3 + 1}",
                           "Taxi": d_taxi, "Chauffeur": d_chauf, "Categorie": d_cat, "Details": d_det,
                           "Montant_HT": round(ht, 2), "TPS": round(tps, 2), "TVQ": round(tvq, 2),
                           "Montant_Total": d_tot,
                           "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())}

                    if st.session_state.edit_mode: df_dep = df_dep[df_dep.UUID != st.session_state.edit_id]
                    df_dep = pd.concat([df_dep, pd.DataFrame([row])], ignore_index=True)
                    save_data("dep", df_dep);
                    st.success("Sauvegardé");
                    reset_form();
                    st.rerun()
            if dele:
                df_dep = df_dep[df_dep.UUID != st.session_state.edit_id]
                save_data("dep", df_dep);
                st.warning("Supprimé");
                reset_form();
                st.rerun()

# =============================================================================
# 3. CHAUFFEURS
# =============================================================================
elif selected_menu == "Chauffeurs":
    st.subheader("👨‍✈️ Gestion Chauffeurs")
    df_c = load_data("chauf")
    col_list, col_form = st.columns([1, 1])
    with col_list:
        if not df_c.empty:
            event = st.dataframe(df_c[["Nom", "Prenom", "License_ID"]], on_select="rerun", selection_mode="single-row",
                                 use_container_width=True, hide_index=True)
            if event.selection.rows:
                idx = event.selection.rows[0];
                real_idx = df_c.index[idx];
                row_data = df_c.loc[real_idx]
                if st.button("Modifier"):
                    st.session_state.edit_mode = True;
                    st.session_state.edit_id = row_data["UUID"];
                    st.session_state.form_data = row_data.to_dict();
                    st.rerun()
        if st.button("Nouveau"): reset_form(); st.rerun()

    with col_form:
        fd = st.session_state.form_data
        with st.form("crud_chauf"):
            n = st.text_input("Nom", value=fd.get("Nom", ""))
            p = st.text_input("Prénom", value=fd.get("Prenom", ""))
            l = st.text_input("License ID (Pocket)", value=fd.get("License_ID", ""))
            a = st.text_input("Adresse", value=fd.get("Adresse", ""))
            t = st.text_input("Téléphone", value=fd.get("Telephone", ""))
            m = st.text_input("Matricule", value=fd.get("Matricule", ""))
            nt = st.text_area("Note", value=fd.get("Note", ""))

            c1, c2 = st.columns(2)
            sub = c1.form_submit_button("Sauvegarder", type="primary")
            dele = False
            if st.session_state.edit_mode: dele = c2.form_submit_button("Supprimer")

            if sub and n:
                new = {"Nom": n, "Prenom": p, "License_ID": l, "Adresse": a, "Telephone": t, "Matricule": m, "Note": nt,
                       "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())}
                if st.session_state.edit_mode: df_c = df_c[df_c.UUID != st.session_state.edit_id]
                df_c = pd.concat([df_c, pd.DataFrame([new])], ignore_index=True)
                save_data("chauf", df_c);
                st.success("Enregistré");
                reset_form();
                st.rerun()
            if dele:
                df_c = df_c[df_c.UUID != st.session_state.edit_id]
                save_data("chauf", df_c);
                st.warning("Supprimé");
                reset_form();
                st.rerun()

# =============================================================================
# 4. FLOTTE TAXIS
# =============================================================================
elif selected_menu == "Flotte Taxis":
    st.subheader("🚖 Gestion de la Flotte")
    df_t = load_data("taxis")
    l_chauf = [""] + get_liste_chauffeurs()

    col_list, col_form = st.columns([1, 1])
    with col_list:
        if not df_t.empty:
            event = st.dataframe(df_t[["Taxi_ID", "Chauffeur_Defaut"]], on_select="rerun", selection_mode="single-row",
                                 use_container_width=True, hide_index=True)
            if event.selection.rows:
                idx = event.selection.rows[0];
                real_idx = df_t.index[idx];
                row_data = df_t.loc[real_idx]
                if st.button("Modifier Taxi"):
                    st.session_state.edit_mode = True;
                    st.session_state.edit_id = row_data["UUID"];
                    st.session_state.form_data = row_data.to_dict();
                    st.rerun()
        if st.button("Ajouter Taxi"): reset_form(); st.rerun()

    with col_form:
        fd = st.session_state.form_data
        with st.form("crud_taxi"):
            tid = st.text_input("Numéro Taxi (ex: 101)", value=fd.get("Taxi_ID", ""))
            imm = st.text_input("Immatriculation", value=fd.get("Immatriculation", ""))

            c_def_val = fd.get("Chauffeur_Defaut", "")
            idx_def = l_chauf.index(c_def_val) if c_def_val in l_chauf else 0
            c_def = st.selectbox("Chauffeur par Défaut (Optionnel)", l_chauf, index=idx_def)

            c1, c2 = st.columns(2)
            sub = c1.form_submit_button("Sauvegarder", type="primary")
            dele = False
            if st.session_state.edit_mode: dele = c2.form_submit_button("Supprimer")

            if sub and tid:
                new = {"Taxi_ID": tid, "Immatriculation": imm, "Chauffeur_Defaut": c_def,
                       "UUID": st.session_state.edit_id if st.session_state.edit_mode else str(uuid.uuid4())}
                if st.session_state.edit_mode: df_t = df_t[df_t.UUID != st.session_state.edit_id]
                df_t = pd.concat([df_t, pd.DataFrame([new])], ignore_index=True)
                save_data("taxis", df_t);
                st.success("Enregistré");
                reset_form();
                st.rerun()
            if dele:
                df_t = df_t[df_t.UUID != st.session_state.edit_id]
                save_data("taxis", df_t);
                st.warning("Supprimé");
                reset_form();
                st.rerun()

# =============================================================================
# 5. SYNTHÈSE
# =============================================================================
elif selected_menu == "Synthèse":
    st.header("📊 Tableau de Bord")
    df_rev = load_data("rev");
    df_dep = load_data("dep")

    years = sorted(list(set(df_rev["Annee"].astype(str).tolist() + df_dep["Annee"].astype(str).tolist())), reverse=True)
    if not years: years = [str(datetime.now().year)]
    c1, c2 = st.columns(2)
    sel_y = c1.selectbox("Année", years);
    sel_v = c2.selectbox("Regroupement", ["Mois", "Trimestre", "Annuel"])

    # 1. REVENUS
    df_r = df_rev[df_rev["Annee"].astype(str) == str(sel_y)].copy()
    for c in ["Salaire_Chauffeur", "Grand_Total_Remis", "Total_Brut", "Essence", "Lavage"]:
        if c in df_r.columns: df_r[c] = pd.to_numeric(df_r[c], errors='coerce').fillna(0)

    div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)
    df_r["Ess_TPS"] = ((df_r["Essence"] + df_r["Lavage"]) / div) * (CONFIG["tps"] / 100)
    df_r["Ess_TVQ"] = ((df_r["Essence"] + df_r["Lavage"]) / div) * (CONFIG["tvq"] / 100)

    grp = "Mois" if sel_v == "Mois" else ("Trimestre" if sel_v == "Trimestre" else "Annee")
    syn_r = df_r.groupby(grp)[["Total_Brut", "Salaire_Chauffeur", "Grand_Total_Remis", "Ess_TPS", "Ess_TVQ"]].sum()

    # 2. DEPENSES
    df_d = df_dep[df_dep["Annee"].astype(str) == str(sel_y)].copy()
    if sel_v == "Trimestre": df_d["Trimestre"] = "T" + ((pd.to_datetime(df_d["Date"]).dt.month - 1) // 3 + 1).astype(
        str)
    grp_d = "Mois" if sel_v == "Mois" else ("Trimestre" if sel_v == "Trimestre" else "Annee")
    for c in ["Montant_Total", "TPS", "TVQ"]:
        if c in df_d.columns: df_d[c] = pd.to_numeric(df_d[c], errors='coerce').fillna(0)
    syn_d = df_d.groupby(grp_d)[["Montant_Total", "TPS", "TVQ"]].sum()

    # 3. FUSION
    final = syn_r.join(syn_d, lsuffix="_r", rsuffix="_d", how="outer").fillna(0)
    final["TPS à Recevoir"] = final.get("Ess_TPS", 0) + final.get("TPS", 0)
    final["TVQ à Recevoir"] = final.get("Ess_TVQ", 0) + final.get("TVQ", 0)
    final["PROFIT NET"] = final.get("Grand_Total_Remis", 0) - final.get("Montant_Total", 0)

    final = final.rename(
        columns={"Total_Brut": "Revenu BRUT", "Salaire_Chauffeur": "Salaire (40%)", "Grand_Total_Remis": "Net Perçu",
                 "Montant_Total": "Dépenses Garage"})

    cols_money = ["Revenu BRUT", "Salaire (40%)", "Net Perçu", "Dépenses Garage", "TPS à Recevoir", "TVQ à Recevoir",
                  "PROFIT NET"]

    # Config dynamique des colonnes pour le formatage
    col_cfg = {}
    for c in cols_money:
        if c in final.columns: col_cfg[c] = st.column_config.NumberColumn(format="%.2f $")

    st.dataframe(final, column_config=col_cfg, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total TPS", f"{final['TPS à Recevoir'].sum():.2f} $")
    c2.metric("Total TVQ", f"{final['TVQ à Recevoir'].sum():.2f} $")
    c3.metric("Profit Net", f"{final['PROFIT NET'].sum():.2f} $")

    st.divider()
    st.subheader("Détail Audit Taxes")
    audit = []
    for _, r in df_d.iterrows():
        if r.get("TPS", 0) > 0: audit.append(
            {"Date": r["Date"], "Source": r["Categorie"], "TPS": r["TPS"], "TVQ": r["TVQ"],
             "Total": r["Montant_Total"]})
    for _, r in df_r.iterrows():
        if r.get("Ess_TPS", 0) > 0: audit.append(
            {"Date": r["Date_Debut"], "Source": "Essence/Lavage", "TPS": r["Ess_TPS"], "TVQ": r["Ess_TVQ"],
             "Total": r["Essence"] + r["Lavage"]})

    if audit:
        df_aud = pd.DataFrame(audit).sort_values("Date", ascending=False)
        aud_cfg = {
            "TPS": st.column_config.NumberColumn(format="%.2f $"),
            "TVQ": st.column_config.NumberColumn(format="%.2f $"),
            "Total": st.column_config.NumberColumn(format="%.2f $")
        }
        st.dataframe(df_aud, column_config=aud_cfg, use_container_width=True)

# =============================================================================
# 6. PARAMETRES
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
        cat = st.text_area("Catégories", value="\n".join(CONFIG["categories"]))
        if st.form_submit_button("Sauvegarder"):
            save_config({"cout_appel": nc, "pct_chauf": np, "taux_impot": ni, "tps": nt, "tvq": nv,
                         "categories": [x.strip() for x in cat.split('\n') if x.strip()]})
            st.success("Sauvegardé !");
            st.rerun()

verifier_fichiers()