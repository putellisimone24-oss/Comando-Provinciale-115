import streamlit as st
import pandas as pd
import sqlite3
import random
import time
from datetime import datetime, timedelta

# Per il refresh automatico (fondamentale per le missioni automatiche)
# Se non hai la libreria, usa il trucco del meta-refresh o installala
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=30000, key="vvf_auto_refresh") # Ogni 30 secondi controlla il sistema

# =========================================================
# 1. DATABASE E LOGICA GENERAZIONE
# =========================================================
def init_db_vvf():
    conn = sqlite3.connect('centrale_vvf_auto.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mezzi_vvf 
                 (id TEXT PRIMARY KEY, tipo TEXT, stato TEXT, litri_attuali INTEGER, litri_max INTEGER, ora_arrivo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS interventi_vvf 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tipologia TEXT, comune TEXT, indirizzo TEXT, stato TEXT, ora_inizio TEXT)''')
    
    if c.execute("SELECT COUNT(*) FROM mezzi_vvf").fetchone()[0] == 0:
        mezzi = [('APS 1', 'AutoPompa', 'In Sede', 3200, 3200, ''), 
                 ('ABP 1', 'AutoBotte', 'In Sede', 8000, 8000, ''),
                 ('AS 1', 'AutoScala', 'In Sede', 0, 0, ''),
                 ('Vf 1', 'Comando', 'In Sede', 0, 0, '')]
        c.executemany("INSERT INTO mezzi_vvf VALUES (?,?,?,?,?,?)", mezzi)
    conn.commit()
    conn.close()

def genera_missione_automatica():
    """Crea una missione casuale nel database"""
    tipi = ["Incendio Civile", "Incendio Boschivo", "Incidente Stradale", "Fuga Gas", "Soccorso Persona"]
    comuni = ["Sondrio", "Morbegno", "Tirano", "Chiavenna", "Aprica", "Bormio"]
    vie = ["Via Roma", "Piazza Garibaldi", "Via Milano", "S.S. 38", "Via Stelvio"]
    
    t = random.choice(tipi)
    c_res = random.choice(comuni)
    v_res = random.choice(vie)
    ora = datetime.now().strftime("%H:%M")
    
    conn = sqlite3.connect('centrale_vvf_auto.db')
    conn.execute("INSERT INTO interventi_vvf (tipologia, comune, indirizzo, stato, ora_inizio) VALUES (?,?,?,?,?)",
                 (t, c_res, v_res, 'APERTO', ora))
    conn.commit()
    conn.close()

init_db_vvf()

# =========================================================
# 2. LOGICA DI AUTOMAZIONE (IL "MOTORE")
# =========================================================
# Probabilità che nasca una missione ogni 30 secondi (es. 20%)
if random.random() < 0.20: 
    genera_missione_automatica()

# Aggiornamento arrivo mezzi
conn = sqlite3.connect('centrale_vvf_auto.db')
ora_ora = datetime.now().strftime("%H:%M:%S")
conn.execute("UPDATE mezzi_vvf SET stato='Sul Posto' WHERE stato='In Viaggio' AND ora_arrivo <= ?", (ora_ora,))
conn.commit()
conn.close()

# =========================================================
# 3. INTERFACCIA
# =========================================================
st.title("👨‍🚒 Sala Operativa 115 - Comando Provinciale")

# --- SIDEBAR MEZZI ---
with st.sidebar:
    st.header("🚒 Mezzi e Risorse")
    df_m = pd.read_sql_query("SELECT * FROM mezzi_vvf", sqlite3.connect('centrale_vvf_auto.db'))
    for _, m in df_m.iterrows():
        status = "🟢" if m['stato'] == "In Sede" else "🔴"
        st.write(f"{status} **{m['id']}** ({m['stato']})")
        if m['stato'] != "In Sede":
            if st.button(f"Rientro {m['id']}"):
                conn = sqlite3.connect('centrale_vvf_auto.db')
                conn.execute("UPDATE mezzi_vvf SET stato='In Sede', litri_attuali=litri_max WHERE id=?", (m['id'],))
                conn.commit()
                st.rerun()

# --- BLOCCO MISSIONI (IL CUORE) ---
st.subheader("🚨 Richieste di Soccorso in Attesa")

# Tasto manuale
if st.button("📞 GENERA MISSIONE (MANUALE)", type="primary"):
    genera_missione_automatica()
    st.rerun()

conn = sqlite3.connect('centrale_vvf_auto.db')
interventi = pd.read_sql_query("SELECT * FROM interventi_vvf WHERE stato='APERTO' ORDER BY id DESC", conn)
conn.close()

if interventi.empty:
    st.info("Nessuna chiamata pendente. Il sistema monitora le emergenze...")
else:
    for _, intv in interventi.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.error(f"**{intv['tipologia'].upper()}**")
                st.write(f"📍 {intv['comune']} - {intv['indirizzo']} (h {intv['ora_inizio']})")
            
            with col2:
                # Selezione mezzi per questa specifica missione
                mezzi_liberi = df_m[df_m['stato'] == 'In Sede']['id'].tolist()
                scelta = st.multiselect("Invia:", mezzi_liberi, key=f"sel_{intv['id']}")
                if st.button("🚀 INVIA", key=f"go_{intv['id']}"):
                    if scelta:
                        ora_arr = (datetime.now() + timedelta(minutes=1)).strftime("%H:%M:%S")
                        conn = sqlite3.connect('centrale_vvf_auto.db')
                        for mid in scelta:
                            conn.execute("UPDATE mezzi_vvf SET stato='In Viaggio', ora_arrivo=? WHERE id=?", (ora_arr, mid))
                        conn.execute("UPDATE interventi_vvf SET stato='GESTITO' WHERE id=?", (intv['id'],))
                        conn.commit()
                        st.success("Squadre in uscita!")
                        time.sleep(1)
                        st.rerun()
