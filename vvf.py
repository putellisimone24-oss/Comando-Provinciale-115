import streamlit as st
import pandas as pd
import random
import math
import time
import sqlite3
from datetime import datetime
from pymilvus import MilvusClient

# =========================================================
# 1. CONNESSIONE ZILLIZ CLOUD (PONTE SOREU)
# =========================================================
ZILLIZ_URI = "https://in03-c0c7c2467e80acb.serverless.aws-eu-central-1.cloud.zilliz.com" 
ZILLIZ_TOKEN = "bfe6a9e62b37468484ab4481ef5d061448733ee5007d3a8db97579d86c5f128459d008778e621b1ef6685860847ab1b2f9d482dc"

# Inizializziamo il client subito all'avvio
try:
    client = MilvusClient(uri=ZILLIZ_URI, token=ZILLIZ_TOKEN)
except Exception as e:
    st.error(f"Errore connessione Zilliz: {e}")

def init_zilliz_ponte():
    try:
        if not client.has_collection("richieste_vvf_soreu"):
            client.create_collection(
                collection_name="richieste_vvf_soreu",
                dimension=2, 
                primary_field_name="id",
                id_type="int",
                auto_id=True
            )
    except:
        pass

# =========================================================
# 2. DATABASE LOCALE E INIZIALIZZAZIONE
# =========================================================
def init_db_vvf():
    conn = sqlite3.connect('centrale_unica.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS utenti 
                 (username TEXT PRIMARY KEY, password TEXT, cambio_obbligatorio INTEGER, ruolo TEXT)''')
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

# Avvio DB
init_db_vvf()
init_zilliz_ponte()

# =========================================================
# 3. CONFIGURAZIONE E SESSIONE
# =========================================================
st.set_page_config(page_title="Comando Provinciale VVF - 115", layout="wide")

if 'utente_connesso' not in st.session_state: st.session_state.utente_connesso = None
if 'ruolo' not in st.session_state: st.session_state.ruolo = None

# --- LOGICA LOGIN ---
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
# 4. DATABASE MEZZI E SCENARI
# =========================================================
if 'database_mezzi_vvf' not in st.session_state:
    st.session_state.database_mezzi_vvf = {
        "APS Bergamo 1": {"stato": "In Sede", "tipo": "APS", "sede": "Bergamo Centrale", "lat": 45.6891, "lon": 9.6631},
        "AS Bergamo 1": {"stato": "In Sede", "tipo": "AS", "sede": "Bergamo Centrale", "lat": 45.6891, "lon": 9.6631},
        "APS Treviglio 1": {"stato": "In Sede", "tipo": "APS", "sede": "Treviglio", "lat": 45.5268, "lon": 9.5912},
        "ABP Treviglio 1": {"stato": "In Sede", "tipo": "ABP", "sede": "Treviglio", "lat": 45.5268, "lon": 9.5912},
        "BOSCHIVO Treviglio": {"stato": "In Sede", "tipo": "AIB", "sede": "Treviglio", "lat": 45.5268, "lon": 9.5912},
        "APS Romano 1": {"stato": "In Sede", "tipo": "APS", "sede": "Romano di L.", "lat": 45.5133, "lon": 9.7544},
        "APS Brescia 1": {"stato": "In Sede", "tipo": "APS", "sede": "Brescia Centrale", "lat": 45.5469, "lon": 10.2015},
        "ABP Brescia 1": {"stato": "In Sede", "tipo": "ABP", "sede": "Brescia Centrale", "lat": 45.5469, "lon": 10.2015},
        "APS Chiari 1": {"stato": "In Sede", "tipo": "APS", "sede": "Chiari", "lat": 45.5385, "lon": 9.9288},
    }

scenari_vvf = [
    {"titolo": "Incendio Civile", "mezzi_req": ["APS", "AS"]},
    {"titolo": "Incidente Stradale", "mezzi_req": ["APS"]},
    {"titolo": "Incendio Boschivo", "mezzi_req": ["APS", "AIB"]},
    {"titolo": "Apertura Porta", "mezzi_req": ["APS"]},
    {"titolo": "Allagamento", "mezzi_req": ["APS"]}
]

# Inizializzazione variabili sessione
if 'missioni_vvf_attive' not in st.session_state: st.session_state.missioni_vvf_attive = {}
if 'evento_vvf_corrente' not in st.session_state: st.session_state.evento_vvf_corrente = None
if 'next_vvf_mission' not in st.session_state: st.session_state.next_vvf_mission = time.time() + 300

# Automazione missioni
if time.time() > st.session_state.next_vvf_mission:
    sce_auto = random.choice(scenari_vvf)
    st.session_state.evento_vvf_corrente = {
        "tipo": sce_auto["titolo"],
        "comune": random.choice(["Bergamo", "Brescia", "Treviglio", "Romano di L."]),
        "indirizzo": "Verifica in corso...",
        "lat": 45.6, "lon": 9.7
    }
    st.session_state.next_vvf_mission = time.time() + 300
    st.toast("🚨 NUOVA CHIAMATA 115!")

# =========================================================
# 5. INTERFACCIA
# =========================================================
st.sidebar.title("📟 Sala Operativa 115")
st.sidebar.write(f"Op: {st.session_state.utente_connesso.upper()}")

tab1, tab2 = st.tabs(["📝 Gestione Interventi", "🚒 Stato Mezzi"])

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
                m_disp = [k for k, v in st.session_state.database_mezzi_vvf.items() if v['stato'] == "In Sede"]
                scelti = st.multiselect("Allarma Squadre:", m_disp)
                
                if st.button("🚀 PARTENZA"):
                    m_id = random.randint(1000, 9999)
                    for m in scelti:
                        st.session_state.database_mezzi_vvf[m]['stato'] = "In Intervento"
                    st.session_state.missioni_vvf_attive[m_id] = ev
                    st.session_state.evento_vvf_corrente = None
                    st.rerun()

    with col_map:
        df_map = pd.DataFrame([{"lat": v["lat"], "lon": v["lon"]} for v in st.session_state.database_mezzi_vvf.values()])
        st.map(df_map)

st.divider()

# =========================================================
# 6. IL PONTE CON LA SOREU (ZILLIZ)
# =========================================================
st.subheader("🚑 Collegamento SOREU Alpina (Zilliz Cloud)")

if st.session_state.missioni_vvf_attive:
    for mid, info in st.session_state.missioni_vvf_attive.items():
        with st.container(border=True):
            st.write(f"Intervento #{mid}: **{info['tipo']}** a {info['comune']}")
            
            if st.button(f"🚑 RICHIEDI AMBULANZA PER #{mid}", key=f"btn_{mid}"):
                data_zilliz = [
                    {
                        "vector": [0.1, 0.1],
                        "comune": info['comune'],
                        "indirizzo": info['indirizzo'],
                        "scenario": info['tipo'],
                        "stato": "PENDENTE"
                    }
                ]
                try:
                    client.insert(collection_name="richieste_vvf_soreu", data=data_zilliz)
                    st.success(f"Richiesta sanitaria inviata per intervento #{mid}")
                except Exception as e:
                    st.error(f"Errore Zilliz: {e}")

# Sidebar Rientri
st.sidebar.divider()
for m_nome, m_dati in st.session_state.database_mezzi_vvf.items():
    if m_dati['stato'] != "In Sede":
        if st.sidebar.button(f"🔙 Rientro {m_nome}"):
            st.session_state.database_mezzi_vvf[m_nome]['stato'] = "In Sede"
            st.rerun()
