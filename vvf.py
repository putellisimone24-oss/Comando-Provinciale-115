import streamlit as st
import pandas as pd
import sqlite3
import folium
import random
import time
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

# REFRESH AUTOMATICO: Fondamentale per far "apparire" le missioni ogni 5 minuti
st_autorefresh(interval=30000, key="global_refresh") 

# Nel blocco "Operazioni Tecniche sul Posto" dell'app VVF
if st.button("🚑 RICHIEDI ASSISTENZA SANITARIA"):
    conn = sqlite3.connect('centrale_unica.db')
    conn.execute('''INSERT INTO richieste_sanitarie (comune, indirizzo, scenario_vvf, stato) 
                    VALUES (?, ?, ?, ?)''', 
                 (intv['comune'], intv['indirizzo'], intv['tipologia'], 'PENDENTE'))
    conn.commit()
    conn.close()
    st.toast("Richiesta inviata alla SOREU Alpina!")

# =========================================================
# 1. DATABASE COMPLETO SEDI E MEZZI (BG-BS)
# =========================================================
def init_db_reale():
    conn = sqlite3.connect('centrale_lombardia_est_v2.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS sedi_vvf (nome TEXT PRIMARY KEY, lat REAL, lon REAL, comando TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mezzi_vvf (id TEXT PRIMARY KEY, tipo TEXT, sede TEXT, stato TEXT, ora_arrivo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interventi_vvf (id INTEGER PRIMARY KEY AUTOINCREMENT, tipologia TEXT, comune TEXT, indirizzo TEXT, stato TEXT, ora_inizio TEXT)''')

    # --- ELENCO SEDI REALI ---
    sedi = [
        ('Bergamo Centrale', 45.6891, 9.6631, 'Bergamo'),
        ('Treviglio', 45.5268, 9.5912, 'Bergamo'),
        ('Romano di Lombardia', 45.5133, 9.7544, 'Bergamo'),
        ('Dalmine', 45.6483, 9.6033, 'Bergamo'),
        ('Zogno', 45.7944, 9.6644, 'Bergamo'),
        ('Clusone', 45.8822, 9.9490, 'Bergamo'),
        ('Brescia Centrale', 45.5469, 10.2015, 'Brescia'),
        ('Desenzano del Garda', 45.4744, 10.5333, 'Brescia'),
        ('Chiari', 45.5385, 9.9288, 'Brescia'),
        ('Darfo Boario Terme', 45.8856, 10.1833, 'Brescia'),
        ('Orzinuovi', 45.4056, 9.9285, 'Brescia'),
        ('Salò', 45.6074, 10.5231, 'Brescia')
    ]
    c.executemany("INSERT OR IGNORE INTO sedi_vvf VALUES (?,?,?,?)", sedi)

    # --- PARCO MEZZI DETTAGLIATO (Esempio Reale) ---
    if c.execute("SELECT COUNT(*) FROM mezzi_vvf").fetchone()[0] == 0:
        mezzi = [
            # BERGAMO
            ('APS Bergamo 1', 'AutoPompa', 'Bergamo Centrale', 'In Sede', ''),
            ('ABP Bergamo 1', 'AutoBotte', 'Bergamo Centrale', 'In Sede', ''),
            ('AS Bergamo 1', 'AutoScala', 'Bergamo Centrale', 'In Sede', ''),
            ('APS Treviglio 1', 'AutoPompa', 'Treviglio', 'In Sede', ''),
            ('ABP Treviglio 1', 'AutoBotte', 'Treviglio', 'In Sede', ''),
            ('AS Treviglio 1', 'AutoScala', 'Treviglio', 'In Sede', ''),
            ('AIB Treviglio (Boschivo)', 'Boschivo', 'Treviglio', 'In Sede', ''),
            ('APS Romano 1', 'AutoPompa', 'Romano di Lombardia', 'In Sede', ''),
            ('ABP Romano 1', 'AutoBotte', 'Romano di Lombardia', 'In Sede', ''),
            # BRESCIA
            ('APS Brescia 1', 'AutoPompa', 'Brescia Centrale', 'In Sede', ''),
            ('ABP Brescia 1', 'AutoBotte', 'Brescia Centrale', 'In Sede', ''),
            ('AS Brescia 1', 'AutoScala', 'Brescia Centrale', 'In Sede', ''),
            ('AG Brescia 1', 'AutoGru', 'Brescia Centrale', 'In Sede', ''),
            ('APS Chiari 1', 'AutoPompa', 'Chiari', 'In Sede', ''),
            ('APS Darfo 1', 'AutoPompa', 'Darfo Boario Terme', 'In Sede', '')
        ]
        c.executemany("INSERT OR IGNORE INTO mezzi_vvf VALUES (?,?,?,?,?)", mezzi)
    
    conn.commit()
    conn.close()

# =========================================================
# 2. MOTORE DI AUTOMAZIONE (MISSIONI OGNI 5 MIN)
# =========================================================
def logica_automazione():
    # Gestione Timer per Missioni (ogni 5 minuti = 300 secondi)
    if "next_mission_time" not in st.session_state:
        st.session_state.next_mission_time = time.time() + 100

    if time.time() >= st.session_state.next_mission_time:
        tipi = ["Incendio Civile", "Incendio Boschivo", "Incidente Stradale", "Soccorso Persona", "Fuga Gas"]
        comuni = ["Treviglio", "Bergamo", "Brescia", "Chiari", "Romano di Lombardia", "Dalmine", "Desenzano"]
        
        t = random.choice(tipi)
        c_name = random.choice(comuni)
        ora = datetime.now().strftime("%H:%M")
        
        conn = sqlite3.connect('centrale_lombardia_est_v2.db')
        conn.execute("INSERT INTO interventi_vvf (tipologia, comune, indirizzo, stato, ora_inizio) VALUES (?,?,?,?,?)",
                     (t, c_name, "Coordinate in attesa", "APERTO", ora))
        conn.commit()
        conn.close()
        
        # Reset timer per la prossima missione tra 5 minuti
        st.session_state.next_mission_time = time.time() + 300
        st.toast(f"🚨 NUOVA CHIAMATA: {t} a {c_name}!")

# =========================================================
# 3. INTERFACCIA PRINCIPALE
# =========================================================
init_db_reale()
logica_automazione()

st.set_page_config(layout="wide", page_title="SO 115 BG-BS")
st.title("🖥️ Sala Operativa 115 - Bergamo & Brescia")

# --- MAPPA INTERATTIVA ---
conn = sqlite3.connect('centrale_lombardia_est_v2.db')
df_sedi = pd.read_sql_query("SELECT * FROM sedi_vvf", conn)
df_mezzi = pd.read_sql_query("SELECT * FROM mezzi_vvf", conn)
interventi_attivi = pd.read_sql_query("SELECT * FROM interventi_vvf WHERE stato='APERTO'", conn)
conn.close()

m = folium.Map(location=[45.6, 9.9], zoom_start=9, tiles="cartodbpositron")
for _, s in df_sedi.iterrows():
    m_disponibili = df_mezzi[(df_mezzi['sede'] == s['nome']) & (df_mezzi['stato'] == 'In Sede')].shape[0]
    color = "green" if m_disponibili > 0 else "red"
    folium.Marker([s['lat'], s['lon']], popup=s['nome'], tooltip=f"{s['nome']} (Disp: {m_disponibili})", icon=folium.Icon(color=color, icon='fire', prefix='fa')).add_to(m)

st_folium(m, width="100%", height=400)

# --- GESTIONE INTERVENTI (IN AUTOMATICO E MANUALE) ---
st.divider()
col_sx, col_dx = st.columns([2, 1])

with col_sx:
    st.subheader("🚨 Emergenze in Attesa")
    if interventi_attivi.empty:
        st.info("Monitoraggio sistema attivo. Prossima scansione 112 in corso...")
    else:
        for _, intv in interventi_attivi.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.error(f"**{intv['tipologia'].upper()}** - {intv['comune']}")
                    st.caption(f"Ricevuta h: {intv['ora_inizio']}")
                with c2:
                    # Filtra mezzi per comando (se intervento è a BG, suggerisce mezzi BG)
                    invia_da = st.selectbox("Invia da:", df_sedi['nome'].tolist(), key=f"sede_{intv['id']}")
                    disp = df_mezzi[(df_mezzi['sede'] == invia_da) & (df_mezzi['stato'] == 'In Sede')]['id'].tolist()
                    scelta = st.multiselect("Mezzi:", disp, key=f"m_{intv['id']}")
                    if st.button("🚀 PARTENZA", key=f"go_{intv['id']}"):
                        if scelta:
                            conn = sqlite3.connect('centrale_lombardia_est_v2.db')
                            for mid in scelta:
                                conn.execute("UPDATE mezzi_vvf SET stato='In Intervento' WHERE id=?", (mid,))
                            conn.execute("UPDATE interventi_vvf SET stato='GESTITO' WHERE id=?", (intv['id'],))
                            conn.commit()
                            conn.close()
                            st.rerun()

with col_dx:
    st.subheader("🚒 Stato Sedi")
    for _, s in df_sedi.iterrows():
        m_s = df_mezzi[df_mezzi['sede'] == s['nome']]
        in_sede = m_s[m_s['stato'] == 'In Sede'].shape[0]
        st.write(f"**{s['nome']}**: {in_sede}/{m_s.shape[0]} pronti")
        if st.checkbox("Vedi Mezzi", key=f"check_{s['nome']}"):
            for _, mz in m_s.iterrows():
                ico = "🟢" if mz['stato'] == "In Sede" else "🔴"
                st.write(f"{ico} {mz['id']} ({mz['tipo']})")
                if mz['stato'] != "In Sede":
                    if st.button(f"Rientro {mz['id']}", key=f"rie_{mz['id']}"):
                        conn = sqlite3.connect('centrale_lombardia_est_v2.db')
                        conn.execute("UPDATE mezzi_vvf SET stato='In Sede' WHERE id=?", (mz['id'],))
                        conn.commit()
                        st.rerun()
