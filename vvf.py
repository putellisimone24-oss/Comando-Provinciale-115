import streamlit as st
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta

# =========================================================
# 1. DATABASE VVF (INTERVENTI SPECIFICI)
# =========================================================
def init_db_vvf_completo():
    conn = sqlite3.connect('centrale_vvf_comando.db')
    c = conn.cursor()
    
    # Tabella Mezzi
    c.execute('''CREATE TABLE IF NOT EXISTS mezzi_vvf 
                 (id TEXT PRIMARY KEY, tipo TEXT, sede TEXT, stato TEXT, 
                  litri_attuali INTEGER, litri_max INTEGER, ora_arrivo_stimata TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM mezzi_vvf")
    if c.fetchone()[0] == 0:
        mezzi = [
            ('APS 1', 'AutoPompa Serbatoio', 'Centrale', 'In Sede', 3200, 3200, ''),
            ('APS 2', 'AutoPompa Serbatoio', 'Centrale', 'In Sede', 3200, 3200, ''),
            ('ABP 1', 'AutoBotte', 'Centrale', 'In Sede', 8000, 8000, ''),
            ('AS 1', 'AutoScala', 'Centrale', 'In Sede', 0, 0, ''),
            ('AG 1', 'AutoGru', 'Centrale', 'In Sede', 0, 0, ''),
            ('ACTE 1', 'Carro Telo', 'Centrale', 'In Sede', 0, 0, ''),
            ('Vf 1', 'Vettura Comando', 'Centrale', 'In Sede', 0, 0, '')
        ]
        c.executemany("INSERT INTO mezzi_vvf VALUES (?,?,?,?,?,?,?)", mezzi)
    
    # Tabella Interventi
    c.execute('''CREATE TABLE IF NOT EXISTS interventi_vvf 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, tipologia TEXT, comune TEXT, 
                  indirizzo TEXT, stato TEXT, ora_inizio TEXT)''')
    conn.commit()
    conn.close()

init_db_vvf_completo()

# =========================================================
# 2. LOGICA AUTOMATICA (TIMER E ARRIVO)
# =========================================================
def aggiorna_logistica():
    conn = sqlite3.connect('centrale_vvf_comando.db')
    c = conn.cursor()
    ora_attuale = datetime.now().strftime("%H:%M:%S")
    # Passaggio automatico da viaggio a sul posto
    c.execute("UPDATE mezzi_vvf SET stato='Sul Posto' WHERE stato='In Viaggio' AND ora_arrivo_stimata <= ?", (ora_attuale,))
    conn.commit()
    conn.close()

aggiorna_logistica()

# =========================================================
# 3. SIDEBAR - STATO MEZZI E RIENTRO
# =========================================================
with st.sidebar:
    st.title("👨‍🚒 Monitoraggio 115")
    
    conn = sqlite3.connect('centrale_vvf_comando.db')
    df_m = pd.read_sql_query("SELECT * FROM mezzi_vvf", conn)
    conn.close()

    for _, m in df_m.iterrows():
        status_color = "🟢" if m['stato'] == "In Sede" else ("🟡" if m['stato'] == "In Viaggio" else "🔴")
        with st.expander(f"{status_color} {m['id']} - {m['stato']}"):
            if m['litri_max'] > 0:
                st.write(f"💧 Acqua: {m['litri_attuali']}/{m['litri_max']} L")
            
            if m['stato'] != "In Sede":
                if st.button(f"🔙 Rientro {m['id']}", key=f"btn_r_{m['id']}"):
                    conn = sqlite3.connect('centrale_vvf_comando.db')
                    conn.execute("UPDATE mezzi_vvf SET stato='In Sede', litri_attuali=litri_max, ora_arrivo_stimata='' WHERE id=?", (m['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

# =========================================================
# 4. CENTRALE OPERATIVA - GLI INTERVENTI VVF
# =========================================================
st.title("📟 Sala Operativa Comando VVF")

# --- NUOVA CHIAMATA DI SOCCORSO ---
with st.container(border=True):
    st.subheader("📝 Nuova Scheda Intervento")
    c1, c2, c3 = st.columns(3)
    with c1:
        tipo_scen = st.selectbox("Tipologia Intervento", [
            "Incendio Civile", 
            "Incendio Boschivo", 
            "Incidente Stradale", 
            "Soccorso Persona (Porta)", 
            "Apertura Porta",
            "Allagamento / Danni Acqua",
            "Recupero Mezzi Pesanti",
            "Fuga Gas"
        ])
    with c2: com_scen = st.text_input("Comune")
    with c3: via_scen = st.text_input("Indirizzo")

    st.write("**Composizione Colonna Mobile:**")
    mezzi_liberi = df_m[df_m['stato'] == 'In Sede']['id'].tolist()
    invio_squadre = st.multiselect("Seleziona Squadre da Allarmare", mezzi_liberi)

    if st.button("🚨 ALLARMA E INVIA", type="primary", use_container_width=True):
        if invio_squadre and com_scen:
            ora_partenza = datetime.now()
            # Simulazione: arrivo in 2 minuti
            ora_arrivo = (ora_partenza + timedelta(minutes=2)).strftime("%H:%M:%S")
            
            conn = sqlite3.connect('centrale_vvf_comando.db')
            conn.execute("INSERT INTO interventi_vvf (tipologia, comune, indirizzo, stato, ora_inizio) VALUES (?,?,?,?,?)",
                         (tipo_scen, com_scen, via_scen, 'APERTO', ora_partenza.strftime("%H:%M")))
            
            for m_id in invio_squadre:
                conn.execute("UPDATE mezzi_vvf SET stato='In Viaggio', ora_arrivo_stimata=? WHERE id=?", (ora_arrivo, m_id))
            conn.commit()
            conn.close()
            st.success(f"Squadre allarmate per {tipo_scen}! Arrivo stimato h {ora_arrivo}")
            time.sleep(1)
            st.rerun()

# --- GESTIONE IDRICA E SUL POSTO ---
st.divider()
st.subheader("🚒 Operazioni Tecniche sul Posto")

mezzi_attivi = df_m[df_m['stato'] == 'Sul Posto']
if not mezzi_attivi.empty:
    for _, m in mezzi_attivi.iterrows():
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            st.write(f"### {m['id']}")
            st.caption(f"Tipo: {m['tipo']}")
        with col_m2:
            if m['litri_max'] > 0:
                st.progress(m['litri_attuali'] / m['litri_max'], text=f"{m['litri_attuali']} Litri rimanenti")
                if m['litri_attuali'] > 0:
                    if st.button(f"💧 Apri Mandata (Eroga 400L) - {m['id']}"):
                        conn = sqlite3.connect('centrale_vvf_comando.db')
                        conn.execute("UPDATE mezzi_vvf SET litri_attuali = MAX(0, litri_attuali - 400) WHERE id=?", (m['id'],))
                        conn.commit()
                        conn.close()
                        st.rerun()
                else:
                    st.error(f"⚠️ {m['id']} HA ESAURITO L'ACQUA!")
            else:
                st.info(f"Mezzo di supporto tecnico (Niente serbatoio)")
else:
    st.info("In attesa che le squadre arrivino sullo scenario o che vengano inviate nuove squadre.")
