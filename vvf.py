import streamlit as st
import pandas as pd
import random
import math
import time
import sqlite3
from datetime import datetime

# =========================================================
# 1. DATABASE E INIZIALIZZAZIONE (ADATTATO VVF)
# =========================================================
def init_db_vvf():
    # USIAMO LO STESSO DB DELLA SOREU PER PARLARCI
    conn = sqlite3.connect('centrale_unica.db')
    c = conn.cursor()
    
    # Tabella Utenti (Gemella della SOREU)
    c.execute('''CREATE TABLE IF NOT EXISTS utenti 
                 (username TEXT PRIMARY KEY, password TEXT, cambio_obbligatorio INTEGER, ruolo TEXT)''')
    
    # TABELLA PONTE: Qui i VVF scrivono per chiedere aiuto alla SOREU
    c.execute('''CREATE TABLE IF NOT EXISTS richieste_sanitarie 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, comune TEXT, indirizzo TEXT, scenario_vvf TEXT, stato TEXT)''')

    c.execute("SELECT COUNT(*) FROM utenti")
    if c.fetchone()[0] == 0:
        utenti_iniziali = [('admin', 'admin', 0, 'Admin'), ('vvf.bergamo', 'vvf', 1, 'Operatore')]
        c.executemany("INSERT INTO utenti VALUES (?,?,?,?)", utenti_iniziali)
    
    conn.commit()
    conn.close()

def get_utente_db(username):
    conn = sqlite3.connect('centrale_unica.db')
    c = conn.cursor()
    c.execute("SELECT username, password, cambio_obbligatorio, ruolo FROM utenti WHERE username=?", (username,))
    res = c.fetchone()
    conn.close()
    return res

init_db_vvf()

# =========================================================
# 2. CONFIGURAZIONE E SESSIONE
# =========================================================
st.set_page_config(page_title="Comando Provinciale VVF - 115", layout="wide")

if 'utente_connesso' not in st.session_state: st.session_state.utente_connesso = None
if 'ruolo' not in st.session_state: st.session_state.ruolo = None
if 'fase_cambio_pw' not in st.session_state: st.session_state.fase_cambio_pw = False

# --- LOGICA LOGIN (IDENTICA ALLA TUA SOREU) ---
if st.session_state.utente_connesso is None:
    st.title("👨‍🚒 Comando Provinciale VVF - Login")
    u_in = st.text_input("Username").lower().strip()
    p_in = st.text_input("Password", type="password")
    if st.button("ACCEDI AL COMANDO", type="primary"):
        user_data = get_utente_db(u_in)
        if user_data and user_data[1] == p_in:
            st.session_state.utente_connesso = u_in
            st.session_state.ruolo = user_data[3]
            st.rerun()
        else: st.error("Accesso negato.")
    st.stop()

# =========================================================
# 3. DATABASE MEZZI VVF (BG + BS)
# =========================================================
if 'database_mezzi_vvf' not in st.session_state:
    st.session_state.database_mezzi_vvf = {
        # DISTACCAMENTI BERGAMO
        "APS Bergamo 1": {"stato": "In Sede", "tipo": "APS", "sede": "Bergamo Centrale", "lat": 45.6891, "lon": 9.6631},
        "AS Bergamo 1": {"stato": "In Sede", "tipo": "AS", "sede": "Bergamo Centrale", "lat": 45.6891, "lon": 9.6631},
        "APS Treviglio 1": {"stato": "In Sede", "tipo": "APS", "sede": "Treviglio", "lat": 45.5268, "lon": 9.5912},
        "ABP Treviglio 1": {"stato": "In Sede", "tipo": "ABP", "sede": "Treviglio", "lat": 45.5268, "lon": 9.5912},
        "BOSCHIVO Treviglio": {"stato": "In Sede", "tipo": "AIB", "sede": "Treviglio", "lat": 45.5268, "lon": 9.5912},
        "APS Romano 1": {"stato": "In Sede", "tipo": "APS", "sede": "Romano di L.", "lat": 45.5133, "lon": 9.7544},
        
        # DISTACCAMENTI BRESCIA
        "APS Brescia 1": {"stato": "In Sede", "tipo": "APS", "sede": "Brescia Centrale", "lat": 45.5469, "lon": 10.2015},
        "ABP Brescia 1": {"stato": "In Sede", "tipo": "ABP", "sede": "Brescia Centrale", "lat": 45.5469, "lon": 10.2015},
        "APS Chiari 1": {"stato": "In Sede", "tipo": "APS", "sede": "Chiari", "lat": 45.5385, "lon": 9.9288},
    }

scenari_vvf = [
    {"titolo": "Incendio Civile", "mezzi_req": ["APS", "AS"], "priorità": "Alta"},
    {"titolo": "Incidente Stradale", "mezzi_req": ["APS"], "priorità": "Alta"},
    {"titolo": "Incendio Boschivo", "mezzi_req": ["APS", "AIB"], "priorità": "Urgente"},
    {"titolo": "Apertura Porta", "mezzi_req": ["APS"], "priorità": "Media"},
    {"titolo": "Allagamento", "mezzi_req": ["APS"], "priorità": "Bassa"}
]

# =========================================================
# 4. INTERFACCIA CENTRALE VVF
# =========================================================
st.sidebar.title("📟 Sala Operativa 115")
st.sidebar.write(f"Operatore: {st.session_state.utente_connesso.upper()}")

# Inizializzazione variabili sessione se non presenti
if 'missioni_vvf_attive' not in st.session_state: st.session_state.missioni_vvf_attive = {}
if 'evento_vvf_corrente' not in st.session_state: st.session_state.evento_vvf_corrente = None

# Timer per missione automatica (Ogni 5 minuti)
if 'next_vvf_mission' not in st.session_state: st.session_state.next_vvf_mission = time.time() + 300

# Controllo se è ora di una nuova missione
if time.time() > st.session_state.next_vvf_mission:
    sce_auto = random.choice(scenari_vvf)
    st.session_state.evento_vvf_corrente = {
        "tipo": sce_auto["titolo"],
        "comune": random.choice(["Bergamo", "Brescia", "Treviglio", "Dalmine"]),
        "indirizzo": "Verifica in corso...",
        "lat": 45.6, "lon": 9.7 # Coordinata approssimativa
    }
    st.session_state.next_vvf_mission = time.time() + 300
    st.toast("🚨 NUOVA CHIAMATA 115!")

# --- LAYOUT PRINCIPALE ---
tab1, tab2 = st.tabs(["📝 Gestione Interventi", "🚒 Stato Colonne Mobili"])

with tab1:
    col_inf, col_map = st.columns([1, 1.5])
    
    with col_inf:
        st.subheader("📋 Scheda Intervento")
        if st.button("🔔 Genera Intervento Manuale"):
            sce = random.choice(scenari_vvf)
            st.session_state.evento_vvf_corrente = {
                "tipo": sce["titolo"], "comune": "Treviglio", "indirizzo": "Via Roma", "lat": 45.52, "lon": 9.59
            }
            st.rerun()

        if st.session_state.evento_vvf_corrente:
            ev = st.session_state.evento_vvf_corrente
            with st.container(border=True):
                st.error(f"⚠️ {ev['tipo'].upper()}")
                st.write(f"📍 {ev['comune']} - {ev['indirizzo']}")
                
                # Selezione mezzi
                m_disp = [k for k, v in st.session_state.database_mezzi_vvf.items() if v['stato'] == "In Sede"]
                scelti = st.multiselect("Seleziona Mezzi da Allarmare:", m_disp)
                
                if st.button("🚀 ALLARMA SQUADRE"):
                    for m in scelti:
                        st.session_state.database_mezzi_vvf[m]['stato'] = "In Intervento"
                        st.session_state.mission_id = random.randint(1000, 9999)
                    st.session_state.missioni_vvf_attive[st.session_state.mission_id] = ev
                    st.session_state.evento_vvf_corrente = None
                    st.rerun()
        else:
            st.info("Nessuna emergenza pendente.")

    with col_map:
        st.subheader("🗺️ Mappa Mezzi")
        df_map = pd.DataFrame([{"lat": v["lat"], "lon": v["lon"]} for v in st.session_state.database_mezzi_vvf.values()])
        st.map(df_map)

st.divider()

# =========================================================
# 5. IL PONTE CON LA SOREU
# =========================================================
st.subheader("🚑 Collegamento SOREU Alpina")
if st.session_state.missioni_vvf_attive:
    for mid, info in st.session_state.missioni_vvf_attive.items():
        with st.expander(f"Intervento #{mid} - {info['tipo']} a {info['comune']}"):
            st.write("Squadre operanti sul posto. Necessaria assistenza sanitaria?")
            
            # TASTO MAGICO: Scrive nel DB della SOREU
            if st.button(f"🚑 RICHIEDI AMBULANZA PER INTERVENTO #{mid}", key=f"req_{mid}"):
                conn = sqlite3.connect('centrale_unica.db')
                conn.execute("INSERT INTO richieste_sanitarie (comune, indirizzo, scenario_vvf, stato) VALUES (?,?,?,?)",
                             (info['comune'], info['indirizzo'], info['tipo'], 'PENDENTE'))
                conn.commit()
                conn.close()
                st.success("Richiesta inviata in SOREU Alpina!")

# Gestione Rientro Mezzi
st.sidebar.divider()
st.sidebar.subheader("Fine Intervento")
for m_nome, m_dati in st.session_state.database_mezzi_vvf.items():
    if m_dati['stato'] != "In Sede":
        if st.sidebar.button(f"🔙 Rientro {m_nome}"):
            st.session_state.database_mezzi_vvf[m_nome]['stato'] = "In Sede"
            st.rerun()
