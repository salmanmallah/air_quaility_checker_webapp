from flask import Flask, render_template, jsonify, request
import urllib.request
import urllib.parse
import json
import time
import os
from getpass import getpass

app = Flask(__name__)

KEY_FILE = "api_key.txt"
BASE    = "https://api.airvisual.com/v2"
CACHE_TTL = 3600
cache = {
    "states": {},
    "cities": {},
}


def get_api_key():
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()

    print("API key not found. Please enter your IQAir API key.")
    key = getpass("API key: ").strip()
    if not key:
        raise SystemExit("API key is required to run this application.")

    with open(KEY_FILE, "w", encoding="utf-8") as f:
        f.write(key)
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    return key

API_KEY = get_api_key()

DEFAULT_COUNTRY_STATES = {
    "Pakistan": [
        {"state":"Azad Kashmir"},
        {"state":"Balochistan"},
        {"state":"FATA"},
        {"state":"Gilgit-Baltistan"},
        {"state":"Islamabad"},
        {"state":"Khyber Pakhtunkhwa"},
        {"state":"Punjab"},
        {"state":"Sindh"},
    ]
}

def cached_states(country):
    now = time.time()
    entry = cache["states"].get(country)
    if entry and now - entry["ts"] < CACHE_TTL:
        return entry["data"]
    try:
        data = fetch(f"{BASE}/states?country={urllib.parse.quote(country)}&key={API_KEY}")
        states = data.get("data", [])
        cache["states"][country] = {"ts": now, "data": states}
        return states
    except Exception:
        if entry:
            return entry["data"]
        if country in DEFAULT_COUNTRY_STATES:
            return DEFAULT_COUNTRY_STATES[country]
        raise


def cached_cities(country, state):
    key = (country, state)
    now = time.time()
    entry = cache["cities"].get(key)
    if entry and now - entry["ts"] < CACHE_TTL:
        return entry["data"]
    try:
        data = fetch(f"{BASE}/cities?state={urllib.parse.quote(state)}&country={urllib.parse.quote(country)}&key={API_KEY}")
        cities = data.get("data", [])
        cache["cities"][key] = {"ts": now, "data": cities}
        return cities
    except Exception:
        if entry:
            return entry["data"]
        raise


def all_cities_for_country(country):
    states = cached_states(country)
    all_cities = []
    for state_obj in states:
        state_name = state_obj.get("state")
        if not state_name:
            continue
        try:
            cities = cached_cities(country, state_name)
        except Exception:
            continue
        for city in cities:
            all_cities.append({"city": city.get("city"), "state": state_name})
    return all_cities

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AirWatch/1.0"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())

def aqi_meta(aqi):
    if aqi <= 50:   return {"label":"Good",            "emoji":"😊", "color":"#22c55e", "advice":"Air quality is satisfactory. Enjoy outdoor activities!"}
    if aqi <= 100:  return {"label":"Moderate",        "emoji":"🙂", "color":"#eab308", "advice":"Acceptable quality. Unusually sensitive individuals may have concerns."}
    if aqi <= 150:  return {"label":"Unhealthy (Sens.)","emoji":"😐","color":"#f97316", "advice":"Sensitive groups may experience effects. Limit prolonged exertion outdoors."}
    if aqi <= 200:  return {"label":"Unhealthy",       "emoji":"😷", "color":"#ef4444", "advice":"Everyone may experience effects. Avoid prolonged outdoor activities."}
    if aqi <= 300:  return {"label":"Very Unhealthy",  "emoji":"🤢", "color":"#a855f7", "advice":"Health alert! Everyone should avoid outdoor exertion."}
    return               {"label":"Hazardous",         "emoji":"☠️", "color":"#7c3aed", "advice":"Emergency conditions. Stay indoors, seal windows."}

# ── Countries → States → Cities cascade ──
@app.route("/api/countries")
def countries():
    try:
        data = fetch(f"{BASE}/countries?key={API_KEY}")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/states")
def states():
    country = request.args.get("country", "Pakistan")
    try:
        states = cached_states(country)
        return jsonify({"status": "success", "data": states})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cities")
def cities():
    state   = request.args.get("state")
    country = request.args.get("country", "Pakistan")
    try:
        if state == "__all__" or request.args.get("all") == "1" or not state:
            all_cities = all_cities_for_country(country)
            return jsonify({"status": "success", "data": all_cities})
        cities = cached_cities(country, state)
        return jsonify({"status": "success", "data": cities})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Main AQI for a city ──
@app.route("/api/aqi")
def get_aqi():
    city    = request.args.get("city", "Karachi")
    state   = request.args.get("state", "Sindh")
    country = request.args.get("country", "Pakistan")
    try:
        url  = f"{BASE}/city?city={urllib.parse.quote(city)}&state={urllib.parse.quote(state)}&country={urllib.parse.quote(country)}&key={API_KEY}"
        data = fetch(url)
        if data.get("status") != "success":
            return jsonify({"error": data.get("data", {}).get("message", "API error")}), 400

        d  = data["data"]
        p  = d["current"]["pollution"]
        w  = d["current"]["weather"]
        m  = aqi_meta(p["aqius"])

        return jsonify({
            "city":    d["city"],
            "state":   d["state"],
            "country": d["country"],
            "coords":  d["location"]["coordinates"],
            "aqi_us":  p["aqius"],
            "aqi_cn":  p.get("aqicn"),
            "main_pollutant": p.get("mainus", "—"),
            "level":   m,
            "weather": {
                "temp":     w["tp"],
                "humidity": w["hu"],
                "wind":     w["ws"],
                "pressure": w["pr"],
                "icon":     w.get("ic", ""),
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Nearest city by IP (uses IQAir nearest_city) ──
@app.route("/api/nearest")
def nearest():
    try:
        data = fetch(f"{BASE}/nearest_city?key={API_KEY}")
        if data.get("status") != "success":
            return jsonify({"error": "Could not detect location"}), 400
        d = data["data"]
        p = d["current"]["pollution"]
        w = d["current"]["weather"]
        m = aqi_meta(p["aqius"])
        return jsonify({
            "city":    d["city"],
            "state":   d["state"],
            "country": d["country"],
            "coords":  d["location"]["coordinates"],
            "aqi_us":  p["aqius"],
            "aqi_cn":  p.get("aqicn"),
            "main_pollutant": p.get("mainus", "—"),
            "level":   m,
            "weather": {
                "temp":     w["tp"],
                "humidity": w["hu"],
                "wind":     w["ws"],
                "pressure": w["pr"],
                "icon":     w.get("ic",""),
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/author")
def author():
    return render_template("author.html")

if __name__ == "__main__":
    app.run(debug=True)
