import streamlit as st
import pandas as pd
import random
import math
import time
from datetime import datetime

# Configurazione della pagina stile "Control Room"
st.set_page_config(page_title="SOREU Alpina - Simulatore 118", layout="wide")

# Funzione per emettere il suono della centrale (Nuova Chiamata)
def riproduci_suono_allarme():
    audio_url = "https://actions.google.com/sounds/v1/alarms/digital_watch_alarm_long.ogg"
    sound_html = f"""
        <audio autoplay style="display:none;">
            <source src="{audio_url}" type="audio/ogg">
        </audio>
    """
    st.components.v1.html(sound_html, height=0, width=0)

# Funzione per emettere il suono di notifica (Richiesta Ospedale)
def riproduci_suono_notifica():
    audio_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
    sound_html = f"""
        <audio autoplay style="display:none;">
            <source src="{audio_url}" type="audio/ogg">
        </audio>
    """
    st.components.v1.html(sound_html, height=0, width=0)

# 1. DATABASE MEZZI SANITARI & ELI
if 'database_mezzi' not in st.session_state:
    st.session_state.database_mezzi = {
        "CRI_BG_161.C": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.6928, "lon": 9.6428, "tipo": "MSB", "sede": "CRI Bergamo"},
        "CRI_BG_162.C": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.6928, "lon": 9.6428, "tipo": "MSB", "sede": "CRI Bergamo"},
        "CRITRE_124.C": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.5268, "lon": 9.5925, "tipo": "MSB", "sede": "CRI Treviglio"},
        "CRITRE_135.C": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.5532, "lon": 9.6198, "tipo": "MSB", "sede": "CRI Treviglio"},
        "MSA 2 004": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.5220, "lon": 9.5990, "tipo": "MSA", "sede": "Osp. Treviglio"},
        "MSA 1 003": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.5203, "lon": 9.7547, "tipo": "MSA", "sede": "Osp. Romano"},
        "CBBG_014.C": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.6725, "lon": 9.6450, "tipo": "MSB", "sede": "Croce Bianca BG"},
        "CRIHBG_154.C": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.5940, "lon": 9.6910, "tipo": "MSB", "sede": "CRI Urgnano"},
        "CRIDAL_118.C": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.6475, "lon": 9.6012, "tipo": "MSB", "sede": "CRI Dalmine"},
        "HORUS I-LMBD": {"stato": "Libero in Sede", "colore": "🟢", "lat": 45.6710, "lon": 9.7020, "tipo": "ELI", "sede": "Base Elisoccorso Bergamo"}
    }

# 2. DATABASE OSPEDALI E SATURAZIONE
if 'database_ospedali' not in st.session_state:
    st.session_state.database_ospedali = {
        "Osp. Papa Giovanni XXIII (BG)": {"pazienti": 0, "max": 10},
        "Osp. Treviglio-Caravaggio": {"pazienti": 0, "max": 6},
        "Osp. Romano di Lombardia": {"pazienti": 0, "max": 4}
    }

if 'missioni' not in st.session_state: st.session_state.missioni = {}
if 'notifiche_centrale' not in st.session_state: st.session_state.notifiche_centrale = []
if 'registro_radio' not in st.session_state: st.session_state.registro_radio = []
if 'ruolo' not in st.session_state: st.session_state.ruolo = None; st.session_state.mezzo_selezionato = None
if 'evento_corrente' not in st.session_state: st.session_state.evento_corrente = None
if 'last_mission_time' not in st.session_state: st.session_state.last_mission_time = time.time()
if 'time_mult' not in st.session_state: st.session_state.time_mult = 1.0
if 'auto_mode' not in st.session_state: st.session_state.auto_mode = False
if 'suono_riprodotto' not in st.session_state: st.session_state.suono_riprodotto = False

def calcola_distanza_e_tempo(lat1, lon1, lat2, lon2, is_eli=False):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distanza = R * c
    velocita = 220.0 if is_eli else 45.0
    tempo_minuti = round((distanza / velocita) * 60)
    if is_eli: tempo_minuti += 2
    if tempo_minuti < 1: tempo_minuti = 1
    return round(distanza, 1), tempo_minuti

def aggiungi_log_radio(mittente, messaggio):
    orario = datetime.now().strftime("%H:%M:%S")
    st.session_state.registro_radio.insert(0, f"[{orario}] 📻 {mittente}: {messaggio}")

# Gestione AUTOMATICA degli stati a tempo (Durata totale: 4 Minuti)
def aggiorna_stati_automatici():
    now = time.time()
    voci_da_rimuovere = []
    
    for m_nome, miss in st.session_state.missioni.items():
        creazione = miss["timestamp_creazione"]
        db = st.session_state.database_mezzi
        
        fase_stato_1 = 30 / st.session_state.time_mult
        fase_stato_2 = 60 / st.session_state.time_mult
        fase_richiesta_osp = 60 / st.session_state.time_mult
        fase_stato_3 = 120 / st.session_state.time_mult
        fase_stato_4 = 180 / st.session_state.time_mult
        durata_totale = 240 / st.session_state.time_mult
        
        tempo_trascorso = now - creazione
        
        # 0 - 30s: STATO 1
        if tempo_trascorso < fase_stato_1:
            if db[m_nome]["stato"] != "1 - Partenza da sede":
                db[m_nome]["stato"] = "1 - Partenza da sede"
                db[m_nome]["colore"] = "🟡"
                aggiungi_log_radio(m_nome, f"STATO 1: Partenza da sede direzione luogo intervento.")
                
        # 30s - 60s: STATO 2
        elif tempo_trascorso < fase_stato_2:
            if db[m_nome]["stato"] != "2 - Arrivato su posto":
                db[m_nome]["stato"] = "2 - Arrivato su posto"
                aggiungi_log_radio(m_nome, "STATO 2: Arrivati sul luogo dell'evento.")
                
        # 1m (60s): Notifica parametri e richiesta ospedale + SUONO
        elif tempo_trascorso >= fase_richiesta_osp and tempo_trascorso < fase_stato_3:
            if not miss.get("richiesto_ospedale", False):
                fc = random.randint(70, 110)
                pa = random.randint(110, 160)
                st.session_state.notifiche_centrale.append(f"🩺 {m_nome} richiede ospedale! Parametri: PA {pa}/90, FC {fc}.")
                aggiungi_log_radio(m_nome, f"Centrale da {m_nome}: Paziente valutato. Parametri stabili. Richiediamo ospedale di destinazione.")
                
                # Attiviamo il suono di richiesta ospedale
                riproduci_suono_notifica()
                
                st.session_state.missioni[m_nome]["richiesto_ospedale"] = True
                
        # 2m - 3m: STATO 3
        elif tempo_trascorso >= fase_stato_3 and tempo_trascorso < fase_stato_4:
            if db[m_nome]["stato"] != "3 - Partenza per ospedale":
                db[m_nome]["stato"] = "3 - Partenza per ospedale"
                destinazione = miss.get("ospedale_confermato", miss["ospedale_assegnato"])
                aggiungi_log_radio(m_nome, f"STATO 3: Paziente a bordo. Direzione {destinazione}.")
                
        # 3m - 4m: STATO 4
        elif tempo_trascorso >= fase_stato_4 and tempo_trascorso < durata_totale:
            if db[m_nome]["stato"] != "Arrivati in Ospedale":
                db[m_nome]["stato"] = "Arrivati in Ospedale"
                destinazione = miss.get("ospedale_confermato", miss["ospedale_assegnato"])
                aggiungi_log_radio(m_nome, f"Arrivati a destinazione presso {destinazione}.")
                
        # > 4m: Chiusura missione e ritorno libero
        elif tempo_trascorso >= durata_totale:
            db[m_nome]["stato"] = "Libero in Sede"
            db[m_nome]["colore"] = "🟢"
            aggiungi_log_radio(m_nome, f"Terminato scarico paziente. Mezzo LIBERO.")
            
            destinazione = miss.get("ospedale_confermato", miss["ospedale_assegnato"])
            if db[m_nome]["tipo"] == "MSB" and destinazione in st.session_state.database_ospedali:
                if st.session_state.database_ospedali[destinazione]["pazienti"] < st.session_state.database_ospedali[destinazione]["max"]:
                    st.session_state.database_ospedali[destinazione]["pazienti"] += 1
                else:
                    st.session_state.notifiche_centrale.append(f"⚠️ {destinazione} SATURO!")
            
            voci_da_rimuovere.append(m_nome)
            
    for v in voci_da_rimuovere:
        del st.session_state.missioni[v]

if st.session_state.auto_mode and st.session_state.missioni:
    aggiorna_stati_automatici()

database_indirizzi = [
    {"comune": "Bergamo", "via": "Via della Croce Rossa 2", "lat": 45.6928, "lon": 9.6428},
    {"comune": "Bergamo", "via": "Piazza Vecchia", "lat": 45.7042, "lon": 9.6622},
    {"comune": "Treviglio", "via": "Via Roma 12", "lat": 45.5268, "lon": 9.5925},
    {"comune": "Caravaggio", "via": "Piazza del Santuario 1", "lat": 45.5000, "lon": 9.6410},
    {"comune": "Dalmine", "via": "Via Guzzanica 5", "lat": 45.6470, "lon": 9.6100},
]

scenari_evento = [
    {"titolo": "Dolore Toracico", "codice": "ROSSO", "note": "Oppressione al petto."},
    {"titolo": "Incidente Stradale", "codice": "GIALLO", "note": "Scontro auto-moto."},
    {"titolo": "Perdita di coscienza", "codice": "ROSSO", "note": "Non risponde."}
]

tempo_base = 120
tempo_necessario = tempo_base / st.session_state.time_mult
if time.time() - st.session_state.last_mission_time > tempo_necessario:
    if not st.session_state.evento_corrente:
        scelta_indirizzo = random.choice(database_indirizzi)
        scelta_scenario = random.choice(scenari_evento)
        st.session_state.evento_corrente = {
            "comune": scelta_indirizzo["comune"], "via": scelta_indirizzo["via"],
            "lat": scelta_indirizzo["lat"], "lon": scelta_indirizzo["lon"],
            "titolo": scelta_scenario["titolo"], "codice": scelta_scenario["codice"], "note": scelta_scenario["note"]
        }
        st.session_state.last_mission_time = time.time()
        st.session_state.suono_riprodotto = False

col_titolo, col_orologio = st.columns([3, 1])
with col_titolo: st.title("🎧 SOREU Alpina - Sala Operativa")
with col_orologio:
    st.metric(label="🕒 Orario Reale", value=datetime.now().strftime("%H:%M:%S"))

if st.session_state.ruolo is None:
    st.subheader("Seleziona la tua postazione operativa:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎧 ENTRA IN SOREU ALPINA", use_container_width=True): st.session_state.ruolo = "centrale"; st.rerun()
    with col2:
        if st.button("🚑 ENTRA IN UN MEZZO DI SOCCORSO", use_container_width=True): st.session_state.ruolo = "mezzo"; st.rerun()
else:
    if st.sidebar.button("⬅️ Logout / Cambia Ruolo"): st.session_state.ruolo = None; st.session_state.mezzo_selezionato = None; st.rerun()

    # ==================== 🎧 INTERFACCIA SOREU ====================
    if st.session_state.ruolo == "centrale":
        st.sidebar.markdown("### 🎧 Operatore SOREU")
        st.sidebar.subheader("🕹️ Opzioni di Gioco")
        st.session_state.auto_mode = st.sidebar.toggle("🤖 Automatizza Equipaggi", value=st.session_state.auto_mode)
        
        st.sidebar.subheader("⏱️ Cadenza Chiamate")
        vel = st.sidebar.radio("Seleziona velocità", ["Normale", "2X", "5X", "10X"])
        if vel == "Normale": st.session_state.time_mult = 1.0
        elif vel == "2X": st.session_state.time_mult = 2.0
        elif vel == "5X": st.session_state.time_mult = 5.0
        elif vel == "10X": st.session_state.time_mult = 10.0
        
        if st.session_state.notifiche_centrale:
            for notifica in st.session_state.notifiche_centrale: st.toast(notifica, icon="🚑")
            st.session_state.notifiche_centrale = []
            
        tab_invio, tab_risorse, tab_ps = st.tabs(["📝 Nuove Missioni", "🚑 Stato Risorse", "🏥 Monitoraggio PS"])
        
        with tab_invio:
            col_evento, col_mappa = st.columns([1.5, 2])
            
            with col_evento:
                st.header("📋 Ricezione Chiamate")
                if st.button("🔔 Forza Generazione Chiamata", type="primary", use_container_width=True):
                    scelta_indirizzo = random.choice(database_indirizzi)
                    scelta_scenario = random.choice(scenari_evento)
                    st.session_state.evento_corrente = {
                        "comune": scelta_indirizzo["comune"], "via": scelta_indirizzo["via"],
                        "lat": scelta_indirizzo["lat"], "lon": scelta_indirizzo["lon"],
                        "titolo": scelta_scenario["titolo"], "codice": scelta_scenario["codice"], "note": scelta_scenario["note"]
                    }
                    st.session_state.suono_riprodotto = False; st.rerun()
                
                st.divider()
                
                if st.session_state.evento_corrente:
                    if not st.session_state.suono_riprodotto:
                        riproduci_suono_allarme()
                        st.session_state.suono_riprodotto = True

                    ev = st.session_state.evento_corrente
                    st.warning(f"📍 Evento: {ev['titolo']} in {ev['via']}, {ev['comune']}")
                    codice_scelto = st.selectbox("Assegna Codice", ["ROSSO", "GIALLO", "VERDE"], index=["ROSSO", "GIALLO", "VERDE"].index(ev['codice']))
                    
                    st.markdown("### 📏 Calcolo Distanze Mezzi Disponibili")
                    mezzi_calcolo = []
                    for nome, dati in st.session_state.database_mezzi.items():
                        if dati["stato"] == "Libero in Sede":
                            dist, tempo = calcola_distanza_e_tempo(dati["lat"], dati["lon"], ev["lat"], ev["lon"], is_eli=(dati["tipo"] == "ELI"))
                            mezzi_calcolo.append({"Mezzo": nome, "Sede": dati["sede"], "Distanza (km)": dist, "Tempo Arrivo (min)": tempo})
                    
                    if mezzi_calcolo:
                        df_calcolo = pd.DataFrame(mezzi_calcolo).sort_values(by="Tempo Arrivo (min)")
                        st.dataframe(df_calcolo, hide_index=True, use_container_width=True)
                        
                        mezzi_scelti = st.multiselect("Seleziona Mezzi da inviare", df_calcolo["Mezzo"].tolist())
                        osp_selezionato = st.selectbox("Pre-allerta Ospedale", list(st.session_state.database_ospedali.keys()))
                        
                        if st.button("🚀 INVIA MEZZI", type="primary", use_container_width=True) and mezzi_scelti:
                            for m_scelto in mezzi_scelti:
                                if not st.session_state.auto_mode:
                                    st.session_state.database_mezzi[m_scelto]["stato"] = "1 - Partenza da sede"
                                    st.session_state.database_mezzi[m_scelto]["colore"] = "🟡"
                                    aggiungi_log_radio(m_scelto, "STATO 1: Partenza da sede direzione luogo intervento.")
                                
                                st.session_state.missioni[m_scelto] = {
                                    "target": f"{ev['via']}, {ev['comune']}", "lat": ev['lat'], "lon": ev['lon'],
                                    "codice": codice_scelto, "titolo": ev['titolo'], "ospedale_assegnato": osp_selezionato,
                                    "timestamp_creazione": time.time(), "richiesto_ospedale": False
                                }
                            st.session_state.evento_corrente = None; st.rerun()
                    else: st.error("Nessun mezzo Libero in Sede disponibile!")
                else: st.info("In attesa di chiamata da NUE 112...")
                    
            with col_mappa:
                st.header("🗺️ Mappa Area Alpina")
                punti_mappa = []
                for nome, dati in st.session_state.database_mezzi.items(): punti_mappa.append({"lat": dati["lat"], "lon": dati["lon"]})
                if punti_mappa: st.map(pd.DataFrame(punti_mappa), zoom=9)
                
                st.subheader("📻 Registro Radio SOREU")
                if st.session_state.registro_radio:
                    box_testo = "\n".join(st.session_state.registro_radio[:15])
                    st.text_area(label="Comunicazioni Voce", value=box_testo, height=200, disabled=True)
                else: st.info("Nessun traffico radio.")
                
                st.subheader("📋 Missioni in Corso (Assegna Ospedale)")
                if st.session_state.missioni:
                    for m, dati in st.session_state.missioni.items():
                        c_m, c_o = st.columns([2, 1])
                        with c_m: st.write(f"🚑 **{m}** -> {dati['target']} ({st.session_state.database_mezzi[m]['stato']})")
                        with c_o:
                            nuovo_osp = st.selectbox(f"Osp. per {m}", list(st.session_state.database_ospedali.keys()), key=f"sel_osp_{m}")
                            if nuovo_osp != dati.get("ospedale_confermato", dati["ospedale_assegnato"]):
                                st.session_state.missioni[m]["ospedale_confermato"] = nuovo_osp
                                st.toast(f"Ospedale aggiornato per {m} -> {nuovo_osp}")
                else: st.caption("Nessuna missione in corso.")
        
        with tab_risorse:
            st.header("🚑 Stato Risorse Territoriali")
            for m, d in st.session_state.database_mezzi.items(): st.write(f"**{m}** ({d['tipo']}): {d['stato']}")
                
        with tab_ps:
            st.header("🏥 Saturazione Pronto Soccorso")
            for osp, dati in st.session_state.database_ospedali.items():
                col_info, col_azione = st.columns([3, 1])
                with col_info:
                    st.write(f"**{osp}** ({dati['pazienti']} / {dati['max']})")
                    st.progress((dati["pazienti"] / dati["max"]))
                with col_azione:
                    if st.button(f"Libera Posto", key=f"dim_{osp}"):
                        if dati["pazienti"] > 0:
                            st.session_state.database_ospedali[osp]["pazienti"] -= 1; st.rerun()

    # ==================== 🚑 INTERFACCIA MEZZO ====================
    elif st.session_state.ruolo == "mezzo":
        if st.session_state.auto_mode: st.warning("⚠️ La modalità AUTOMATICA è attiva.")
        
        if st.session_state.mezzo_selezionato is None:
            st.subheader("Identificazione Equipaggio")
            scelta = st.radio("Seleziona mezzo:", list(st.session_state.database_mezzi.keys()))
            if st.button("Login"): st.session_state.mezzo_selezionato = scelta; st.rerun()
        else:
            mio_mezzo = st.session_state.mezzo_selezionato
            dati_mezzo = st.session_state.database_mezzi[mio_mezzo]
            st.header(f"Terminale: {mio_mezzo}")
            st.write(f"Stato Attuale: **{dati_mezzo['stato']}**")
            
            st.divider()
            st.subheader("Pulsantiera Operativa Stati Radio")
            in_missione = mio_mezzo in st.session_state.missioni
            miss = st.session_state.missioni[mio_mezzo] if in_missione else None
            
            disabilita_manuale = st.session_state.auto_mode or not in_missione
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("🚨 1 - Partenza Sede", use_container_width=True, disabled=disabilita_manuale):
                    dati_mezzo["stato"] = "1 - Partenza da sede"
                    aggiungi_log_radio(mio_mezzo, "STATO 1: Partenza da sede direzione luogo intervento.")
                    st.rerun()
            with c2:
                if st.button("📍 2 - Arrivo Posto", use_container_width=True, disabled=disabilita_manuale):
                    dati_mezzo["stato"] = "2 - Arrivato su posto"
                    aggiungi_log_radio(mio_mezzo, "STATO 2: Arrivati sul luogo dell'evento.")
                    st.rerun()
            with c3:
                if st.button("🏥 3 - Partenza Ospedale", use_container_width=True, disabled=disabilita_manuale):
                    dati_mezzo["stato"] = "3 - Partenza per ospedale"
                    dest = miss.get("ospedale_confermato", miss["ospedale_assegnato"])
                    aggiungi_log_radio(mio_mezzo, f"STATO 3: Paziente a bordo. Direzione {dest}.")
                    st.rerun()
            with c4:
                if st.button("🏁 4 - Arrivo Ospedale", type="primary", use_container_width=True, disabled=disabilita_manuale):
                    dati_mezzo["stato"] = "Libero in Sede"
                    dati_mezzo["colore"] = "🟢"
                    aggiungi_log_radio(mio_mezzo, "STATO 4: Arrivati a destinazione. Mezzo LIBERO.")
                    
                    dest = miss.get("ospedale_confermato", miss["ospedale_assegnato"])
                    if dest in st.session_state.database_ospedali:
                        st.session_state.database_ospedali[dest]["pazienti"] += 1
                    
                    del st.session_state.missioni[mio_mezzo]
                    st.rerun()
