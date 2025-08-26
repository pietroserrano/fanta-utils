
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from google import genai
import csv


file_anagrafica = "Foglio di lavoro senza nome.xlsx"
file_csv_fd = "serie_a_2025_26_players_fd.csv"


def carica_quotazioni(uploaded_file):
    df_q = pd.read_excel(uploaded_file, sheet_name="Tutti", header=1)
    # Restituisci tutte le colonne, senza filtri
    return df_q


def carica_dob_da_csv(csv_path):
    dob_dict = {}
    if not os.path.exists(csv_path):
        return dob_dict
    # Prepara una lista di tutte le righe del CSV
    righe_csv = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            righe_csv.append(row)

        import unicodedata
        def normalize_nome(nome):
            # Rimuove accenti e caratteri speciali, trasforma in minuscolo
            replacements = {
                "ć": "c", "č": "c", "š": "s", "ž": "z", "đ": "d", "ñ": "n",
                "á": "a", "à": "a", "ä": "a", "â": "a", "ã": "a", "å": "a",
                "é": "e", "è": "e", "ë": "e", "ê": "e",
                "í": "i", "ì": "i", "ï": "i", "î": "i",
                "ó": "o", "ò": "o", "ö": "o", "ô": "o", "õ": "o",
                "ú": "u", "ù": "u", "ü": "u", "û": "u",
                "ý": "y", "ÿ": "y",
                "ř": "r", "ł": "l", "ß": "ss", "ø": "o", "œ": "oe",
                "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"
            }
            for k, v in replacements.items():
                nome = nome.replace(k, v)
            nome = unicodedata.normalize('NFKD', nome)
            nome = ''.join([c for c in nome if not unicodedata.combining(c)])
            return nome.lower().replace('.', '').replace('-', ' ').replace("'", " ").strip()

        def estrai_cognome_iniziale(nome):
            # Gestisce "Milinkovic-Savic V." -> (Milinkovic-Savic, V)
            nome = nome.replace('.', '').strip()
            parti = nome.split()
            if len(parti) == 2:
                if len(parti[1]) == 1:
                    return parti[0], parti[1]  # Cognome, Iniziale
                else:
                    return parti[1], parti[0][0]  # Cognome, Iniziale da nome
            elif len(parti) == 1:
                return parti[0], ''
            else:
                # Più di due parti: prendi l'ultima come iniziale se è una lettera
                if len(parti[-1]) == 1:
                    return ' '.join(parti[:-1]), parti[-1]
                else:
                    return ' '.join(parti), ''

        def match_nome(nome_ricerca, squadra_ricerca, righe_csv):
            nome_ricerca_norm = normalize_nome(nome_ricerca)
            cognome_ric, iniziale_ric = estrai_cognome_iniziale(nome_ricerca)
            cognome_ric_norm = normalize_nome(cognome_ric)
            squadra_ric_norm = squadra_ricerca.lower().strip()
            risultati = []
            for row in righe_csv:
                nome_csv = row.get('name', '').strip()
                squadra_csv = row.get('team', '').strip().lower()
                nome_csv_norm = normalize_nome(nome_csv)
                # Match squadra
                if squadra_ric_norm in squadra_csv:
                    # Match diretto
                    if nome_csv_norm == nome_ricerca_norm:
                        risultati.append(row)
                        continue
                    # Match su cognome e iniziale
                    if cognome_ric_norm in nome_csv_norm:
                        if iniziale_ric:
                            # Cerca iniziale nel nome
                            if iniziale_ric.lower() in nome_csv_norm:
                                risultati.append(row)
                                continue
                        else:
                            risultati.append(row)
                            continue
                    # Match invertito: "Vanja Milinkovic-Savic" vs "Milinkovic-Savic V."
                    parti_csv = nome_csv_norm.split()
                    if cognome_ric_norm in parti_csv:
                        if iniziale_ric:
                            if any(p.startswith(iniziale_ric.lower()) for p in parti_csv):
                                risultati.append(row)
                                continue
                        else:
                            risultati.append(row)
                            continue
            return risultati

    # Per ogni riga del CSV, crea chiave e data
    for row in righe_csv:
        nome_csv = row.get('name', '').strip()
        squadra_csv = row.get('team', '').strip()
        dob = row.get('dateOfBirth', '').strip()
        if nome_csv and squadra_csv and dob:
            try:
                dt = datetime.strptime(dob, "%Y-%m-%d")
                dob_str = dt.strftime("%d%m%Y")
            except Exception:
                dob_str = "00000000"
            chiave = f"{nome_csv} ({squadra_csv})"
            dob_dict[chiave] = dob_str

    # Funzione per trovare la data di nascita per una chiave di ricerca
    def cerca_dob_per_chiave(chiave, righe_csv):
        # chiave: "Nome Cognome (Squadra)"
        if not chiave.endswith(")"):
            return None
        nome_ricerca, squadra_ricerca = chiave[:-1].split(" (")
        risultati = match_nome(nome_ricerca, squadra_ricerca, righe_csv)
        if risultati:
            dob = risultati[0].get('dateOfBirth', '').strip()
            try:
                dt = datetime.strptime(dob, "%Y-%m-%d")
                dob_str = dt.strftime("%d%m%Y")
            except Exception:
                dob_str = "00000000"
            return dob_str
        return None

    # Ritorna anche una funzione di ricerca per chiavi custom
    dob_dict['__cerca_dob_per_chiave__'] = lambda chiave: cerca_dob_per_chiave(chiave, righe_csv)
    return dob_dict

def carica_db(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salva_db(path, db):
    # Rimuovi eventuali chiavi non serializzabili
    if '__cerca_dob_per_chiave__' in db:
        db = dict(db)
        db.pop('__cerca_dob_per_chiave__')
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def giocatori_mancanti(giocatori, dob_db):
    chiavi = [f"{r['nome'].strip()} ({r['squadra'].strip()})" for _, r in giocatori.iterrows()]
    mancanti = [k for k in chiavi if k not in dob_db or not dob_db[k] or dob_db[k] == "00000000"]
    return mancanti

def get_dob_batch_from_gemini(nomi_squadre, api_key):
    # nomi_squadre: lista di tuple (nome, squadra, ruolo)
    ruolo_map = {"P": "Portiere", "D": "Difensore", "C": "Centrocampista", "A": "Attaccante"}
    lista = "\n".join([f"{n} ({s}) - {ruolo_map.get(r, r)}" for n, s, r in nomi_squadre])
    prompt = (
        "Per ciascun giocatore della seguente lista, restituisci la data di nascita in formato ddmmyyyy. "
        "Rispondi solo con un oggetto JSON dove la chiave è il nome completo (con squadra tra parentesi) e il valore è la data di nascita.\n"
        "Il ruolo è fornito solo per aiutarti nella ricerca, NON inserirlo nella chiave del JSON.\n"
        "I giocatori militano tutti nel Campionato italiano di Seria A 2025-2026, quindi attieniti solo ai giocatori di quella stagione.\n"
        "Utilizza fonti attendibili come i siti della lega seria a, transfermarkt o fantacalcio.it.\n"
        f"Lista giocatori:\n{lista}"
    )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=[prompt]
    )
    risposta = response.text.strip()
    if risposta.startswith("```json"):
        risposta = risposta[7:]
        if risposta.endswith("```"):
            risposta = risposta[:-3]
    risposta = risposta.strip()
    try:
        dob_dict = json.loads(risposta)
    except Exception:
        dob_dict = {}
    return dob_dict

def genera_file_under(giocatori, dob_db, eta_limite, oggi, output_dir):
    under_ids = []
    # Trova le colonne corrette per nome e squadra
    col_nome = None
    col_squadra = None
    for c in giocatori.columns:
        if str(c).lower() in ["nome", "name"]:
            col_nome = c
        if str(c).lower() in ["squadra", "team"]:
            col_squadra = c
    if not col_nome or not col_squadra:
        raise KeyError("Colonne 'nome'/'squadra' non trovate nel file delle quotazioni.")
    # Trova la colonna id
    col_id = None
    for c in giocatori.columns:
        if str(c).lower() in ["id", "ID", "Id"]:
            col_id = c
            break
    if not col_id:
        raise KeyError("Colonna 'id' non trovata nel file delle quotazioni.")
    for _, r in giocatori.iterrows():
        chiave = f"{str(r[col_nome]).strip()} ({str(r[col_squadra]).strip()})"
        dob_str = dob_db.get(chiave)
        if not dob_str or dob_str == "00000000":
            continue
        try:
            dob_dt = datetime.strptime(dob_str, "%d%m%Y")
        except Exception:
            continue
        # Escludi date di nascita future
        if dob_dt > oggi:
            continue
        eta = oggi.year - dob_dt.year - ((oggi.month, oggi.day) < (dob_dt.month, dob_dt.day))
        if eta < 0:
            continue
        if eta < eta_limite:
            under_ids.append(int(r[col_id]))
    out = {
        "date": int(datetime.now().timestamp() * 1000),
        "name": f"Under {eta_limite} al {oggi.strftime('%d-%m-%Y')}",
        "playersId": under_ids
    }
    out_file = os.path.join(output_dir, f"Under {eta_limite} al {oggi.strftime('%d-%m-%Y')}.fclist")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return out_file, len(under_ids)


def main():
        st.set_page_config(page_title="Genera Under Fantacalcio", layout="wide")
        st.title("Generatore Under Fantacalcio")
        output_dir = os.path.dirname(os.path.abspath(__file__))
        dob_db_file = os.path.join(output_dir, "dob_db.json")
        oggi = datetime(2025, 7, 1)
        # Multipagina
        uploaded_file = st.file_uploader("Carica il file delle quotazioni (Quotazioni_Fantacalcio_Stagione_2025_26.xlsx)", type=["xlsx"], key="file_quotazioni")
        if uploaded_file is None:
            st.info("Carica il file delle quotazioni per accedere alle funzionalità.")
            st.stop()
        giocatori = carica_quotazioni(uploaded_file)
        dob_db = carica_db(dob_db_file)
        pagina = st.sidebar.radio("Seleziona pagina", ["Gestione giocatori", "Genera file Under"])
        if pagina == "Gestione giocatori":
            st.write("## Gestione giocatori e date di nascita")
            col1, col2, col3 = st.columns([2,2,2])
            metric1 = col1.empty()
            metric2 = col2.empty()
            aggiorna_metriche = False
            if st.button("Recupera date dal CSV Serie A", key="csv"):
                dob_db_csv = carica_dob_da_csv(os.path.join(output_dir, file_csv_fd))
                trovati = 0
                dob_db_temp = dict(dob_db)
                for _, r in giocatori.iterrows():
                    chiave_excel = f"{r['nome'].strip()} ({r['squadra'].strip()})"
                    dob = dob_db_csv.get(chiave_excel)
                    if not dob and '__cerca_dob_per_chiave__' in dob_db_csv:
                        dob = dob_db_csv['__cerca_dob_per_chiave__'](chiave_excel)
                    if dob and dob != "00000000":
                        trovati += 1
                        dob_db_temp[chiave_excel] = dob
                dob_db = dob_db_temp
                salva_db(dob_db_file, dob_db)
                st.success(f"Recupero dal CSV completato: {trovati} giocatori trovati e salvati su dob_db.json.")
                aggiorna_metriche = True
            dob_db = carica_db(dob_db_file)
            mancanti = giocatori_mancanti(giocatori, dob_db)
            totale_giocatori = len(giocatori)
            totale_mancanti = len(mancanti)
            metric1.metric("Totale giocatori", totale_giocatori)
            metric2.metric("Giocatori mancanti in dob_db.json", totale_mancanti)
            # Bottone per esportare Excel con colonna dob
            st.markdown("---")
            if st.button("Esporta Excel con colonna DOB", key="export_excel_dob"):
                # Colonne originali del file quotazioni
                colonne_originali = list(giocatori.columns)
                # Trova le colonne corrette per nome e squadra
                col_nome = None
                col_squadra = None
                for c in giocatori.columns:
                    if str(c).lower() in ["nome", "name"]:
                        col_nome = c
                    if str(c).lower() in ["squadra", "team"]:
                        col_squadra = c
                df_export = giocatori.copy()
                df_export["dob"] = df_export.apply(lambda r: dob_db.get(f"{str(r[col_nome]).strip()} ({str(r[col_squadra]).strip()})", ""), axis=1)
                colonne_finali = colonne_originali + ["dob"]
                df_export = df_export[colonne_finali]
                out_path = os.path.join(output_dir, "Quotazioni_Fantacalcio_con_DOB.xlsx")
                df_export.to_excel(out_path, index=False)
                st.success(f"File esportato: {out_path}")
            with st.expander("Mostra elenco giocatori mancanti", expanded=True):
                if mancanti:
                    st.markdown("---")
                    st.subheader("Associa manualmente le date di nascita tramite ricerca automatica")
                    csv_path_locale = os.path.join(output_dir, file_csv_fd)
                    if os.path.exists(csv_path_locale):
                        df_dob = pd.read_csv(csv_path_locale)
                        df_dob["chiave"] = df_dob.apply(lambda r: f"{str(r.get('name','')).strip()} ({str(r.get('team','')).strip()})", axis=1)
                        dob_lookup = dict(zip(df_dob["chiave"], df_dob["dateOfBirth"]))
                        nomi_autocomplete = df_dob["chiave"].tolist()
                        st.write("Tabella giocatori mancanti: seleziona il nome dal CSV per associare la data di nascita")
                        associazioni = {}
                        for giocatore in mancanti:
                            col1, col2 = st.columns([2,2])
                            col1.markdown(f"**{giocatore}**")
                            selected = col2.selectbox(
                                f"Cerca e seleziona per {giocatore}",
                                options=[""] + nomi_autocomplete,
                                index=0,
                                key=f"autocomplete_{giocatore}"
                            )
                            dob_val = dob_lookup.get(selected, "") if selected else ""
                            associazioni[giocatore] = dob_val
                        if st.button("Salva associazioni manuali", key="save_manual_dob"):
                            dob_db_temp = dict(dob_db)
                            n_salvati = 0
                            for chiave, dob_str in associazioni.items():
                                dob_str = dob_str.strip()
                                if dob_str and dob_str != "00000000":
                                    dob_db_temp[chiave] = dob_str
                                    n_salvati += 1
                            salva_db(dob_db_file, dob_db_temp)
                            st.success(f"Associazioni salvate su dob_db.json! ({n_salvati} giocatori aggiornati)")
                            dob_db = carica_db(dob_db_file)
                            mancanti = giocatori_mancanti(giocatori, dob_db)
                            totale_giocatori = len(giocatori)
                            totale_mancanti = len(mancanti)
                            metric1.metric("Totale giocatori", totale_giocatori)
                            metric2.metric("Giocatori mancanti in dob_db.json", totale_mancanti)
                else:
                    st.write("Nessun giocatore mancante!")
            api_key = st.text_input("Gemini API Key", type="password", value="")
            if st.button("Recupera date mancanti con Gemini AI", key="gemini", disabled=(totale_mancanti==0 or not api_key)):
                with st.spinner("Recupero date di nascita mancanti..."):
                    for i in range(0, totale_mancanti, 25):
                        batch = mancanti[i:i+100]
                        nomi_squadre = []
                        for k in batch:
                            nome, resto = k.split(" (")
                            squadra = resto[:-1]
                            riga = giocatori[(giocatori["nome"].str.strip() == nome.strip()) & (giocatori["squadra"].str.strip() == squadra.strip())]
                            if not riga.empty:
                                ruolo = riga.iloc[0]["ruolo"]
                            else:
                                ruolo = "?"
                            nomi_squadre.append((nome, squadra, ruolo))
                        dob_dict_gemini = get_dob_batch_from_gemini(nomi_squadre, api_key)
                        dob_db.update(dob_dict_gemini)
                        salva_db(dob_db_file, dob_db)
                    dob_db = carica_db(dob_db_file)
                    mancanti = giocatori_mancanti(giocatori, dob_db)
                    totale_mancanti = len(mancanti)
                    metric1.metric("Totale giocatori", totale_giocatori)
                    metric2.metric("Giocatori mancanti in dob_db.json", totale_mancanti)
                    st.success(f"Recupero completato. Giocatori ancora mancanti: {totale_mancanti}")
        elif pagina == "Genera file Under":
            st.write("## Generazione file Under")
            eta_limite = st.number_input("Inserisci l'età limite (es. 21, 23)", min_value=1, max_value=40, value=21)
            oggi = datetime(2025, 7, 1)
            data_rif = st.date_input("Data di riferimento per il calcolo età", value=oggi.date())
            if st.button("Genera file Under", key="genera_under_btn"):
                oggi_rif = datetime.combine(data_rif, datetime.min.time())
                out_file, n_giocatori = genera_file_under(giocatori, dob_db, eta_limite, oggi_rif, output_dir)
                st.success(f"File creato: {out_file} ({n_giocatori} giocatori)")
                # Esporta anche in formato Excel
                under_rows = []
                # Trova le colonne corrette per nome e squadra
                col_nome = None
                col_squadra = None
                colonne_originali = list(giocatori.columns)
                for c in giocatori.columns:
                    if str(c).lower() in ["nome", "name"]:
                        col_nome = c
                    if str(c).lower() in ["squadra", "team"]:
                        col_squadra = c
                if not col_nome or not col_squadra:
                    raise KeyError("Colonne 'nome'/'squadra' non trovate nel file delle quotazioni.")
                for _, r in giocatori.iterrows():
                    chiave = f"{str(r[col_nome]).strip()} ({str(r[col_squadra]).strip()})"
                    dob_str = dob_db.get(chiave)
                    if not dob_str or dob_str == "00000000":
                        continue
                    try:
                        dob_dt = datetime.strptime(dob_str, "%d%m%Y")
                    except Exception:
                        continue
                    # Escludi date di nascita future
                    if dob_dt > oggi_rif:
                        continue
                    eta = oggi_rif.year - dob_dt.year - ((oggi_rif.month, oggi_rif.day) < (dob_dt.month, dob_dt.day))
                    if eta < 0:
                        continue
                    if eta < eta_limite:
                        row = dict(r)
                        row["dob"] = dob_str
                        row["età"] = eta
                        under_rows.append(row)
                if under_rows:
                    df_under = pd.DataFrame(under_rows)
                    colonne_finali = colonne_originali + ["dob", "età"]
                    df_under = df_under[colonne_finali]
                    out_excel = os.path.join(output_dir, f"Under_{eta_limite}_al_{oggi_rif.strftime('%d-%m-%Y')}.xlsx")
                    df_under.to_excel(out_excel, index=False)
                    st.success(f"File Excel Under esportato: {out_excel}")

if __name__ == "__main__":
    main()
