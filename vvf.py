import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta

# =========================================================
# 1. DATABASE AVANZATO VVF
# =========================================================
def init_db_vvf_pro():
    conn = sqlite3.connect('centrale_vvf_pro.db')
    c = conn.cursor()
    # Aggiunte colonne: litri_attuali, litri_max, ora_arrivo_stimata
    c.execute('''CREATE TABLE IF NOT EXISTS mezzi_vvf 
                 (id TEXT PRIMARY KEY, tipo TEXT, sede TEXT, stato TEXT, 
                  litri_attuali INTEGER, litri_max INTEGER, ora_arrivo_stimata TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM mezzi_vvf")
    if c.fetchone()[0] == 0:
        mezzi = [
            ('APS 1', 'AutoPompa Serbatoio', 'Centrale', 'In Sede', 3000, 3000, ''),
            ('APS 2', 'AutoPompa Serbatoio', 'Distaccamento A', 'In Sede', 3000, 3000, ''),
            ('ABP 1', 'AutoBotte', 'Centrale', 'In Sede', 8000, 8000, ''),
            ('AS 1', 'AutoScala', 'Centrale', 'In Sede', 0, 0, ''),
            ('Vf 1', 'Vettura Comando', 'Centrale', 'In Sede', 0, 0, '')
        ]
        c.executemany("INSERT INTO mezzi_vvf VALUES (?,?,?,?,?,?,?)", mezzi)
    
    c.execute('''CREATE TABLE IF NOT EXISTS interventi_vvf 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tipologia TEXT, comune TEXT, 
                  indirizzo TEXT, stato TEXT, ora_inizio TEXT)''')
    conn.commit()
    conn.close()

init_db_vvf_pro()

# =========================================================
# 2. LOGICA DI CALCOLO TEMPI E RISORSE
# =========================================================
def aggiorna_stati_mezzi():
    """Controlla se i mezzi sono 'In Viaggio' e se sono arrivati sul posto."""
    conn = sqlite3.connect('centrale_vvf_pro.db')
    c = conn.cursor()
    ora_attuale = datetime.now().strftime("%H:%M:%S")
    
    # Se l'ora attuale ha superato l'ora di arrivo stimata, passa da 'In Viaggio' a 'Sul Posto'
    c.execute("UPDATE mezzi_vvf SET stato='Sul Posto' WHERE stato='In Viaggio' AND ora_arrivo_stimata <= ?", (ora_attuale,))
    conn.commit()
    conn.close()

aggiorna_stati_mezzi()

# =========================================================
# 3. SIDEBAR - MONITORAGGIO IDRICO E POSIZIONE
# =========================================================
with st.sidebar:
    st.title("👨‍🚒 Monitoraggio Mezzi")
    
    conn = sqlite3.connect('centrale_vvf_pro.db')
    df_m = pd.read_sql_query("SELECT * FROM mezzi_vvf", conn)
    conn.close()

    for _, m in df_m.iterrows():
        status_icon = "🟢" if m['stato'] == "In Sede" else ("🟡" if m['stato'] == "In Viaggio" else "🔴")
        with st.expander(f"{status_icon} {m['id']} - {m['stato']}"):
            st.write(f"Sede: {m['sede']}")
            if m['litri_max'] > 0:
                perc = int((m['litri_attuali'] / m['litri_max']) * 100)
                st.progress(m['litri_attuali'] / m['litri_max'], text=f"Acqua: {m['litri_attuali']}L ({perc}%)")
            
            # Tasto Rientro: Libera il mezzo e ricarica l'acqua
            if m['stato'] != "In Sede":
                if st.button(f"Fai Rientrare {m['id']}", key=f"re_{m['id']}"):
                    conn = sqlite3.connect('centrale_vvf_pro.db')
                    conn.execute("UPDATE mezzi_vvf SET stato='In Sede', litri_attuali=litri_max, ora_arrivo_stimata='' WHERE id=?", (m['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

# =========================================================
# 4. CENTRALE OPERATIVA 115
# =========================================================
st.title("📟 Comando Provinciale VVF")

# --- NUOVA SCHEDA INTERVENTO ---
with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    with col1: tip = st.selectbox("Scenario", ["Incendio Civile", "Incendio Boschivo", "Incidente Stradale", "Soccorso Tec."])
    with col2: com = st.text_input("Comune")
    with col3: via = st.text_input("Via/Piazza")
    
    mezzi_pronti = df_m[df_m['stato'] == 'In Sede']['id'].tolist()
    invio = st.multiselect("Squadre in Partenza", mezzi_pronti)
    
    if st.button("🚀 ALLARMA SQUADRE", type="primary", use_container_width=True):
        if invio and com:
            ora_partenza = datetime.now()
            # Simuliamo 2 minuti per arrivare (120 secondi)
            ora_arrivo = (ora_partenza + timedelta(minutes=2)).strftime("%H:%M:%S")
            
            conn = sqlite3.connect('centrale_vvf_pro.db')
            conn.execute("INSERT INTO interventi_vvf (tipologia, comune, indirizzo, stato, ora_inizio) VALUES (?,?,?,?,?)",
                         (tip, com, via, 'APERTO', ora_partenza.strftime("%H:%M")))
            
            for m_id in invio:
                conn.execute("UPDATE mezzi_vvf SET stato='In Viaggio', ora_arrivo_stimata=? WHERE id=?", (ora_arrivo, m_id))
            conn.commit()
            conn.close()
            st.success(f"Squadre Allarmate! Arrivo stimato: {ora_arrivo}")
            time.sleep(1)
            st.rerun()

# --- GESTIONE ACQUA DURANTE INTERVENTO ---
st.divider()
st.subheader("🔥 Gestione Idrica e Operazioni")

mezzi_sul_posto = df_m[df_m['stato'] == 'Sul Posto']
if not mezzi_sul_posto.empty:
    cols = st.columns(len(mezzi_sul_posto))
    for i, (_, m) in enumerate(mezzi_sul_posto.iterrows()):
        with cols[i]:
            st.metric(label=f"Acqua {m['id']}", value=f"{m['litri_attuali']} L")
            if m['litri_attuali'] > 0:
                if st.button(f"Eroga 500L ({m['id']})"):
                    nuovi_litri = max(0, m['litri_attuali'] - 500)
                    conn = sqlite3.connect('centrale_vvf_pro.db')
                    conn.execute("UPDATE mezzi_vvf SET litri_attuali=? WHERE id=?", (nuovi_litri, m['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()
            else:
                st.error("⚠️ ACQUA ESAURITA!")
else:
    st.info("In attesa che le squadre arrivino sullo scenario...")