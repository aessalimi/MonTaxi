import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import json
import uuid
from datetime import datetime, timedelta
from tkcalendar import DateEntry
from PIL import Image, ImageTk

# --- CONFIGURATION FICHIERS ---
FILE_DEPENSES = "depenses_flotte.csv"
FILE_CHAUFFEURS = "chauffeurs.csv"
FILE_REVENUS = "revenus_hebdo.csv"
FILE_CONFIG = "config_taxi.json"

BG_JAUNE = "#FFFFE0"

DEFAULT_CONFIG = {
    "cout_appel": 1.05, "pourcent_chauffeur": 40.0, "taux_impot": 18.0,
    "taux_tps": 5.0, "taux_tvq": 9.975,
    "categories": ["Réparation mécanique", "Carrosserie", "Pneus", "Assurance véhicule", "Permis/Licence SAAQ",
                   "Frais administratifs", "Achat Pièces", "Autre"]
}


# --- GESTION PARAMÈTRES ---
def charger_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(FILE_CONFIG):
        try:
            config.update(json.load(open(FILE_CONFIG, 'r', encoding='utf-8')))
        except:
            pass
    return config


def sauvegarder_config_gui():
    try:
        data = {
            "cout_appel": float(entry_param_appel.get().replace(',', '.')),
            "pourcent_chauffeur": float(entry_param_pct.get().replace(',', '.')),
            "taux_impot": float(entry_param_impot.get().replace(',', '.')),
            "taux_tps": float(entry_param_tps.get().replace(',', '.')),
            "taux_tvq": float(entry_param_tvq.get().replace(',', '.')),
            "categories": [line.strip() for line in text_param_cats.get("1.0", tk.END).split('\n') if line.strip()]
        }
        with open(FILE_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        global PARAMS;
        PARAMS = data
        update_labels_transaction()
        combo_dep_cat['values'] = PARAMS['categories']
        messagebox.showinfo("Succès", "Configuration sauvegardée !")
        if entry_rev_meter_deb.get(): effectuer_calculs()
    except ValueError:
        messagebox.showerror("Erreur", "Chiffres invalides")


PARAMS = charger_config()


# --- UTILITAIRES ---
def safe_float(valeur):
    if not valeur: return 0.0
    try:
        return float(str(valeur).replace(',', '.').replace('$', '').replace(' ', ''))
    except:
        return 0.0


def verifier_fichiers():
    if not os.path.exists(FILE_DEPENSES):
        with open(FILE_DEPENSES, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(
                ["Date", "Mois", "Annee", "Taxi_ID", "Chauffeur", "Categorie", "Details", "Montant_HT", "TPS", "TVQ",
                 "Montant_Total", "UUID"])
    if not os.path.exists(FILE_CHAUFFEURS):
        with open(FILE_CHAUFFEURS, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["Nom", "Prenom", "Matricule", "Telephone", "Note", "UUID"])
    if not os.path.exists(FILE_REVENUS):
        with open(FILE_REVENUS, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["Date_Debut", "Date_Fin", "Mois", "Annee", "Trimestre", "Taxi_ID", "Chauffeur",
                                    "Meter_Debut", "Meter_Fin", "Meter_Total", "Fixe", "Total_Brut", "Nb_Appels",
                                    "Redevance_Calc", "Total_Sujet_Salaire", "Salaire_Chauffeur",
                                    "STS", "Credits_Comptes", "Prix_Fixes", "Visa_Debit", "Essence", "Lavage", "Divers",
                                    "Impot_Ajoute", "Grand_Total_Remis", "UUID"])


def get_liste_chauffeurs():
    l = []
    if os.path.exists(FILE_CHAUFFEURS):
        with open(FILE_CHAUFFEURS, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f): l.append(f"{r['Nom']} {r['Prenom']}")
    return sorted(l)


def get_annees_disponibles():
    years = set();
    years.add(datetime.now().strftime("%Y"))
    if os.path.exists(FILE_REVENUS):
        with open(FILE_REVENUS, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f): years.add(r['Annee'])
    return sorted(list(years), reverse=True)


# =============================================================================
# MODULE 1 : TRANSACTIONS
# =============================================================================
def effectuer_calculs(*args):
    try:
        t_ap, t_pct, t_imp = PARAMS["cout_appel"], PARAMS["pourcent_chauffeur"] / 100, PARAMS["taux_impot"] / 100
        m_d, m_f = safe_float(entry_rev_meter_deb.get()), safe_float(entry_rev_meter_fin.get())
        mt = m_f - m_d if m_f >= m_d else 0.0
        val_meter_total.config(text=f"{mt:.2f}", fg="red" if m_f < m_d and m_f > 0 else "black")

        fixe, nb = safe_float(entry_rev_fixe.get()), int(safe_float(entry_rev_appels.get()))
        brut = mt + fixe
        redev = nb * t_ap
        base = brut - redev
        sal = base * t_pct

        imp_cal = sal * t_imp
        entry_rev_impot.delete(0, tk.END);
        entry_rev_impot.insert(0, f"{imp_cal:.2f}")
        imp_fin = safe_float(entry_rev_impot.get())

        deducs = sum([safe_float(e.get()) for e in
                      [entry_rev_sts, entry_rev_credits, entry_rev_fixe_deduc, entry_rev_visa, entry_rev_essence,
                       entry_rev_lavage, entry_rev_divers]])
        grand_total = brut - sal - deducs + imp_fin

        val_redevance.config(text=f"- {redev:.2f} $")
        val_base_salaire.config(text=f"{base:.2f} $")
        val_salaire.config(text=f"{sal:.2f} $")
        val_total_deduc.config(text=f"{deducs:.2f} $")
        val_grand_total.config(text=f"{grand_total:.2f} $", fg="green" if grand_total >= 0 else "red")

        return {"m_debut": m_d, "m_fin": m_f, "meter_total": mt, "fixe": fixe, "total_brut": brut,
                "nb_appels": nb, "redevance": redev, "base_salaire": base, "salaire": sal,
                "sts": safe_float(entry_rev_sts.get()), "credits": safe_float(entry_rev_credits.get()),
                "prix_fixes": safe_float(entry_rev_fixe_deduc.get()), "visa": safe_float(entry_rev_visa.get()),
                "essence": safe_float(entry_rev_essence.get()), "lavage": safe_float(entry_rev_lavage.get()),
                "divers": safe_float(entry_rev_divers.get()), "impot": imp_fin, "grand_total": grand_total}
    except:
        return None


def update_labels_transaction():
    lbl_txt_redevance.config(text=f"Moins Appels (x {PARAMS['cout_appel']}$):")
    lbl_txt_salaire.config(text=f"Salaire Chauffeur ({PARAMS['pourcent_chauffeur']}%):")
    lbl_txt_impot.config(text=f"IMPOT ({PARAMS['taux_impot']}%):")


def vider_form_trans():
    var_current_trans_id.set("")
    for e in [entry_rev_meter_deb, entry_rev_meter_fin, entry_rev_fixe, entry_rev_appels, entry_rev_sts,
              entry_rev_credits, entry_rev_fixe_deduc, entry_rev_visa, entry_rev_essence,
              entry_rev_lavage, entry_rev_divers, entry_rev_impot]: e.delete(0, tk.END)
    entry_rev_date.set_date(datetime.now())
    for l in [val_meter_total, val_redevance, val_base_salaire, val_salaire, val_total_deduc,
              val_grand_total]: l.config(text="0.00 $")
    if tree_trans.selection(): tree_trans.selection_remove(tree_trans.selection())


def charger_tab_trans():
    for i in tree_trans.get_children(): tree_trans.delete(i)
    if os.path.exists(FILE_REVENUS):
        with open(FILE_REVENUS, 'r', encoding='utf-8') as f:
            reader = csv.reader(f);
            next(reader, None)
            for row in list(reader):
                if len(row) > 1:
                    rid = row[-1] if len(row) > 25 else "missing"
                    tree_trans.insert("", 0, values=(row[0], row[5], row[6], row[-2] + " $", rid))


def select_trans(event):
    sel = tree_trans.selection()
    if not sel: return
    vals = tree_trans.item(sel[0])['values']
    var_current_trans_id.set(vals[4])
    with open(FILE_REVENUS, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) > 0 and row[-1] == vals[4]: data = row; break
        else:
            return
    try:
        entry_rev_date.set_date(data[0])
    except:
        pass
    entry_rev_taxi.delete(0, tk.END);
    entry_rev_taxi.insert(0, data[5])
    combo_rev_chauffeur.set(data[6])

    mapping = [(entry_rev_meter_deb, 7), (entry_rev_meter_fin, 8), (entry_rev_fixe, 10), (entry_rev_appels, 12),
               (entry_rev_sts, 16), (entry_rev_credits, 17), (entry_rev_fixe_deduc, 18), (entry_rev_visa, 19),
               (entry_rev_essence, 20), (entry_rev_lavage, 21), (entry_rev_divers, 22), (entry_rev_impot, 23)]
    for w, i in mapping: w.delete(0, tk.END); (w.insert(0, data[i]) if i < len(data) else None)
    effectuer_calculs()


def crud_trans(mode):
    # Sécurité pour Créer
    if mode == "create" and var_current_trans_id.get():
        if not messagebox.askyesno("Attention", "Créer un doublon ?"): return
        var_current_trans_id.set("")

    # Sécurité pour Supprimer
    if mode == "delete":
        if not var_current_trans_id.get() or not messagebox.askyesno("Confirm", "Supprimer définitivement ?"): return

    # Calculs si pas delete
    res = None
    if mode != "delete":
        res = effectuer_calculs()
        if not res or not entry_rev_taxi.get() or not combo_rev_chauffeur.get():
            messagebox.showwarning("Erreur", "Données manquantes");
            return

    # --- LOGIQUE CRITIQUE DE RÉÉCRITURE DU FICHIER ---
    rows = []
    if os.path.exists(FILE_REVENUS):
        with open(FILE_REVENUS, 'r', encoding='utf-8') as f: rows = list(csv.reader(f))

    header = rows[0] if rows else []
    new_rows = []
    target_id = var_current_trans_id.get()

    # Construction de la nouvelle liste
    for row in rows[1:]:
        if len(row) < 26:
            # On garde les lignes corrompues/anciennes pour ne pas perdre de données
            new_rows.append(row)
            continue

        row_id = row[25]

        if row_id == target_id:
            # Si c'est la ligne ciblée
            if mode == "delete":
                continue  # ON NE L'AJOUTE PAS -> SUPPRESSION EFFECTIVE
            elif mode == "update":
                continue  # On l'ajoute plus bas avec les nouvelles valeurs

        # Sinon on garde la ligne
        new_rows.append(row)

    # Si Create ou Update, on ajoute la nouvelle ligne
    if mode != "delete":
        d_deb = entry_rev_date.get_date().strftime("%Y-%m-%d")
        d_o = datetime.strptime(d_deb, "%Y-%m-%d");
        d_fin = (d_o + timedelta(days=6)).strftime("%Y-%m-%d")
        m, y, t = d_o.strftime("%Y-%m"), d_o.strftime("%Y"), f"T{(d_o.month - 1) // 3 + 1}"
        cid = target_id if mode == "update" else str(uuid.uuid4())

        line = [d_deb, d_fin, m, y, t, entry_rev_taxi.get(), combo_rev_chauffeur.get(),
                res['m_debut'], res['m_fin'], f"{res['meter_total']:.2f}", res['fixe'], f"{res['total_brut']:.2f}",
                res['nb_appels'], f"{res['redevance']:.2f}", f"{res['base_salaire']:.2f}", f"{res['salaire']:.2f}",
                res['sts'], res['credits'], res['prix_fixes'], res['visa'], res['essence'], res['lavage'],
                res['divers'], res['impot'], f"{res['grand_total']:.2f}", cid]

        new_rows.append(line)

    # ÉCRITURE DISQUE
    with open(FILE_REVENUS, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(new_rows)

    # RAFRAICHISSEMENT
    vider_form_trans()
    charger_tab_trans()
    # On force la mise à jour de l'onglet Analyse immédiatement
    calculer_synthese()

    if mode == "delete":
        messagebox.showinfo("Succès", "Transaction supprimée")
    else:
        messagebox.showinfo("Succès", "Enregistré")


# =============================================================================
# MODULE 2 : DÉPENSES
# =============================================================================
def vider_form_dep():
    var_current_dep_id.set("")
    for e in [entry_dep_taxi, combo_dep_chauffeur, combo_dep_cat, entry_dep_details, entry_dep_montant]:
        if isinstance(e, tk.Entry):
            e.delete(0, tk.END)
        else:
            e.set('')
    entry_dep_date.set_date(datetime.now())
    var_taxe.set(0);
    lbl_detail_taxes.config(text="")
    if tree_dep.selection(): tree_dep.selection_remove(tree_dep.selection())


def charger_tab_dep():
    for i in tree_dep.get_children(): tree_dep.delete(i)
    if os.path.exists(FILE_DEPENSES):
        with open(FILE_DEPENSES, 'r', encoding='utf-8') as f:
            reader = csv.reader(f);
            next(reader, None)
            for row in list(reader):
                if len(row) > 10:
                    rid = row[-1] if len(row) > 11 else "missing"
                    tree_dep.insert("", 0, values=(row[0], row[3], row[5], row[8], row[9], row[10] + " $", rid))


def select_dep(event):
    sel = tree_dep.selection()
    if not sel: return
    vals = tree_dep.item(sel[0])['values']
    var_current_dep_id.set(vals[6])
    with open(FILE_DEPENSES, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) > 0 and row[-1] == vals[6]: data = row; break
        else:
            return
    try:
        entry_dep_date.set_date(data[0])
    except:
        pass
    entry_dep_taxi.delete(0, tk.END);
    entry_dep_taxi.insert(0, data[3])
    combo_dep_chauffeur.set(data[4]);
    combo_dep_cat.set(data[5])
    entry_dep_details.delete(0, tk.END);
    entry_dep_details.insert(0, data[6])
    entry_dep_montant.delete(0, tk.END);
    entry_dep_montant.insert(0, data[10])
    if safe_float(data[8]) > 0:
        var_taxe.set(1)
    else:
        var_taxe.set(0)


def crud_dep(mode):
    if mode == "create" and var_current_dep_id.get():
        if not messagebox.askyesno("Attention", "Copier dépense ?"): return
        var_current_dep_id.set("")
    if mode == "delete":
        if not var_current_dep_id.get() or not messagebox.askyesno("Confirm", "Supprimer ?"): return

    line = None
    if mode != "delete":
        mt = safe_float(entry_dep_montant.get())
        if mt == 0: messagebox.showwarning("Erreur", "Montant requis"); return

        if var_taxe.get() == 1:
            div = 1 + (PARAMS["taux_tps"] / 100) + (PARAMS["taux_tvq"] / 100)
            ht = mt / div
            tps, tvq = ht * (PARAMS["taux_tps"] / 100), ht * (PARAMS["taux_tvq"] / 100)
        else:
            ht, tps, tvq = mt, 0.0, 0.0

        d = entry_dep_date.get_date().strftime("%Y-%m-%d")
        d_o = datetime.strptime(d, "%Y-%m-%d")
        cid = var_current_dep_id.get() or str(uuid.uuid4())
        line = [d, d_o.strftime("%Y-%m"), d_o.strftime("%Y"), entry_dep_taxi.get(), combo_dep_chauffeur.get(),
                combo_dep_cat.get(), entry_dep_details.get(), f"{ht:.2f}", f"{tps:.2f}", f"{tvq:.2f}", f"{mt:.2f}", cid]

    rows = []
    if os.path.exists(FILE_DEPENSES):
        with open(FILE_DEPENSES, 'r', encoding='utf-8') as f: rows = list(csv.reader(f))

    header = rows[0] if rows else []
    new_rows = []
    target_id = var_current_dep_id.get()

    for row in rows[1:]:
        if len(row) < 12:
            new_rows.append(row)
            continue

        if row[-1] == target_id:
            if mode == "delete": continue
            if mode == "update": continue  # On ajoute la nouvelle ligne plus bas
        else:
            new_rows.append(row)

    if mode != "delete" and line: new_rows.append(line)

    with open(FILE_DEPENSES, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(header);
        csv.writer(f).writerows(new_rows)

    vider_form_dep();
    charger_tab_dep();
    calculer_synthese()
    if mode != "delete": messagebox.showinfo("Succès", "Dépense enregistrée")


# =============================================================================
# MODULE 3 : CHAUFFEURS
# =============================================================================
def vider_form_chauf():
    var_current_chauf_id.set("")
    for e in [entry_ch_nom, entry_ch_prenom, entry_ch_mat, entry_ch_tel, entry_ch_note]: e.delete(0, tk.END)
    if tree_chauf.selection(): tree_chauf.selection_remove(tree_chauf.selection())


def charger_tab_chauf():
    for i in tree_chauf.get_children(): tree_chauf.delete(i)
    if os.path.exists(FILE_CHAUFFEURS):
        with open(FILE_CHAUFFEURS, 'r', encoding='utf-8') as f:
            reader = csv.reader(f);
            next(reader, None)
            for row in list(reader):
                if len(row) > 1:
                    rid = row[-1] if len(row) > 5 else "missing"
                    tree_chauf.insert("", 0, values=(row[0], row[1], row[3], rid))


def select_chauf(event):
    sel = tree_chauf.selection()
    if not sel: return
    vals = tree_chauf.item(sel[0])['values']
    var_current_chauf_id.set(vals[3])
    with open(FILE_CHAUFFEURS, 'r', encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) > 0 and row[-1] == vals[3]: data = row; break
        else:
            return
    entry_ch_nom.delete(0, tk.END);
    entry_ch_nom.insert(0, data[0])
    entry_ch_prenom.delete(0, tk.END);
    entry_ch_prenom.insert(0, data[1])
    entry_ch_mat.delete(0, tk.END);
    entry_ch_mat.insert(0, data[2])
    entry_ch_tel.delete(0, tk.END);
    entry_ch_tel.insert(0, data[3])
    entry_ch_note.delete(0, tk.END);
    entry_ch_note.insert(0, data[4])


def crud_chauf(mode):
    if mode == "create" and var_current_chauf_id.get():
        if not messagebox.askyesno("Attention", "Créer doublon ?"): return
        var_current_chauf_id.set("")
    if mode == "delete":
        if not var_current_chauf_id.get() or not messagebox.askyesno("Confirm", "Supprimer ?"): return

    line = None
    if mode != "delete":
        if not entry_ch_nom.get(): messagebox.showwarning("Erreur", "Nom requis"); return
        cid = var_current_chauf_id.get() or str(uuid.uuid4())
        line = [entry_ch_nom.get(), entry_ch_prenom.get(), entry_ch_mat.get(), entry_ch_tel.get(), entry_ch_note.get(),
                cid]

    rows = []
    if os.path.exists(FILE_CHAUFFEURS):
        with open(FILE_CHAUFFEURS, 'r', encoding='utf-8') as f: rows = list(csv.reader(f))

    header = rows[0] if rows else []
    new_rows = []
    target_id = var_current_chauf_id.get()

    for row in rows[1:]:
        if len(row) < 6:
            new_rows.append(row)
            continue
        if row[-1] == target_id:
            if mode == "delete": continue
            if mode == "update": continue
        else:
            new_rows.append(row)

    if mode != "delete" and line: new_rows.append(line)

    with open(FILE_CHAUFFEURS, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(header);
        csv.writer(f).writerows(new_rows)
    vider_form_chauf();
    charger_tab_chauf();
    mise_a_jour_combos()
    if mode != "delete": messagebox.showinfo("Succès", "Chauffeur enregistré")


def mise_a_jour_combos():
    l = get_liste_chauffeurs()
    combo_rev_chauffeur['values'] = l;
    combo_dep_chauffeur['values'] = l


# =============================================================================
# MODULE 4 : SYNTHÈSE (CORRIGÉE ET OPTIMISÉE)
# =============================================================================
def calculer_synthese():
    # Nettoyage des tableaux
    for i in tree_synthese.get_children(): tree_synthese.delete(i)
    for i in tree_analyse_det.get_children(): tree_analyse_det.delete(i)

    f_annee = combo_filt_annee.get()
    f_type = combo_filt_type.get()  # Mois, Trimestre, Annuel

    stats = {}

    # Structure : { "2025-01": { brut:0, salaire:0, net_proprio:0, tps:0, tvq:0 } }

    # Helper pour déterminer la clé de regroupement
    def get_key(row):
        if f_type == "Par Mois":
            return row['Mois']
        elif f_type == "Par Trimestre":
            return f"T{(int(row['Mois'].split('-')[1]) - 1) // 3 + 1}"
        else:
            return f"ANNÉE {row['Annee']}"

    div_taxe = 1 + PARAMS["taux_tps"] / 100 + PARAMS["taux_tvq"] / 100

    # 1. SCAN REVENUS (Transactions) -> Salaire, Net Proprio, Taxes Essence/Lavage
    if os.path.exists(FILE_REVENUS):
        with open(FILE_REVENUS, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['Annee'] != f_annee: continue

                key = get_key(row)
                if key not in stats: stats[key] = {'brut': 0, 'salaire': 0, 'remettre': 0, 'tps': 0, 'tvq': 0}

                # Sommes basiques (STRICTES)
                stats[key]['brut'] += safe_float(row['Total_Brut'])
                stats[key]['salaire'] += safe_float(row['Salaire_Chauffeur'])
                stats[key]['remettre'] += safe_float(row['Grand_Total_Remis'])

                # Extraction Taxes implicites (Essence/Lavage)
                for col in ["Essence", "Lavage"]:
                    val = safe_float(row.get(col, 0))
                    if val > 0:
                        ht = val / div_taxe
                        tps, tvq = ht * PARAMS["taux_tps"] / 100, ht * PARAMS["taux_tvq"] / 100
                        stats[key]['tps'] += tps
                        stats[key]['tvq'] += tvq
                        # Ajout au détail
                        tree_analyse_det.insert("", tk.END, values=(row['Date_Debut'], f"{col} (Trans.)", f"{tps:.2f}",
                                                                    f"{tvq:.2f}", f"{val:.2f}"))

    # 2. SCAN DEPENSES (Factures) -> Taxes Dépenses
    if os.path.exists(FILE_DEPENSES):
        with open(FILE_DEPENSES, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row['Annee'] != f_annee: continue

                key = get_key(row)
                if key not in stats: stats[key] = {'brut': 0, 'salaire': 0, 'remettre': 0, 'tps': 0, 'tvq': 0}

                tps, tvq = safe_float(row['TPS']), safe_float(row['TVQ'])
                stats[key]['tps'] += tps
                stats[key]['tvq'] += tvq

                if tps > 0 or tvq > 0:
                    tree_analyse_det.insert("", tk.END,
                                            values=(row['Date'], row['Categorie'], f"{tps:.2f}", f"{tvq:.2f}",
                                                    row['Montant_Total']))

    # 3. REMPLISSAGE TABLEAU SYNTHESE
    for k, v in sorted(stats.items()):
        tree_synthese.insert("", tk.END, values=(
            k,
            f"{v['brut']:.2f} $",
            f"{v['salaire']:.2f} $",
            f"{v['remettre']:.2f} $",
            f"{v['tps']:.2f} $",
            f"{v['tvq']:.2f} $"
        ))


# =============================================================================
# INTERFACE
# =============================================================================
fenetre = tk.Tk()
fenetre.title("Gestion Taxi - MonTaxi31 - Version Finale")
fenetre.geometry("1280x950")

var_current_trans_id = tk.StringVar()
var_current_dep_id = tk.StringVar()
var_current_chauf_id = tk.StringVar()

frame_logo = tk.Frame(fenetre, bg="white", pady=10);
frame_logo.pack(fill="x")
LOGO_PATH = "logo.png"
if os.path.exists(LOGO_PATH):
    try:
        img = Image.open(LOGO_PATH);
        hpercent = (80 / float(img.size[1]));
        img = img.resize((int((float(img.size[0]) * float(hpercent))), 80), Image.Resampling.LANCZOS)
        logo_tk = ImageTk.PhotoImage(img);
        tk.Label(frame_logo, image=logo_tk, bg="white", bd=0).pack()
    except:
        tk.Label(frame_logo, text="MonTaxi31", font=("Arial", 24, "bold"), bg="white").pack()
else:
    tk.Label(frame_logo, text="MonTaxi31", font=("Arial", 24, "bold"), bg="white").pack()

notebook = ttk.Notebook(fenetre);
notebook.pack(pady=10, expand=True, fill="both")
tab_trans = tk.Frame(notebook);
notebook.add(tab_trans, text=" 📒 TRANSACTIONS ")
tab_res = tk.Frame(notebook);
notebook.add(tab_res, text=" 📊 SYNTHÈSE ")
tab_dep = tk.Frame(notebook);
notebook.add(tab_dep, text=" 🔧 DÉPENSES ")
tab_chauf = tk.Frame(notebook);
notebook.add(tab_chauf, text=" 👨‍✈️ CHAUFFEURS ")
tab_param = tk.Frame(notebook);
notebook.add(tab_param, text=" ⚙️ PARAMÈTRES ")

# TRANSACTIONS
f_top = tk.Frame(tab_trans);
f_top.pack(fill="x", padx=10)
f_info = tk.LabelFrame(f_top, text="Infos", padx=5);
f_info.pack(fill="x")
tk.Label(f_info, text="Date:").pack(side=tk.LEFT)
entry_rev_date = DateEntry(f_info, width=12, background='#008CBA', foreground='white', borderwidth=2,
                           date_pattern='yyyy-mm-dd');
entry_rev_date.pack(side=tk.LEFT)
tk.Label(f_info, text="Taxi:").pack(side=tk.LEFT, padx=5);
entry_rev_taxi = tk.Entry(f_info, width=6, bg=BG_JAUNE);
entry_rev_taxi.pack(side=tk.LEFT)
tk.Label(f_info, text="Chauffeur:").pack(side=tk.LEFT, padx=5);
combo_rev_chauffeur = ttk.Combobox(f_info, width=20);
combo_rev_chauffeur.pack(side=tk.LEFT)

f_calc = tk.Frame(f_top);
f_calc.pack(fill="x", pady=5)
lf_g = tk.LabelFrame(f_calc, text="Revenus", padx=5);
lf_g.pack(side=tk.LEFT, fill="both", expand=True)


def row(p, t, r): tk.Label(p, text=t).grid(row=r, column=0, sticky="w"); e = tk.Entry(p, bg=BG_JAUNE, width=10); e.grid(
    row=r, column=1); return e


entry_rev_meter_deb = row(lf_g, "Meter DEBUT:", 0);
entry_rev_meter_fin = row(lf_g, "Meter FIN:", 1)
tk.Label(lf_g, text="Meter Total:", font="Arial 9 bold").grid(row=2, column=0);
val_meter_total = tk.Label(lf_g, text="0.00", font="Arial 9 bold");
val_meter_total.grid(row=2, column=1)
entry_rev_fixe = row(lf_g, "Fixe:", 3);
entry_rev_appels = row(lf_g, "Appels:", 4)
lbl_txt_redevance = tk.Label(lf_g, text="Redevance:", fg="gray");
lbl_txt_redevance.grid(row=5, column=0);
val_redevance = tk.Label(lf_g, text="0.00", fg="red");
val_redevance.grid(row=5, column=1)
tk.Label(lf_g, text="Base Salaire:", font="Arial 9 bold").grid(row=6, column=0);
val_base_salaire = tk.Label(lf_g, text="0.00", font="Arial 9 bold");
val_base_salaire.grid(row=6, column=1)
lbl_txt_salaire = tk.Label(lf_g, text="Salaire:", fg="blue");
lbl_txt_salaire.grid(row=7, column=0);
val_salaire = tk.Label(lf_g, text="0.00", font="Arial 10 bold", fg="blue");
val_salaire.grid(row=7, column=1)

lf_d = tk.LabelFrame(f_calc, text="Déductions", padx=5);
lf_d.pack(side=tk.LEFT, fill="both", expand=True, padx=5)
entry_rev_sts = row(lf_d, "STS:", 0);
entry_rev_credits = row(lf_d, "Credits:", 1);
entry_rev_fixe_deduc = row(lf_d, "Prix Fixe:", 2);
entry_rev_visa = row(lf_d, "Visa:", 3)
entry_rev_essence = row(lf_d, "Essence:", 4);
entry_rev_lavage = row(lf_d, "Lavage:", 5);
entry_rev_divers = row(lf_d, "Divers:", 6)
tk.Label(lf_d, text="Total Ded:").grid(row=7, column=0);
val_total_deduc = tk.Label(lf_d, text="0.00");
val_total_deduc.grid(row=7, column=1)
lbl_txt_impot = tk.Label(lf_d, text="Impot:", fg="green");
lbl_txt_impot.grid(row=8, column=0);
entry_rev_impot = tk.Entry(lf_d, bg=BG_JAUNE, width=10);
entry_rev_impot.grid(row=8, column=1)

f_btn = tk.Frame(f_top, pady=5, bg="#eee");
f_btn.pack(fill="x")
tk.Button(f_btn, text="CALCULER", command=effectuer_calculs).pack(side=tk.LEFT)
tk.Button(f_btn, text="AJOUTER", command=lambda: crud_trans("create"), bg="#4CAF50", fg="white").pack(side=tk.LEFT,
                                                                                                      padx=5)
tk.Button(f_btn, text="MODIFIER", command=lambda: crud_trans("update"), bg="orange").pack(side=tk.LEFT, padx=5)
tk.Button(f_btn, text="SUPPRIMER", command=lambda: crud_trans("delete"), bg="#F44336", fg="white").pack(side=tk.LEFT,
                                                                                                        padx=5)
tk.Button(f_btn, text="VIDER", command=vider_form_trans).pack(side=tk.RIGHT)
val_grand_total = tk.Label(f_btn, text="0.00 $", font="Arial 18 bold", fg="blue", bg="#eee");
val_grand_total.pack(side=tk.RIGHT, padx=10)
tk.Label(f_btn, text="SOMME À REMETTRE :", font="Arial 12 bold", bg="#eee").pack(side=tk.RIGHT)

f_list = tk.LabelFrame(tab_trans, text="Historique");
f_list.pack(fill="both", expand=True, padx=10, pady=5)
cols_t = ("Date", "Taxi", "Chauffeur", "Total", "UUID");
tree_trans = ttk.Treeview(f_list, columns=cols_t, show="headings", height=6)
for c in cols_t: tree_trans.heading(c, text=c)
tree_trans.column("UUID", width=0, stretch=tk.NO)
tree_trans.pack(fill="both", expand=True, side=tk.LEFT);
tree_trans.bind("<<TreeviewSelect>>", select_trans)

# SYNTHESE
f_filt = tk.Frame(tab_res, pady=10);
f_filt.pack()
tk.Label(f_filt, text="Année :").pack(side=tk.LEFT)
combo_filt_annee = ttk.Combobox(f_filt, values=get_annees_disponibles(), width=6);
combo_filt_annee.pack(side=tk.LEFT, padx=5)
if get_annees_disponibles():
    combo_filt_annee.current(0)
else:
    combo_filt_annee.set(datetime.now().year)
tk.Label(f_filt, text="Vue :").pack(side=tk.LEFT, padx=10)
combo_filt_type = ttk.Combobox(f_filt, values=["Par Mois", "Par Trimestre", "Annuel"], width=12);
combo_filt_type.current(0);
combo_filt_type.pack(side=tk.LEFT, padx=5)
tk.Button(f_filt, text="ACTUALISER TABLEAU", command=calculer_synthese, bg="#008CBA", fg="white").pack(side=tk.LEFT,
                                                                                                       padx=20)

f_syn = tk.LabelFrame(tab_res, text="Synthèse Financière Globale (Revenus & Taxes)", padx=10, pady=5);
f_syn.pack(fill="x", padx=10)
cols_s = ("Période", "Revenu BRUT Taxi", "Salaire Chauffeur", "À Remettre (Proprio)", "TPS à Recevoir",
          "TVQ à Recevoir")
tree_synthese = ttk.Treeview(f_syn, columns=cols_s, show="headings", height=8)
for c in cols_s: tree_synthese.heading(c, text=c); tree_synthese.column(c, width=130)
tree_synthese.pack(fill="x")

f_det = tk.LabelFrame(tab_res, text="Détail des Taxes (Dépenses + Essence/Lavage)", padx=10, pady=5);
f_det.pack(fill="both", expand=True, padx=10)
cols_d = ("Date", "Source", "TPS", "TVQ", "Montant TTC");
tree_analyse_det = ttk.Treeview(f_det, columns=cols_d, show="headings")
for c in cols_d: tree_analyse_det.heading(c, text=c)
sb_ad = ttk.Scrollbar(f_det, orient="vertical", command=tree_analyse_det.yview);
sb_ad.pack(side=tk.RIGHT, fill="y")
tree_analyse_det.configure(yscrollcommand=sb_ad.set);
tree_analyse_det.pack(fill="both", expand=True)

# DEPENSES
f_d_form = tk.LabelFrame(tab_dep, text="Dépense", padx=10, pady=10);
f_d_form.pack(fill="x", padx=10)
tk.Label(f_d_form, text="Date:").grid(row=0, column=0);
entry_dep_date = DateEntry(f_d_form, width=12, background='#008CBA', foreground='white', borderwidth=2,
                           date_pattern='yyyy-mm-dd');
entry_dep_date.grid(row=0, column=1)
tk.Label(f_d_form, text="Taxi:").grid(row=0, column=2);
entry_dep_taxi = tk.Entry(f_d_form, bg=BG_JAUNE);
entry_dep_taxi.grid(row=0, column=3)
tk.Label(f_d_form, text="Chauffeur:").grid(row=1, column=0);
combo_dep_chauffeur = ttk.Combobox(f_d_form);
combo_dep_chauffeur.grid(row=1, column=1)
tk.Label(f_d_form, text="Catégorie:").grid(row=1, column=2);
combo_dep_cat = ttk.Combobox(f_d_form, values=PARAMS['categories']);
combo_dep_cat.grid(row=1, column=3)
tk.Label(f_d_form, text="Détails:").grid(row=2, column=0);
entry_dep_details = tk.Entry(f_d_form, width=30, bg=BG_JAUNE);
entry_dep_details.grid(row=2, column=1, columnspan=3, sticky="w")
tk.Label(f_d_form, text="Total:").grid(row=0, column=4);
entry_dep_montant = tk.Entry(f_d_form, bg=BG_JAUNE, width=10);
entry_dep_montant.grid(row=0, column=5)
var_taxe = tk.IntVar();
tk.Checkbutton(f_d_form, text="Taxes incluses?", variable=var_taxe).grid(row=1, column=5)
lbl_detail_taxes = tk.Label(f_d_form, text="", fg="gray");
lbl_detail_taxes.grid(row=2, column=5)
f_db = tk.Frame(f_d_form);
f_db.grid(row=3, columnspan=6, pady=10)
tk.Button(f_db, text="AJOUTER", command=lambda: crud_dep("create"), bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
tk.Button(f_db, text="MODIFIER", command=lambda: crud_dep("update"), bg="orange").pack(side=tk.LEFT, padx=5)
tk.Button(f_db, text="SUPPRIMER", command=lambda: crud_dep("delete"), bg="#F44336", fg="white").pack(side=tk.LEFT,
                                                                                                     padx=5)
tk.Button(f_db, text="VIDER", command=vider_form_dep).pack(side=tk.LEFT, padx=20)
f_d_list = tk.LabelFrame(tab_dep, text="Liste");
f_d_list.pack(fill="both", expand=True, padx=10, pady=5)
cols_d = ("Date", "Taxi", "Cat", "TPS", "TVQ", "Total", "UUID");
tree_dep = ttk.Treeview(f_d_list, columns=cols_d, show="headings")
for c in cols_d: tree_dep.heading(c, text=c)
tree_dep.column("UUID", width=0, stretch=tk.NO);
tree_dep.pack(fill="both", expand=True);
tree_dep.bind("<<TreeviewSelect>>", select_dep)

# CHAUFFEURS
f_c_form = tk.LabelFrame(tab_chauf, text="Fiche", padx=10, pady=10);
f_c_form.pack(fill="x", padx=10)
tk.Label(f_c_form, text="Nom:").grid(row=0, column=0);
entry_ch_nom = tk.Entry(f_c_form, bg=BG_JAUNE);
entry_ch_nom.grid(row=0, column=1)
tk.Label(f_c_form, text="Prénom:").grid(row=0, column=2);
entry_ch_prenom = tk.Entry(f_c_form, bg=BG_JAUNE);
entry_ch_prenom.grid(row=0, column=3)
tk.Label(f_c_form, text="Matricule:").grid(row=1, column=0);
entry_ch_mat = tk.Entry(f_c_form, bg=BG_JAUNE);
entry_ch_mat.grid(row=1, column=1)
tk.Label(f_c_form, text="Téléphone:").grid(row=1, column=2);
entry_ch_tel = tk.Entry(f_c_form, bg=BG_JAUNE);
entry_ch_tel.grid(row=1, column=3)
tk.Label(f_c_form, text="Note:").grid(row=2, column=0);
entry_ch_note = tk.Entry(f_c_form, width=30, bg=BG_JAUNE);
entry_ch_note.grid(row=2, column=1, columnspan=3, sticky="w")
f_cb = tk.Frame(f_c_form);
f_cb.grid(row=3, columnspan=4, pady=10)
tk.Button(f_cb, text="AJOUTER", command=lambda: crud_chauf("create"), bg="#4CAF50", fg="white").pack(side=tk.LEFT,
                                                                                                     padx=5)
tk.Button(f_cb, text="MODIFIER", command=lambda: crud_chauf("update"), bg="orange").pack(side=tk.LEFT, padx=5)
tk.Button(f_cb, text="SUPPRIMER", command=lambda: crud_chauf("delete"), bg="#F44336", fg="white").pack(side=tk.LEFT,
                                                                                                       padx=5)
tk.Button(f_cb, text="VIDER", command=vider_form_chauf).pack(side=tk.LEFT, padx=20)
f_c_list = tk.LabelFrame(tab_chauf, text="Liste");
f_c_list.pack(fill="both", expand=True, padx=10, pady=5)
cols_c = ("Nom", "Prenom", "Tel", "UUID");
tree_chauf = ttk.Treeview(f_c_list, columns=cols_c, show="headings")
for c in cols_c: tree_chauf.heading(c, text=c)
tree_chauf.column("UUID", width=0, stretch=tk.NO);
tree_chauf.pack(fill="both", expand=True);
tree_chauf.bind("<<TreeviewSelect>>", select_chauf)

# PARAMETRES
f_scroll = tk.Frame(tab_param);
f_scroll.pack(fill="both", expand=True)
c_p = tk.Canvas(f_scroll);
c_p.pack(side=tk.LEFT, fill="both", expand=True)
sb_p = ttk.Scrollbar(f_scroll, orient="vertical", command=c_p.yview);
sb_p.pack(side=tk.RIGHT, fill="y")
c_p.configure(yscrollcommand=sb_p.set);
c_p.bind('<Configure>', lambda e: c_p.configure(scrollregion=c_p.bbox("all")))
f_p_in = tk.Frame(c_p);
c_p.create_window((0, 0), window=f_p_in, anchor="nw")
tk.Label(f_p_in, text="Taux", font="Arial 12 bold").pack(pady=10)
lf_p = tk.LabelFrame(f_p_in, text="Valeurs", padx=10, pady=10);
lf_p.pack()
tk.Label(lf_p, text="Coût Appel:").grid(row=0, column=0);
entry_param_appel = tk.Entry(lf_p, bg=BG_JAUNE);
entry_param_appel.insert(0, PARAMS["cout_appel"]);
entry_param_appel.grid(row=0, column=1)
tk.Label(lf_p, text="% Chauffeur:").grid(row=1, column=0);
entry_param_pct = tk.Entry(lf_p, bg=BG_JAUNE);
entry_param_pct.insert(0, PARAMS["pourcent_chauffeur"]);
entry_param_pct.grid(row=1, column=1)
tk.Label(lf_p, text="% Impôt:").grid(row=2, column=0);
entry_param_impot = tk.Entry(lf_p, bg=BG_JAUNE);
entry_param_impot.insert(0, PARAMS["taux_impot"]);
entry_param_impot.grid(row=2, column=1)
tk.Label(lf_p, text="% TPS:").grid(row=3, column=0);
entry_param_tps = tk.Entry(lf_p, bg=BG_JAUNE);
entry_param_tps.insert(0, PARAMS["taux_tps"]);
entry_param_tps.grid(row=3, column=1)
tk.Label(lf_p, text="% TVQ:").grid(row=4, column=0);
entry_param_tvq = tk.Entry(lf_p, bg=BG_JAUNE);
entry_param_tvq.insert(0, PARAMS["taux_tvq"]);
entry_param_tvq.grid(row=4, column=1)
tk.Label(f_p_in, text="Catégories", font="Arial 12 bold").pack(pady=10)
text_param_cats = tk.Text(f_p_in, height=10, width=40, bg=BG_JAUNE);
text_param_cats.pack()
text_param_cats.insert("1.0", "\n".join(PARAMS["categories"]))
tk.Button(f_p_in, text="SAUVEGARDER", command=sauvegarder_config_gui, bg="#008CBA", fg="white").pack(pady=20)

btn_quit = tk.Button(fenetre, text="QUITTER L'APPLICATION", command=fenetre.destroy, bg="#333", fg="white",
                     font="Arial 10 bold")
btn_quit.pack(side=tk.BOTTOM, fill="x", pady=5)

verifier_fichiers();
mise_a_jour_combos()
charger_tab_trans();
charger_tab_dep();
charger_tab_chauf();
calculer_synthese()
fenetre.mainloop()