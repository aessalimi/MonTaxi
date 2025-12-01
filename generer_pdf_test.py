from fpdf import FPDF

def creer_pdf_test():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)

    # On écrit ligne par ligne le contenu typique de vos fichiers
    # J'utilise exactement les mots-clés que votre app attend
    lignes = [
        "FEUILLE HEBDOMADAIRE TAXI",
        "--------------------------------------------------",
        "CHAUFFEUR: Jean Testeur",
        "NO: 999",
        "DATE LUNDI: 12 Mai",
        "AU DIMANCHE: 18 Mai 2025",
        "",
        "--- DONNÉES COMPTEUR ---",
        "JOUR/DATE      METER",
        "LUNDI          100.00",
        "MARDI          200.00",
        "MERCREDI       300.00",
        "TOTAL:         1200.50",  # Votre app cherche "TOTAL:"
        "",
        "--- SALAIRE ---",
        "TOTAL SEMAINE METER .......... 1200.50",
        "FACTURES MONTANTS FIXES ...... 50.00",
        "NOMBRES D'APPELS ............. 45",
        "",
        "--- DÉDUCTIONS & RECETTES ---",
        "TOTAUX STS ................... 150.00",
        "TOTAUX CREDITS ............... 25.00",
        "TOTAUX PRIX FIXES ............ 10.00",
        "TOTAUX VISE/MASTER/DEBIT ..... 400.00",
        "TOTAUX ESSENCE ............... 85.50",
        "LAVAGE AUTO .................. 12.00",
        "DEPENSES (autre) ............. 5.00",
        "",
        "--- IMPOTS & NET ---",
        "AJOUTER $ POUR IMPOT ......... 75.20",
        "GRAND TOTAL A REMETTRE ....... 300.00"
    ]

    for ligne in lignes:
        pdf.cell(200, 8, txt=ligne, ln=True)

    nom_fichier = "test_taxi_parfait.pdf"
    pdf.output(nom_fichier)
    print(f"✅ Fichier '{nom_fichier}' généré avec succès !")

if __name__ == "__main__":
    creer_pdf_test()