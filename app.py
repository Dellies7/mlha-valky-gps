from flask import Flask, render_template, jsonify, request
import sqlite3
import os
import math
import time
import random
from werkzeug.security import generate_password_hash, check_password_hash

# --- DEFINICE STROJŮ ---
DEFINICE_STROJU = {
    "pesi": {"nazev": "Pěší chůze", "bonus": 1.0, "req_level": 1, "ikona": "🚶"},
    "ctyrkolka": {"nazev": "Terénní čtyřkolka", "bonus": 1.5, "req_level": 8, "ikona": "🚜"},
    "bugina": {"nazev": "Rychlá bugina", "bonus": 2.0, "req_level": 10, "ikona": "🏎️"},
    "vznasedlo": {"nazev": "Vznášedlo", "bonus": 2.5, "req_level": 12, "ikona": "🛸"}
}

def inicializuj_databazi():
    conn = sqlite3.connect('mlha_db.sqlite')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS uzivatele (id INTEGER PRIMARY KEY AUTOINCREMENT, jmeno TEXT UNIQUE NOT NULL, heslo TEXT NOT NULL, zlato INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS odkryta_mista (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL, FOREIGN KEY (user_id) REFERENCES uzivatele(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zajimavosti (id INTEGER PRIMARY KEY AUTOINCREMENT, nazev TEXT NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL, popis TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zapisnik (id INTEGER PRIMARY KEY AUTOINCREMENT, zajimavost_id INTEGER NOT NULL, user_id INTEGER NOT NULL, vzkaz TEXT NOT NULL, datum TEXT NOT NULL, FOREIGN KEY (zajimavost_id) REFERENCES zajimavosti(id), FOREIGN KEY (user_id) REFERENCES uzivatele(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS hrac_vybaveni (user_id INTEGER, typ TEXT, item_id TEXT, PRIMARY KEY (user_id, typ))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zakoupene_predmety (user_id INTEGER, item_id TEXT, PRIMARY KEY (user_id, item_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS aktivni_buff (user_id INTEGER, item_id TEXT, konec_ts REAL, PRIMARY KEY (user_id, item_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS denni_postup (user_id INTEGER, datum TEXT, truhly INTEGER DEFAULT 0, nakupy INTEGER DEFAULT 0, zapisy INTEGER DEFAULT 0, odmena_vybrana INTEGER DEFAULT 0, PRIMARY KEY (user_id, datum))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS hrac_artefakty (user_id INTEGER, artefakt_id TEXT, PRIMARY KEY (user_id, artefakt_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS hrac_banka (user_id INTEGER PRIMARY KEY, zainvestovano INTEGER DEFAULT 0, posledni_vyber TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS hrac_garaz (user_id INTEGER, dil_id TEXT, PRIMARY KEY (user_id, dil_id))''')
    
    # OPRAVENO: Správná struktura tabulky pro ukládání aktivního stroje
    cursor.execute('''CREATE TABLE IF NOT EXISTS hrac_stroj (user_id INTEGER PRIMARY KEY, aktivni_stroj_id TEXT DEFAULT 'pesi')''')
    
    cursor.execute("SELECT * FROM zajimavosti WHERE nazev = 'Výškový bod Větrník'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO zajimavosti (nazev, lat, lng, popis) VALUES ('Výškový bod Větrník', 48.77814, 14.28116, 'Dosáhl jsi vrcholu Větrník! Zapiš se do zápisníku.')")
    
    conn.commit()
    conn.close()

inicializuj_databazi()

app = Flask(__name__)
DB_PATH = 'mlha_db.sqlite'

def aktualizuj_denni_postup(user_id, sloupec):
    if not user_id: return
    dnes = time.strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO denni_postup (user_id, datum) VALUES (?, ?)", (user_id, dnes))
    cursor.execute(f"UPDATE denni_postup SET {sloupec} = {sloupec} + 1 WHERE user_id = ? AND datum = ?", (user_id, dnes))
    conn.commit()
    conn.close()

# --- DEFINICE HRY ---
DEFINICE_PREDMETU = [
    {"id": "h1", "nazev": "Trenérská kšiltovka", "barva": "#ff1744", "typ": "hlava", "req_level": 1, "cena": 0},
    {"id": "h3", "nazev": "Ochranná přilba", "barva": "#00e5ff", "typ": "hlava", "req_level": 5, "cena": 0},
    {"id": "h_vip", "nazev": "Zlatá svatozář (VIP)", "barva": "#ffea00", "typ": "hlava", "req_level": 1, "cena": 50, "premium": True},
    {"id": "h_cyber", "nazev": "Kyber-helma (VIP)", "barva": "#ff0057", "typ": "hlava", "req_level": 1, "cena": 75, "premium": True},
    {"id": "o1", "nazev": "Sportovní mikina", "barva": "#2979ff", "typ": "telo", "req_level": 1, "cena": 0},
    {"id": "o3", "nazev": "Kybernetický plášť", "barva": "#00e676", "typ": "telo", "req_level": 6, "cena": 0},
    {"id": "o_vip", "nazev": "Královská zbroj (VIP)", "barva": "#ffd700", "typ": "telo", "req_level": 1, "cena": 100, "premium": True},
    {"id": "o_phoenix", "nazev": "Plášť Fénixe (VIP)", "barva": "#ff3d00", "typ": "telo", "req_level": 1, "cena": 120, "premium": True},
    {"id": "d1", "nazev": "Sluneční brýle", "barva": "#ffeb3b", "typ": "oci", "req_level": 2, "cena": 0},
    {"id": "d2", "nazev": "Futuristický vizor", "barva": "#d500f9", "typ": "oci", "req_level": 5, "cena": 0},
    {"id": "z2", "nazev": "Světelný meč", "barva": "#00e5ff", "typ": "ruka", "req_level": 3, "cena": 0},
    {"id": "z3", "nazev": "Bojová sekera", "barva": "#ff3d00", "typ": "ruka", "req_level": 6, "cena": 0},
    {"id": "z_vip", "nazev": "Božský meč (VIP)", "barva": "#ffffff", "typ": "ruka", "req_level": 1, "cena": 150, "premium": True},
    {"id": "z_hammer", "nazev": "Hromové kladivo (VIP)", "barva": "#00e5ff", "typ": "ruka", "req_level": 1, "cena": 160, "premium": True},
    {"id": "a_fire", "nazev": "Ohnivá Aura (VIP)", "barva": "#ff3d00", "typ": "aura", "req_level": 1, "cena": 200, "premium": True},
    {"id": "a_ice", "nazev": "Ledová Aura (VIP)", "barva": "#00e5ff", "typ": "aura", "req_level": 1, "cena": 200, "premium": True},
    {"id": "pet_coon", "nazev": "Mainská mývalí (VIP)", "barva": "#e65100", "typ": "mazlicek", "req_level": 1, "cena": 350, "premium": True},
    {"id": "pet_fox", "nazev": "Ohnivá liška (VIP)", "barva": "#ff3d00", "typ": "mazlicek", "req_level": 1, "cena": 450, "premium": True},
    {"id": "pet_dragon", "nazev": "Malý drak (VIP)", "barva": "#d500f9", "typ": "mazlicek", "req_level": 1, "cena": 500, "premium": True},
    {"id": "pet_owl", "nazev": "Sněžná sova (VIP)", "barva": "#e0f7fa", "typ": "mazlicek", "req_level": 1, "cena": 600, "premium": True},
    {"id": "pet_wolf", "nazev": "Stínový vlk (VIP)", "barva": "#4a148c", "typ": "mazlicek", "req_level": 1, "cena": 800, "premium": True},
    {"id": "pet_robo", "nazev": "Kyber-Dron (VIP)", "barva": "#00e676", "typ": "mazlicek", "req_level": 1, "cena": 1000, "premium": True},
    {"id": "m_dalekohled", "nazev": "Dalekohled (+50m)", "barva": "#00e5ff", "typ": "mapa", "req_level": 2, "cena": 40, "premium": True, "ikona": "fas fa-binoculars"},
    {"id": "m_magnet", "nazev": "Magnet (Sběr na 60m)", "barva": "#ffea00", "typ": "mapa", "req_level": 3, "cena": 60, "premium": True, "ikona": "fas fa-magnet"},
    {"id": "m_radar", "nazev": "Radar (Víc truhel)", "barva": "#ff1744", "typ": "mapa", "req_level": 4, "cena": 80, "premium": True, "ikona": "fas fa-satellite-dish"},
    {"id": "m_double", "nazev": "Zlatá horečka (2x)", "barva": "#ffd700", "typ": "mapa", "req_level": 1, "cena": 70, "premium": True, "ikona": "fas fa-angle-double-up"},
    {"id": "m_stroj_radar", "nazev": "Radar na součástky", "barva": "#00e5ff", "typ": "mapa", "req_level": 8, "cena": 100, "premium": True, "ikona": "fas fa-satellite"},
    {"id": "m_stroj_magnet", "nazev": "Chytrý magnet (Díly)", "barva": "#00e676", "typ": "mapa", "req_level": 8, "cena": 120, "premium": True, "ikona": "fas fa-tools"},
    {"id": "m_art_radar", "nazev": "Hledač artefaktů", "barva": "#ff3d00", "typ": "mapa", "req_level": 6, "cena": 100, "premium": True, "ikona": "fas fa-search-location"},
    {"id": "c_luck", "nazev": "Truhla Štěstěny", "barva": "#ffea00", "typ": "consumable", "req_level": 1, "cena": 100, "premium": True, "ikona": "fas fa-dice"},
]

DEFINICE_MILNIKU = [
    {"id": "m1", "nazev": "První toulky", "popis": "Ujdi celkem 5 km.", "vzdalenost": 5.0, "xp_odmena": 500},
    {"id": "m2", "nazev": "Průzkumnice", "popis": "Ujdi celkem 15 km.", "vzdalenost": 15.0, "xp_odmena": 1200},
    {"id": "m3", "nazev": "Železné nohy", "popis": "Ujdi celkem 30 km.", "vzdalenost": 30.0, "xp_odmena": 2500},
    {"id": "m4", "nazev": "Paní mlhy", "popis": "Ujdi celkem 50 km.", "vzdalenost": 50.0, "xp_odmena": 5000},
]

DEFINICE_ARTEFAKTU = [
    {"id": "a1", "nazev": "Úlomek vltavínu", "popis": "Tajemný zelený kámen. Prý je to pozůstatek dávného dopadu meteoritu.", "ikona": "💎"},
    {"id": "a2", "nazev": "Zrezivělá vojenská známka", "popis": "Připomínka pohnutých událostí, které se zde odehrály v polovině 20. století.", "ikona": "🏷️"},
    {"id": "a3", "nazev": "Ztracený deník", "popis": "Stránky jsou rozmočené, ale inkoust z roku 1945 se dá ještě přečíst.", "ikona": "📔"},
    {"id": "a4", "nazev": "Stará rožmberská pečeť", "popis": "Nalezena v prachu cesty. Nese hrdý znak pětilisté růže.", "ikona": "📜"},
    {"id": "a5", "nazev": "Prasklý kompas", "popis": "Střelka se zběsile točí. Komu asi kdysi ukazoval cestu domů?", "ikona": "🧭"}
]

DEFINICE_DILU = [
    {"id": "d_svicka", "nazev": "Zapalovací svíčka", "ikona": "⚡"},
    {"id": "d_karburator", "nazev": "Karburátor", "ikona": "🛢️"},
    {"id": "d_pist", "nazev": "Kovaný píst", "ikona": "🔩"},
    {"id": "d_retez", "nazev": "Hnací řetěz", "ikona": "⛓️"},
    {"id": "d_ram", "nazev": "Ocelový rám", "ikona": "🛠️"}
]

# --- POMOCNÉ FUNKCE ---
def spocitej_vzdalenost(body):
    if len(body) < 2: return 0.0
    celkem_metru = 0.0
    for i in range(1, len(body)):
        lat1, lon1 = body[i-1][0], body[i-1][1]
        lat2, lon2 = body[i][0], body[i][1]
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        celkem_metru += R * c
    return celkem_metru / 1000.0

def spocti_rpg_stav(user_id):
    if not user_id:
        return {"level": 1, "xp": 0, "xp_potreba": 500, "celkem_xp": 0, "vzdalenost": 0.0, "odemcene_milniky": [], "vybaveni": {}, "mince": 0, "zakoupene": [], "aktivni_buffy": {}, "denni_stav": {"truhly":0, "nakupy":0, "zapisy":0, "odmena_vybrana":0}, "nalezene_artefakty": [], "banka_stav": {"zainvestovano": 0, "lze_vybrat": False}, "nalezene_dily": [], "aktivni_stroj": "pesi"}
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT lat, lng FROM odkryta_mista WHERE user_id = ?", (user_id,))
    body = cursor.fetchall()
    cursor.execute("SELECT zlato FROM uzivatele WHERE id = ?", (user_id,))
    u_row = cursor.fetchone()
    mince = u_row[0] if u_row else 0
    cursor.execute("SELECT typ, item_id FROM hrac_vybaveni WHERE user_id = ?", (user_id,))
    vybaveni = {r[0]: r[1] for r in cursor.fetchall()}
    for t in ["hlava", "telo", "oci", "ruka", "mapa", "aura", "mazlicek"]:
        if t not in vybaveni: vybaveni[t] = ""
    cursor.execute("SELECT item_id FROM zakoupene_predmety WHERE user_id = ?", (user_id,))
    zakoupene = [r[0] for r in cursor.fetchall()]
    now = time.time()
    cursor.execute("SELECT item_id, konec_ts FROM aktivni_buff WHERE user_id = ? AND konec_ts > ?", (user_id, now))
    aktivni_buffy = {r[0]: int(r[1] - now) for r in cursor.fetchall()}
    
    dnes = time.strftime("%Y-%m-%d")
    cursor.execute("SELECT truhly, nakupy, zapisy, odmena_vybrana FROM denni_postup WHERE user_id = ? AND datum = ?", (user_id, dnes))
    denni_row = cursor.fetchone()
    denni_stav = {"truhly": denni_row[0], "nakupy": denni_row[1], "zapisy": denni_row[2], "odmena_vybrana": denni_row[3]} if denni_row else {"truhly": 0, "nakupy": 0, "zapisy": 0, "odmena_vybrana": 0}
    
    cursor.execute("SELECT artefakt_id FROM hrac_artefakty WHERE user_id = ?", (user_id,))
    nalezene_artefakty = [r[0] for r in cursor.fetchall()]
    
    cursor.execute("SELECT zainvestovano, posledni_vyber FROM hrac_banka WHERE user_id = ?", (user_id,))
    banka_row = cursor.fetchone()
    if banka_row:
        zainvestovano = banka_row[0]
        lze_vybrat = (banka_row[1] != dnes and zainvestovano > 0)
    else:
        zainvestovano = 0
        lze_vybrat = False
    banka_stav = {"zainvestovano": zainvestovano, "lze_vybrat": lze_vybrat}
    
    cursor.execute("SELECT dil_id FROM hrac_garaz WHERE user_id = ?", (user_id,))
    nalezene_dily = [r[0] for r in cursor.fetchall()]
    
    # NAČTENÍ AKTIVNÍHO STROJE
    cursor.execute("SELECT aktivni_stroj_id FROM hrac_stroj WHERE user_id = ?", (user_id,))
    stroj_row = cursor.fetchone()
    aktivni_stroj = stroj_row[0] if stroj_row else "pesi"
    
    # Bezpečnostní pojistka: Pokud hráč nemá dostatek dílů, stroj se resetuje na chůzi
    if len(nalezene_dily) < len(DEFINICE_DILU) and aktivni_stroj != "pesi":
        aktivni_stroj = "pesi"
        cursor.execute("INSERT OR REPLACE INTO hrac_stroj (user_id, aktivni_stroj_id) VALUES (?, 'pesi')", (user_id,))
        conn.commit()
        
    conn.close()

    vzdalenost_km = spocitej_vzdalenost(body)
    
    # OPRAVENO: Bonus stroje se nyní správně aplikuje na efektivní vzdálenost pro výpočet XP i milníků
    bonus = DEFINICE_STROJU.get(aktivni_stroj, {}).get("bonus", 1.0)
    efektivni_vzdalenost = vzdalenost_km * bonus
    celkem_xp = int(efektivni_vzdalenost * 300)
    
    odemcene_milniky = []
    for m in DEFINICE_MILNIKU:
        if efektivni_vzdalenost >= m["vzdalenost"]:
            celkem_xp += m["xp_odmena"]
            odemcene_milniky.append(m["id"])

    level = 1
    xp_potreba = 500
    zbyvajici_xp = celkem_xp
    while zbyvajici_xp >= xp_potreba:
        zbyvajici_xp -= xp_potreba
        level += 1
        xp_potreba = math.floor(500 * math.pow(1.2, level - 1))

    return {
        "level": level, "xp": zbyvajici_xp, "xp_potreba": xp_potreba, "celkem_xp": celkem_xp,
        "vzdalenost": vzdalenost_km, "odemcene_milniky": odemcene_milniky, "vybaveni": vybaveni,
        "mince": mince, "zakoupene": zakoupene, "aktivni_buffy": aktivni_buffy, 
        "denni_stav": denni_stav, "nalezene_artefakty": nalezene_artefakty, 
        "banka_stav": banka_stav, "nalezene_dily": nalezene_dily, "aktivni_stroj": aktivni_stroj
    }

# --- ROUTES / ENDPOINTY ---
@app.route('/')
def index():
    return render_template('index.html', stav=spocti_rpg_stav(None), milniky=DEFINICE_MILNIKU, predmety=DEFINICE_PREDMETU, artefakty=DEFINICE_ARTEFAKTU, dily=DEFINICE_DILU)

@app.route('/api/stav', methods=['GET'])
def get_stav_uzivatele():
    user_id = request.args.get('user_id')
    return jsonify(spocti_rpg_stav(user_id))

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    jmeno = data.get('jmeno')
    heslo = data.get('heslo')
    if not jmeno or not heslo: return jsonify({'chyba': 'Vyplňte jméno a heslo.'}), 400
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM uzivatele WHERE jmeno = ?', (jmeno,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'chyba': 'Toto jméno už je zabrané.'}), 400
    heslo_hash = generate_password_hash(heslo)
    cursor.execute('INSERT INTO uzivatele (jmeno, heslo) VALUES (?, ?)', (jmeno, heslo_hash))
    conn.commit()
    conn.close()
    return jsonify({'zprava': 'Účet byl úspěšně vytvořen!'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    jmeno = data.get('jmeno')
    heslo = data.get('heslo')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, heslo FROM uzivatele WHERE jmeno = ?', (jmeno,))
    uzivatel = cursor.fetchone()
    conn.close()
    if uzivatel and check_password_hash(uzivatel[1], heslo):
        return jsonify({'zprava': 'Přihlášení úspěšné!', 'user_id': uzivatel[0], 'jmeno': jmeno}), 200
    else:
        return jsonify({'chyba': 'Špatné jméno nebo heslo.'}), 401

@app.route('/api/body', methods=['GET'])
def get_body():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({'body': []}) 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT lat, lng FROM odkryta_mista WHERE user_id = ?', (user_id,))
    vsechny_body_hrace = cursor.fetchall()
    conn.close()
    return jsonify({'body': [[b[0], b[1]] for b in vsechny_body_hrace]})

@app.route('/api/ulozit', methods=['POST'])
def ulozit_bod():
    data = request.get_json() or {}
    lat, lng, user_id = data.get('lat'), data.get('lng'), data.get('user_id')
    if not user_id: return jsonify({'chyba': 'Hráč není přihlášen'}), 401
    if lat and lng:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO odkryta_mista (user_id, lat, lng) VALUES (?, ?, ?)", (user_id, lat, lng))
        conn.commit()
        cursor.execute("SELECT lat, lng FROM odkryta_mista WHERE user_id = ?", (user_id,))
        vsechny_body = [[row[0], row[1]] for row in cursor.fetchall()]
        conn.close()
    else:
        vsechny_body = []
    return jsonify({"status": "success", "stav": spocti_rpg_stav(user_id), "vsechny_body": vsechny_body})

@app.route('/api/zajimavosti', methods=['GET'])
def get_zajimavosti():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nazev, lat, lng, popis FROM zajimavosti')
    mista = cursor.fetchall()
    conn.close()
    return jsonify([{'id': m[0], 'nazev': m[1], 'lat': m[2], 'lng': m[3], 'popis': m[4]} for m in mista])

@app.route('/api/zapisnik', methods=['GET', 'POST'])
def zapisnik_akce():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if request.method == 'GET':
        misto_id = request.args.get('zajimavost_id')
        cursor.execute('SELECT u.jmeno, z.vzkaz, z.datum FROM zapisnik z JOIN uzivatele u ON z.user_id = u.id WHERE z.zajimavost_id = ? ORDER BY z.id DESC', (misto_id,))
        vysledek = [{'jmeno': z[0], 'vzkaz': z[1], 'datum': z[2]} for z in cursor.fetchall()]
        conn.close()
        return jsonify(vysledek)
    if request.method == 'POST':
        data = request.get_json()
        misto_id, user_id, vzkaz = data.get('zajimavost_id'), data.get('user_id'), data.get('vzkaz')
        datum = time.strftime("%d.%m.%Y %H:%M")
        cursor.execute('INSERT INTO zapisnik (zajimavost_id, user_id, vzkaz, datum) VALUES (?, ?, ?, ?)', (misto_id, user_id, vzkaz, datum))
        conn.commit()
        conn.close()
        aktualizuj_denni_postup(user_id, 'zapisy')
        return jsonify({'zprava': 'Úspěšně zapsáno!'}), 201

@app.route('/api/zmenit_obleceni', methods=['POST'])
def zmenit_obleceni():
    data = request.get_json() or {}
    typ, item_id, user_id = data.get('typ'), data.get('item_id'), data.get('user_id')
    if typ and user_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO hrac_vybaveni (user_id, typ, item_id) VALUES (?, ?, ?)", (user_id, typ, item_id))
        conn.commit()
        conn.close()
    return jsonify({"status": "success", "stav": spocti_rpg_stav(user_id)})

@app.route('/api/vybrat_odmenu', methods=['POST'])
def vybrat_odmenu():
    data = request.get_json() or {}
    hodnota, user_id = data.get('hodnota', 5), data.get('user_id')
    if user_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE uzivatele SET zlato = zlato + ? WHERE id = ?", (hodnota, user_id))
        conn.commit()
        conn.close()
        aktualizuj_denni_postup(user_id, 'truhly')
    return jsonify({"status": "success", "stav": spocti_rpg_stav(user_id)})

@app.route('/api/sebrat_artefakt', methods=['POST'])
def sebrat_artefakt():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id: return jsonify({"status": "error"})
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT artefakt_id FROM hrac_artefakty WHERE user_id = ?", (user_id,))
    vlastnene = [r[0] for r in cursor.fetchall()]
    
    mozne_nove = [a['id'] for a in DEFINICE_ARTEFAKTU if a['id'] not in vlastnene]
    if mozne_nove:
        novy_id = random.choice(mozne_nove)
        cursor.execute("INSERT INTO hrac_artefakty (user_id, artefakt_id) VALUES (?, ?)", (user_id, novy_id))
        conn.commit()
        nalezeno = next(a for a in DEFINICE_ARTEFAKTU if a['id'] == novy_id)
        zprava = f"🏺 ÚŽASNÝ OBJEV! Nalezla jsi historický artefakt: {nalezeno['nazev']}! Podívej se do deníku."
    else:
        cursor.execute("UPDATE uzivatele SET zlato = zlato + 250 WHERE id = ?", (user_id,))
        conn.commit()
        zprava = "🏺 Našla jsi prastaré naleziště, ale už máš kompletní sbírku! Získáváš odměnu 250 zlaťáků."

    conn.close()
    return jsonify({"status": "success", "zprava": zprava, "stav": spocti_rpg_stav(user_id)})

@app.route('/api/sebrat_dil', methods=['POST'])
def sebrat_dil():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id: return jsonify({"status": "error"})
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = time.time()
    cursor.execute("SELECT item_id FROM aktivni_buff WHERE user_id = ? AND konec_ts > ? AND item_id = 'm_stroj_magnet'", (user_id, now))
    ma_chytry_magnet = cursor.fetchone() is not None
    
    cursor.execute("SELECT dil_id FROM hrac_garaz WHERE user_id = ?", (user_id,))
    vlastnene = [r[0] for r in cursor.fetchall()]
    
    volby = []
    vahy = []
    
    for dil in DEFINICE_DILU:
        volby.append(dil)
        if dil['id'] in vlastnene:
            vahy.append(1)
        else:
            vahy.append(2 if ma_chytry_magnet else 1)
            
    vybrany_dil = random.choices(volby, weights=vahy, k=1)[0]
    
    if vybrany_dil['id'] in vlastnene:
        vydelek = random.randint(20, 30)
        cursor.execute("UPDATE uzivatele SET zlato = zlato + ? WHERE id = ?", (vydelek, user_id))
        conn.commit()
        zprava = f"⚙️ Našla jsi {vybrany_dil['nazev']}, ale ten už máš! Prodáváš ho na trhu za {vydelek} zlaťáků."
    else:
        cursor.execute("INSERT INTO hrac_garaz (user_id, dil_id) VALUES (?, ?)", (user_id, vybrany_dil['id']))
        conn.commit()
        zprava = f"⚙️ CINK! Nový díl: {vybrany_dil['nazev']}! Zanes ho do garáže."

    conn.close()
    return jsonify({"status": "success", "zprava": zprava, "stav": spocti_rpg_stav(user_id)})

# OPRAVENO: Skládání strojů nyní korektně zapisuje do textového sloupce aktivni_stroj_id
@app.route('/api/slozit_stroj', methods=['POST'])
def slozit_stroj():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id: return jsonify({"status": "error"})
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT dil_id FROM hrac_garaz WHERE user_id = ?", (user_id,))
    vlastnene = [r[0] for r in cursor.fetchall()]
    
    if len(vlastnene) >= len(DEFINICE_DILU):
        cursor.execute("INSERT OR REPLACE INTO hrac_stroj (user_id, aktivni_stroj_id) VALUES (?, 'ctyrkolka')", (user_id,))
        conn.commit()
        zprava = "🏍️ ÚSPĚCH! Poskládala jsi základní mechanickou sadu. Tvůj první stroj byl automaticky aktivován v Garáži!"
        status = "success"
    else:
        zprava = "Chybí ti nějaké díly."
        status = "chyba"

    conn.close()
    return jsonify({"status": status, "zprava": zprava, "stav": spocti_rpg_stav(user_id)})

# OPRAVENO: Výběr konkrétního stroje zohledňuje kompletaci mechanické sady i levelové požadavky
@app.route('/api/vybrat_stroj', methods=['POST'])
def vybrat_stroj():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    stroj_id = data.get('stroj_id')
    
    if stroj_id not in DEFINICE_STROJU:
        return jsonify({"status": "error", "zprava": "Neznámý stroj"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT dil_id FROM hrac_garaz WHERE user_id = ?", (user_id,))
    vlastnene_dily = [r[0] for r in cursor.fetchall()]
    
    stav = spocti_rpg_stav(user_id)
    
    # Podmínka: Pro jakýkoliv pokročilý stroj musí mít postavenou kompletní sadu dílů
    if stroj_id != "pesi" and len(vlastnene_dily) < len(DEFINICE_DILU):
        conn.close()
        return jsonify({"status": "error", "zprava": "Musíš nejprve v garáži poskládat všech 5 základních mechanických dílů!"}), 403
        
    if stav['level'] < DEFINICE_STROJU[stroj_id]['req_level']:
        conn.close()
        return jsonify({"status": "error", "zprava": f"Potřebuješ level {DEFINICE_STROJU[stroj_id]['req_level']}!"}), 403

    cursor.execute("INSERT OR REPLACE INTO hrac_stroj (user_id, aktivni_stroj_id) VALUES (?, ?)", (user_id, stroj_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "zprava": f"Aktivován stroj: {DEFINICE_STROJU[stroj_id]['nazev']}", "stav": spocti_rpg_stav(user_id)})

@app.route('/api/koupit', methods=['POST'])
def koupit():
    data = request.get_json() or {}
    item_id, cena, user_id = data.get('item_id'), data.get('cena'), data.get('user_id')
    if not user_id: return jsonify({"status": "error"})
    
    predmet = next((p for p in DEFINICE_PREDMETU if p["id"] == item_id), None)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT zlato FROM uzivatele WHERE id = ?", (user_id,))
    aktualni_mince = cursor.fetchone()[0]
    
    vyhra_z_lootboxu = None
    if aktualni_mince >= cena and predmet:
        if predmet['typ'] == 'consumable' and item_id == 'c_luck':
            vyhra_z_lootboxu = random.randint(50, 300)
            cursor.execute("UPDATE uzivatele SET zlato = zlato - ? + ? WHERE id = ?", (cena, vyhra_z_lootboxu, user_id))
        else:
            cursor.execute("UPDATE uzivatele SET zlato = zlato - ? WHERE id = ?", (cena, user_id))
            if predmet['typ'] == 'mapa':
                cursor.execute("INSERT OR REPLACE INTO aktivni_buff (user_id, item_id, konec_ts) VALUES (?, ?, ?)", (user_id, item_id, time.time() + 3600))
            else:
                cursor.execute("INSERT OR IGNORE INTO zakoupene_predmety (user_id, item_id) VALUES (?, ?)", (user_id, item_id))
        conn.commit()
        conn.close()
        aktualizuj_denni_postup(user_id, 'nakupy')
        status = "success"
    else:
        status = "nedostatek_minci"
        conn.close()
    return jsonify({"status": status, "stav": spocti_rpg_stav(user_id), "vyhra": vyhra_z_lootboxu})

@app.route('/api/vybrat_denni_odmenu', methods=['POST'])
def vybrat_denni_odmenu():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    if not user_id: return jsonify({"status": "error"})
    
    dnes = time.strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT truhly, nakupy, zapisy, odmena_vybrana FROM denni_postup WHERE user_id = ? AND datum = ?", (user_id, dnes))
    row = cursor.fetchone()
    
    if row and row[0] >= 3 and row[1] >= 1 and row[2] >= 1 and row[3] == 0:
        cursor.execute("UPDATE denni_postup SET odmena_vybrana = 1 WHERE user_id = ? AND datum = ?", (user_id, dnes))
        cursor.execute("UPDATE uzivatele SET zlato = zlato + 500 WHERE id = ?", (user_id,))
        conn.commit()
        status = "success"
    else:
        status = "chyba"
    conn.close()
    return jsonify({"status": status, "stav": spocti_rpg_stav(user_id)})

@app.route('/api/banka_akce', methods=['POST'])
def banka_akce():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    akce = data.get('akce')
    castka = int(data.get('castka', 0))

    if not user_id: return jsonify({"status": "error"})

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    dnes = time.strftime("%Y-%m-%d")

    cursor.execute("INSERT OR IGNORE INTO hrac_banka (user_id, zainvestovano, posledni_vyber) VALUES (?, 0, '')", (user_id,))
    cursor.execute("SELECT zainvestovano, posledni_vyber FROM hrac_banka WHERE user_id = ?", (user_id,))
    zainvestovano, posledni_vyber = cursor.fetchone()

    if akce == 'vlozit' and castka > 0:
        cursor.execute("SELECT zlato FROM uzivatele WHERE id = ?", (user_id,))
        zlato = cursor.fetchone()[0]
        if zlato >= castka:
            cursor.execute("UPDATE uzivatele SET zlato = zlato - ? WHERE id = ?", (castka, user_id))
            cursor.execute("UPDATE hrac_banka SET zainvestovano = zainvestovano + ? WHERE user_id = ?", (castka, user_id))
            zprava = f"🏦 Úspěšně jsi investovala {castka} zlaťáků do svého portfolia."
        else:
            zprava = "Nemáš dostatek mincí v peněžence."
            
    elif akce == 'vybrat_zisk':
        if posledni_vyber != dnes and zainvestovano > 0:
            zisk = max(1, int(zainvestovano * 0.05))
            cursor.execute("UPDATE uzivatele SET zlato = zlato + ? WHERE id = ?", (zisk, user_id))
            cursor.execute("UPDATE hrac_banka SET posledni_vyber = ? WHERE user_id = ?", (dnes, user_id))
            zprava = f"💸 Výplata dorazila! Získáváš denní dividendu: {zisk} zlaťáků."
        else:
            zprava = "Úrok už jsi dnes vybrala, nebo nemáš nic zainvestováno."

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "zprava": zprava, "stav": spocti_rpg_stav(user_id)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)