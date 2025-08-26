
import streamlit as st
import pandas as pd

st.title("Calcolatore Fantacalcio - Fee percentuale annuale")
st.text("Simulatore Costo Opzione Under")

st.divider()

# Scaglioni per ciascuna fascia
SCAGLIONI = {
    "Under 19": [
        {"min": 1, "max": 19, "pct": 0.10},   # 10% per prezzi da 1 a 19
        {"min": 20, "max": 999, "pct": 0.20}  # 20% per prezzi da 20 in su
    ],
    "Under 23": [
        {"min": 1, "max": 19, "pct": 0.30},   # 30% per prezzi da 1 a 19
        {"min": 20, "max": 999, "pct": 0.50}  # 50% per prezzi da 20 in su
    ]
}

# Funzione per trovare la percentuale corretta
def get_fee_pct(fascia, prezzo_asta):
    for scaglione in SCAGLIONI[fascia]:
        if scaglione["min"] <= prezzo_asta <= scaglione["max"]:
            return scaglione["pct"]
    return 0  # Default se non trova scaglione

# Stato della simulazione
if "show_totale" not in st.session_state:
    st.session_state.show_totale = False

if not st.session_state.show_totale:
    with st.container():
        prezzo_asta = st.number_input("Prezzo d'asta (P0)", min_value=1, step=1, value=10)
        fascia = st.selectbox("Fascia giocatore", list(SCAGLIONI.keys()))
        anni = st.number_input("Numero di anni", min_value=1, max_value=2, value=1, step=1)
        if st.button("Calcola", key="calcola"):
            st.session_state.prezzo_asta = prezzo_asta
            st.session_state.fascia = fascia
            st.session_state.anni = anni
            st.session_state.show_totale = True
            st.rerun()

if st.session_state.show_totale:
    fee_pct = get_fee_pct(st.session_state.fascia, st.session_state.prezzo_asta)
    fee = round(st.session_state.prezzo_asta * fee_pct, 2)
    totale = st.session_state.prezzo_asta
    dati = []

    for anno in range(1, st.session_state.anni + 2):
        totale += fee
        dati.append({
            "Anno": anno,
            "Costo opzione annuale (FM)": fee,
            "Totale (FM)": round(totale, 2)
        })

    df = pd.DataFrame(dati).reset_index(drop=True)
    df_formattato = df.style.format({
        "Costo opzione annuale (FM)": "{:.0f} FM",
        "Totale (FM)": "{:.0f} FM"
    })

    st.subheader("📊 Totale da pagare per anno")
    st.dataframe(data=df_formattato, hide_index=True)
    if st.button("Effettua nuova simulazione", key="nuova_simulazione"):
        st.session_state.show_totale = False
        for k in ["prezzo_asta", "fascia", "anni"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()
