import streamlit as st
import pandas as pd
import sqlite3
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta

# Refresh ogni 30 secondi per monitorare i mezzi sulla mappa
st_autorefresh(interval=30000, key="map_refresh")

# =========================================================
# 1. DATABASE COORDINATE E MEZZI (BG e BS)
# =========================================================
def init_db_comandi():
    conn = sqlite3.connect('centrale_lombardia_est.db')
    c = conn.cursor()
    
    # Tabella Sedi (Comandi e Distaccamenti)
    c.execute('''CREATE TABLE IF NOT EXISTS sedi_vvf 
                 (nome TEXT PRIMARY KEY, lat REAL, lon REAL, tipo TEXT, comando TEXT)''')
    
    # Tabella Mezzi Reali
    c.execute('''CREATE TABLE IF NOT EXISTS mezzi_vvf 
                 (id TEXT PRIMARY KEY, tipo TEXT, sede TEXT, stato TEXT, ora_arrivo TEXT)''')

    # Popolamento Sedi (Esempio principali)
    sedi = [
        ('Bergamo Centrale', 45.6891, 9.6631, 'Permanente', 'Bergamo'),
        ('Dalmine', 45.6483, 9.6033, 'Permanente', 'Bergamo'),
        ('Zogno', 45.7944, 9.6644, 'Permanente', 'Bergamo'),
        ('Brescia Centrale', 45.5469, 10.2015, 'Permanente', 'Brescia'),
        ('Desenzano', 45.4744, 10.5333, 'Permanente', 'Brescia'),
        ('Darfo Boario', 45.8856, 10.1833, 'Permanente', 'Brescia')
    ]
    c.executemany("INSERT OR IGNORE INTO sedi_vvf VALUES (?,?,?,?,?)", sedi)

    # Popolamento Mezzi (Esempio reale)
    if c.execute("SELECT COUNT(*) FROM mezzi_vvf").fetchone()[0] == 0:
        mezzi = [
            ('APS Bergamo 1', 'AutoPompa', 'Bergamo Centrale', 'In Sede', ''),
            ('AS Bergamo 1', 'AutoScala', 'Bergamo Centrale', 'In Sede', ''),
            ('APS Brescia 1', 'AutoPompa', 'Brescia Centrale', 'In Sede', ''),
            ('ABP Brescia 1', 'AutoBotte', 'Brescia Centrale', 'In Sede', ''),
            ('APS Desenzano 1', 'AutoPompa', 'Desenzano', 'In Sede', '')
        ]
        c.executemany("INSERT OR IGNORE INTO mezzi_vvf VALUES (?,?,?,?,?)", mezzi)
    
    conn.commit()
    conn.close()

init_db_comandi()

# =========================================================
# 2. INTERFACCIA MAPPA INTERATTIVA
# =========================================================
st.title("🗺️ Sala Operativa Interforze VVF (BG-BS)")

conn = sqlite3.connect('centrale_lombardia_est.db')
df_sedi = pd.read_sql_query("SELECT * FROM sedi_vvf", conn)
df_mezzi = pd.read_sql_query("SELECT * FROM mezzi_vvf", conn)
conn.close()

# Creazione Mappa con Folium centrata tra BG e BS
m = folium.Map(location=[45.6, 9.9], zoom_start=9, tiles="cartodbpositron")

for _, sede in df_sedi.iterrows():
    # Conta quanti mezzi sono in sede
    mezzi_in_sede = df_mezzi[(df_mezzi['sede'] == sede['nome']) & (df_mezzi['stato'] == 'In Sede')].shape[0]
    total_mezzi = df_mezzi[df_mezzi['sede'] == sede['nome']].shape[0]
    
    colore = 'green' if mezzi_in_sede > 0 else 'red'
    icona = 'fire-extinguisher' if sede['tipo'] == 'Permanente' else 'home'
    
    folium.Marker(
        [sede['lat'], sede['lon']],
        popup=f"<b>{sede['nome']}</b><br>Mezzi: {mezzi_in_sede}/{total_mezzi}",
        tooltip=sede['nome'],
        icon=folium.Icon(color=colore, icon=icona, prefix='fa')
    ).add_to(m)

# Visualizzazione Mappa
st_folium(m, width=1100, height=500)

# =========================================================
# 3. GESTIONE OPERATIVA
# =========================================================
col_invio, col_status = st.columns([1, 1])

with col_invio:
    st.subheader("🚨 Nuova Partenza")
    with st.form("invio_mezzi"):
        sede_scelta = st.selectbox("Sede di Partenza", df_sedi['nome'].tolist())
        mezzi_disp = df_mezzi[(df_mezzi['sede'] == sede_scelta) & (df_mezzi['stato'] == 'In Sede')]['id'].tolist()
        selezionati = st.multiselect("Mezzi", mezzi_disp)
        destinazione = st.text_input("Località Intervento")
        
        if st.form_submit_button("CONFERMA USCITA"):
            if selezionati:
                conn = sqlite3.connect('centrale_lombardia_est.db')
                for mid in selezionati:
                    conn.execute("UPDATE mezzi_vvf SET stato='In Intervento' WHERE id=?", (mid,))
                conn.commit()
                conn.close()
                st.success(f"Squadre di {sede_scelta} in movimento!")
                st.rerun()

with col_status:
    st.subheader("🚒 Stato Flotta")
    for _, mz in df_mezzi.iterrows():
        status = "🟢" if mz['stato'] == "In Sede" else "🔴"
        st.write(f"{status} **{mz['id']}** ({mz['sede']})")
        if mz['stato'] != "In Sede":
            if st.button(f"Fine Intervento {mz['id']}"):
                conn = sqlite3.connect('centrale_lombardia_est.db')
                conn.execute("UPDATE mezzi_vvf SET stato='In Sede' WHERE id=?", (mz['id'],))
                conn.commit()
                st.rerun()
