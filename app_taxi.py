import streamlit as st
import pandas as pd
import os
import json
import uuid
from datetime import datetime, timedelta

st.set_page_config(page_title="MonTaxi31", page_icon="🚖", layout="wide")

# --- FICHIERS ---
FILES = {
}


}
        try:
        except:
            pass


def save_config(cfg):




                "Meter_Deb", "Meter_Fin", "Meter_Total", "Fixe", "Total_Brut", "Nb_Appels",
                "Redevance", "Base_Salaire", "Salaire_Chauffeur", "STS", "Credits", "Prix_Fixes",

            try:
                df = pd.read_csv(FILES[key])


        return df
        return pd.DataFrame()


def save_data(key, df):
    df.to_csv(FILES[key], index=False)



# =============================================================================
# =============================================================================






            try:
            except:




            st.divider()

                st.rerun()

# =============================================================================
# =============================================================================

            c1, c2 = st.columns(2)


                        div = 1 + (CONFIG["tps"] / 100) + (CONFIG["tvq"] / 100)
                        tvq = ht * (CONFIG["tvq"] / 100)
                    else:

                    st.rerun()
                st.rerun()

# =============================================================================
# =============================================================================

            c1, c2 = st.columns(2)
                df_c = pd.concat([df_c, pd.DataFrame([new])], ignore_index=True)
                st.rerun()


# =============================================================================
# =============================================================================

    c1, c2 = st.columns(2)









    st.divider()

            {"Date": r["Date"], "Source": r["Categorie"], "TPS": r["TPS"], "TVQ": r["TVQ"],

        c1, c2 = st.columns(2)
