from flask import Flask, render_template, jsonify, request
import sqlite3
import os
import math
import time
import random

app = Flask(__name__)
DB_PATH = 'mlha_db.sqlite'

# OBROVSKÁ DEFINICE PŘEDMĚTŮ VČETNĚ MAZLÍČKŮ A AUR
DEFINICE_PREDMETU = [
    # Pokrývka hlavy
    {"id": "h1", "nazev": "Trenérská kšiltovka", "barva": "#ff1744", "typ": "hlava", "req_level": 1, "cena": 0},
    {"id": "h3", "nazev": "Ochranná přilba", "barva": "#00e5ff", "typ": "hlava", "req_level": 5, "cena": 0},
    {"id": "h_vip", "nazev": "Zlatá svatozář (VIP)", "barva": "#ffea00", "typ": "hlava", "req_level": 1, "cena": 50, "premium": True},
    {"id": "h_cyber", "nazev": "Kyber-helma (VIP)", "barva": "#ff0057", "typ": "hlava", "req_level": 1, "cena": 75, "premium": True},
    
    # Oblečení (Svršky)
    {"id": "o1", "nazev": "Sportovní mikina", "barva": "#2979ff", "typ": "telo", "req_level": 1, "cena": 0},
    {"id": "o3", "nazev": "Kybernetický plášť", "barva": "#00e676", "typ": "telo", "req_level": 6, "cena": 0},
    {"id": "o_vip", "nazev": "Královská zbroj (VIP)", "barva": "#ffd700", "typ": "telo", "req_level": 1, "cena": 100, "premium": True},
    {"id": "o_phoenix", "nazev": "Plášť Fénixe (VIP)", "barva": "#ff3d00", "typ": "telo", "req_level": 1, "cena": 120, "premium": True},
    
    # Oči a doplňky
    {"id": "d1", "nazev": "Sluneční brýle", "barva": "#ffeb3b", "typ": "oci", "req_level": 2, "cena": 0},
    {"id": "d2", "nazev": "Futuristický vizor", "barva": "#d500f9", "typ": "oci", "req_level": 5, "cena": 0},
    
    # Zbraně a vybavení
    {"id": "z2", "nazev": "Světelný meč", "barva": "#00e5ff", "typ": "ruka", "req_level": 3, "cena": 0},
    {"id": "z3", "nazev": "Bojová sekera", "barva": "#ff3d00", "typ": "ruka", "req_level": 6, "cena": 0},
    {"id": "z_vip", "nazev": "Božský meč (VIP)", "barva": "#ffffff", "typ": "ruka", "req_level": 1, "cena": 150, "premium": True},
    {"id": "z_hammer", "nazev": "Hromové kladivo (VIP)", "barva": "#00e5ff", "typ": "ruka", "req_level": 1, "cena": 160, "premium": True},

    # Aury a Vizuální efekty
    {"id": "a_fire", "nazev": "Ohnivá Aura (VIP)", "barva": "#ff3d00", "typ": "aura", "req_level": 1, "cena": 200, "premium": True},
    {"id": "a_ice", "nazev": "Ledová Aura (VIP)", "barva": "#00e5ff", "typ": "aura", "req_level": 1, "cena": 200, "premium": True},

    # Široký výběr mazlíčků
    {"id": "pet_coon", "nazev": "Mainská mývalí (VIP)", "barva": "#e65100", "typ": "mazlicek", "req_level": 1, "cena": 350, "premium": True},
    {"id": "pet_fox", "nazev": "Ohnivá liška (VIP)", "barva": "#ff3d00", "typ": "mazlicek", "req_level": 1, "cena": 450, "premium": True},
    {"id": "pet_dragon", "nazev": "Malý drak (VIP)", "barva": "#d500f9", "typ": "mazlicek", "req_level": 1, "cena": 500, "premium": True},
    {"id": "pet_owl", "nazev": "Sněžná sova (VIP)", "barva": "#e0f7fa", "typ": "mazlicek", "req_level": 1, "cena": 600, "premium": True},
    {"id": "pet_wolf", "nazev": "Stínový vlk (VIP)", "barva": "#4a148c", "typ": "mazlicek", "req_level": 1, "cena": 800, "premium": True},
    {"id": "pet_robo", "nazev": "Kyber-Dron (VIP)", "barva": "#00e676", "typ": "mazlicek", "req_level": 1, "cena": 1000, "premium": True},

    # Mapové vychytávky (Platí 60 minut)
    {"id": "m_dalekohled", "nazev": "Dalekohled (+50m Odkrytí)", "barva": "#00e5ff", "typ": "mapa", "req_level": 2, "cena": 40, "premium": True, "ikona": "fas fa-binoculars"},
    {"id": "m_magnet", "nazev": "Magnet (Sběr na 60m)", "barva": "#ffea00", "typ": "mapa", "req_level": 3, "cena": 60, "premium": True, "ikona": "fas fa-magnet"},
    {"id": "m_radar", "nazev": "Radar (Víc truhel)", "barva": "#ff1744", "typ": "mapa", "req_level": 4, "cena": 80, "premium": True, "ikona": "fas fa-satellite-dish"},
    {"id": "m_double", "nazev": "Zlatá horečka (2x Mince)", "barva": "#ffd700", "typ": "mapa", "req_level": 1, "cena": 70, "premium": True, "ikona": "fas fa-angle-double-up"},
    
    # Lootbox (Spotřební)
    {"id": "c_luck", "nazev": "Truhla Štěstěny (50-300🪙)", "barva": "#ffea00", "typ": "consumable", "req_level": 1, "cena": 100, "premium": True, "ikona": "fas fa-dice"},
]

DEFINICE_MILNIKU = [
    {"id": "m1", "nazev": "Poutník-začátečník", "popis": "Dosáhni vzdálenosti 0.5 km.", "vzdalenost": 0.5, "xp_odmena": 100},
    {"id": "m2", "nazev": "Rozpohybované nohy", "popis": "Dosáhni vzdálenosti 1.0 km.", "vzdalenost": 1.0, "xp_odmena": 150},
    {"id": "m3", "nazev": "Průzkumník z okolí", "popis": "Dosáhni vzdálenosti 2.0 km.", "vzdalenost": 2.0, "xp_odmena": 250},
    {"id": "m4", "nazev": "Pětka v kapse", "popis": "Dosáhni vzdálenosti 5.0 km.", "vzdalenost": 5.0, "xp_odmena": 400},
]

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS prozkoumana_mista (id INTEGER PRIMARY KEY AUTOINCREMENT, lat REAL NOT NULL, lng REAL NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS hrac_vybaveni (typ TEXT PRIMARY KEY, item_id TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS hrac_penize (id INTEGER PRIMARY KEY, mince INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zakoupene_predmety (item_id TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS aktivni_buff (item_id TEXT PRIMARY KEY, konec_ts REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS zakoupene_xp (id INTEGER PRIMARY KEY, xp_bonus INTEGER)''')
    cursor.execute("INSERT OR IGNORE INTO zakoupene_xp (id, xp_bonus) VALUES (1, 0)")
    
    for typ in ["hlava", "telo", "oci", "ruka", "mapa", "aura", "mazlicek"]:
        cursor.execute("INSERT OR IGNORE INTO hrac_vybaveni (typ, item_id) VALUES (?, ?)", (typ, ""))
    cursor.execute("INSERT OR IGNORE INTO hrac_penize (id, mince) VALUES (1, 0)")
    
    conn.commit()
    conn.close()

init_db()

def spocitej_vzdalenost(body):
    if len(body) < 2: return 0.0
    celkem_metru = 0.0
    for i in range(1, len(body)):
        lat1, lon1 = body[i-1]['lat'], body[i-1]['lng']
        lat2, lon2 = body[i]['lat'], body[i]['lng']
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        celkem_metru += R * c
    return celkem_metru / 1000.0

def spocti_rpg_stav():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT lat, lng FROM prozkoumana_mista")
        body = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT typ, item_id FROM hrac_vybaveni")
        vybaveni = {row['typ']: row['item_id'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT mince FROM hrac_penize WHERE id = 1")
        mince = cursor.fetchone()['mince']
        
        cursor.execute("SELECT item_id FROM zakoupene_predmety")
        zakoupene = [row['item_id'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT xp_bonus FROM zakoupene_xp WHERE id = 1")
        xp_bonus = cursor.fetchone()['xp_bonus']
        
        now = time.time()
        cursor.execute("SELECT item_id, konec_ts FROM aktivni_buff WHERE konec_ts > ?", (now,))
        aktivni_buffy = {row['item_id']: int(row['konec_ts'] - now) for row in cursor.fetchall()}
        conn.close()
    except Exception as e:
        body, vybaveni, mince, zakoupene, aktivni_buffy, xp_bonus = [], {}, 0, [], {}, 0

    vzdalenost_km = spocitej_vzdalenost(body)
    celkem_xp = (len(body) * 15) + xp_bonus
    odemcene_milniky = []
    
    for m in DEFINICE_MILNIKU:
        if vzdalenost_km >= m["vzdalenost"]:
            celkem_xp += m["xp_odmena"]
            odemcene_milniky.append(m["id"])

    level = 1
    xp_potreba = 100
    zbyvajici_xp = celkem_xp
    while zbyvajici_xp >= xp_potreba:
        zbyvajici_xp -= xp_potreba
        level += 1
        xp_potreba = math.floor(100 * math.pow(1.5, level - 1))

    return {
        "level": level, "xp": zbyvajici_xp, "xp_potreba": xp_potreba, "celkem_xp": celkem_xp,
        "vzdalenost": vzdalenost_km, "odemcene_milniky": odemcene_milniky, "vybaveni": vybaveni,
        "mince": mince, "zakoupene": zakoupene, "aktivni_buffy": aktivni_buffy
    }

@app.route('/')
def index():
    return render_template('index.html', stav=spocti_rpg_stav(), milniky=DEFINICE_MILNIKU, predmety=DEFINICE_PREDMETU)

@app.route('/api/body', methods=['GET'])
def get_body():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT lat, lng FROM prozkoumana_mista")
    body = [[row['lat'], row['lng']] for row in cursor.fetchall()]
    conn.close()
    return jsonify({"body": body})

@app.route('/api/ulozit', methods=['POST'])
def ulozit_bod():
    data = request.get_json() or {}
    lat, lng = data.get('lat'), data.get('lng')
    if lat and lng:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO prozkoumana_mista (lat, lng) VALUES (?, ?)", (lat, lng))
        conn.commit()
        cursor.execute("SELECT lat, lng FROM prozkoumana_mista")
        vsechny_body = [[row['lat'], row['lng']] for row in cursor.fetchall()]
        conn.close()
    else:
        vsechny_body = []
    return jsonify({"status": "success", "stav": spocti_rpg_stav(), "vsechny_body": vsechny_body})

@app.route('/api/zmenit_obleceni', methods=['POST'])
def zmenit_obleceni():
    data = request.get_json() or {}
    typ, item_id = data.get('typ'), data.get('item_id')
    if typ:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE hrac_vybaveni SET item_id = ? WHERE typ = ?", (item_id, typ))
        conn.commit()
        conn.close()
    return jsonify({"status": "success", "stav": spocti_rpg_stav()})

@app.route('/api/vybrat_odmenu', methods=['POST'])
def vybrat_odmenu():
    data = request.get_json() or {}
    hodnota = data.get('hodnota', 5)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE hrac_penize SET mince = mince + ? WHERE id = 1", (hodnota,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "stav": spocti_rpg_stav()})

@app.route('/api/koupit', methods=['POST'])
def koupit():
    data = request.get_json() or {}
    item_id, cena = data.get('item_id'), data.get('cena')
    
    predmet = next((p for p in DEFINICE_PREDMETU if p["id"] == item_id), None)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mince FROM hrac_penize WHERE id = 1")
    aktualni_mince = cursor.fetchone()['mince']
    
    vyhra_z_lootboxu = None
    
    if aktualni_mince >= cena and predmet:
        if predmet['typ'] == 'consumable' and item_id == 'c_luck':
            vyhra_z_lootboxu = random.randint(50, 300)
            cursor.execute("UPDATE hrac_penize SET mince = mince - ? + ? WHERE id = 1", (cena, vyhra_z_lootboxu))
        else:
            cursor.execute("UPDATE hrac_penize SET mince = mince - ? WHERE id = 1", (cena,))
            if predmet['typ'] == 'mapa':
                cursor.execute("INSERT OR REPLACE INTO aktivni_buff (item_id, konec_ts) VALUES (?, ?)", (item_id, time.time() + 3600))
            else:
                cursor.execute("INSERT OR IGNORE INTO zakoupene_predmety (item_id) VALUES (?)", (item_id,))
            
        conn.commit()
        status = "success"
    else:
        status = "nedostatek_minci"
    conn.close()
    return jsonify({"status": status, "stav": spocti_rpg_stav(), "vyhra": vyhra_z_lootboxu})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True,)