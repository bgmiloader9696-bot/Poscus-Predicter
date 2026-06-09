import os, json, hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_file, abort

app = Flask(__name__)

KEYS_FILE  = "keys.json"
RES_FILE   = "resellers.json"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "VC5SA9AT0H2010")

# ─── FILE HELPERS ────────────────────────────────────────────
def load_keys():
    try:
        with open(KEYS_FILE) as f: return json.load(f)
    except: return {}

def save_keys(data):
    with open(KEYS_FILE, "w") as f: json.dump(data, f, indent=2)

def load_resellers():
    try:
        with open(RES_FILE) as f: return json.load(f)
    except: return {}

def save_resellers(data):
    with open(RES_FILE, "w") as f: json.dump(data, f, indent=2)

# ─── AUTH ─────────────────────────────────────────────────────
def is_admin():
    return request.headers.get("X-Admin-Token") == ADMIN_TOKEN

def get_reseller_id():
    """Returns reseller_id if valid token, else None"""
    token = request.headers.get("X-Reseller-Token")
    if not token: return None
    resellers = load_resellers()
    for rid, rd in resellers.items():
        if rd.get("token") == token and rd.get("active", True):
            return rid
    return None

# ─── MAIN PAGE ───────────────────────────────────────────────
@app.route("/")
def index():
    return send_file("index.html")

@app.route("/admin")
def admin():
    return send_file("admin.html")

# ─── PUBLIC: KEY VALIDATE ────────────────────────────────────
@app.route("/api/key/validate", methods=["POST"])
def key_validate():
    data = request.json or {}
    k = (data.get("key") or "").strip().upper()
    keys = load_keys()
    if k not in keys:
        return jsonify({"valid": False, "msg": "Invalid key"})
    kd = keys[k]
    if not kd.get("active", False):
        return jsonify({"valid": False, "msg": "Key inactive"})
    today = datetime.now().strftime("%Y-%m-%d")
    if kd.get("expiry") and kd["expiry"] < today:
        return jsonify({"valid": False, "msg": "Key expired"})
    return jsonify({"valid": True, "name": kd.get("name",""), "expiry": kd.get("expiry","")})

@app.route("/api/key/verify", methods=["POST"])
def key_verify():
    data = request.json or {}
    k = (data.get("key") or "").strip().upper()
    device = (data.get("device") or "").strip()
    keys = load_keys()
    if k not in keys:
        return jsonify({"valid": False, "msg": "Invalid key"})
    kd = keys[k]
    if not kd.get("active", False):
        return jsonify({"valid": False, "msg": "Key inactive"})
    today = datetime.now().strftime("%Y-%m-%d")
    if kd.get("expiry") and kd["expiry"] < today:
        return jsonify({"valid": False, "msg": "Key expired"})
    stored_dev = (kd.get("device") or "").strip()
    if stored_dev and stored_dev != device:
        return jsonify({"valid": False, "msg": "Device mismatch"})
    if not stored_dev and device:
        keys[k]["device"] = device
        save_keys(keys)
    return jsonify({"valid": True, "name": kd.get("name",""), "expiry": kd.get("expiry","")})

# ─── ADMIN: KEYS ─────────────────────────────────────────────
@app.route("/api/admin/keys", methods=["GET"])
def admin_get_keys():
    if not is_admin(): return abort(403)
    return jsonify(load_keys())

@app.route("/api/admin/key/add", methods=["POST"])
def admin_add_key():
    if not is_admin(): return abort(403)
    data = request.json or {}
    k = (data.get("key") or "").strip().upper()
    if not k: return jsonify({"ok": False, "msg": "No key"})
    keys = load_keys()
    if k in keys: return jsonify({"ok": False, "msg": "Key exists"})
    keys[k] = {
        "active": data.get("active", True),
        "name":   data.get("name", ""),
        "expiry": data.get("expiry", ""),
        "device": data.get("device", ""),
        "note":   data.get("note", ""),
        "owner":  "admin",
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_keys(keys)
    return jsonify({"ok": True})

@app.route("/api/admin/key/delete", methods=["POST"])
def admin_del_key():
    if not is_admin(): return abort(403)
    data = request.json or {}
    k = (data.get("key") or "").strip().upper()
    keys = load_keys()
    if k in keys:
        del keys[k]
        save_keys(keys)
    return jsonify({"ok": True})

@app.route("/api/admin/key/update", methods=["POST"])
def admin_update_key():
    if not is_admin(): return abort(403)
    data = request.json or {}
    k = (data.get("key") or "").strip().upper()
    keys = load_keys()
    if k not in keys: return jsonify({"ok": False, "msg": "Not found"})
    for field in ["active","name","expiry","device","note"]:
        if field in data: keys[k][field] = data[field]
    save_keys(keys)
    return jsonify({"ok": True})

@app.route("/api/admin/key/reset-device", methods=["POST"])
def admin_reset_device():
    if not is_admin(): return abort(403)
    data = request.json or {}
    k = (data.get("key") or "").strip().upper()
    keys = load_keys()
    if k not in keys: return jsonify({"ok": False, "msg": "Not found"})
    keys[k]["device"] = ""
    save_keys(keys)
    return jsonify({"ok": True})

# ─── ADMIN: RESELLERS ────────────────────────────────────────
@app.route("/api/admin/resellers", methods=["GET"])
def admin_get_resellers():
    if not is_admin(): return abort(403)
    return jsonify(load_resellers())

@app.route("/api/admin/reseller/add", methods=["POST"])
def admin_add_reseller():
    if not is_admin(): return abort(403)
    data = request.json or {}
    rid = (data.get("reseller_id") or "").strip().upper()
    if not rid: return jsonify({"ok": False, "msg": "No ID"})
    resellers = load_resellers()
    if rid in resellers: return jsonify({"ok": False, "msg": "Already exists"})
    token = hashlib.md5(f"{rid}{datetime.now()}".encode()).hexdigest()[:16].upper()
    resellers[rid] = {
        "name":    data.get("name", rid),
        "token":   token,
        "active":  True,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note":    data.get("note", "")
    }
    save_resellers(resellers)
    return jsonify({"ok": True, "token": token, "reseller_id": rid})

@app.route("/api/admin/reseller/delete", methods=["POST"])
def admin_del_reseller():
    if not is_admin(): return abort(403)
    data = request.json or {}
    rid = (data.get("reseller_id") or "").strip().upper()
    resellers = load_resellers()
    if rid in resellers:
        del resellers[rid]
        save_resellers(resellers)
    return jsonify({"ok": True})

@app.route("/api/admin/reseller/toggle", methods=["POST"])
def admin_toggle_reseller():
    if not is_admin(): return abort(403)
    data = request.json or {}
    rid = (data.get("reseller_id") or "").strip().upper()
    resellers = load_resellers()
    if rid not in resellers: return jsonify({"ok": False, "msg": "Not found"})
    resellers[rid]["active"] = not resellers[rid].get("active", True)
    save_resellers(resellers)
    return jsonify({"ok": True, "active": resellers[rid]["active"]})

# ─── RESELLER: DEVICE ID MANAGEMENT ─────────────────────────
@app.route("/api/reseller/my-devices", methods=["GET"])
def reseller_my_devices():
    rid = get_reseller_id()
    if not rid: return abort(403)
    keys = load_keys()
    my_devices = {}
    for k, kd in keys.items():
        if kd.get("owner") == rid and kd.get("device", "").strip():
            my_devices[k] = kd
    return jsonify(my_devices)

@app.route("/api/reseller/my-keys", methods=["GET"])
def reseller_my_keys():
    rid = get_reseller_id()
    if not rid: return abort(403)
    keys = load_keys()
    my_keys = {k: v for k, v in keys.items() if v.get("owner") == rid}
    return jsonify(my_keys)

@app.route("/api/reseller/add-device", methods=["POST"])
def reseller_add_device():
    rid = get_reseller_id()
    if not rid: return abort(403)
    data = request.json or {}
    device_id = (data.get("device_id") or "").strip()
    key = (data.get("key") or "").strip().upper()
    expiry = (data.get("expiry") or "").strip()
    name = (data.get("name") or "").strip()
    if not device_id or not key:
        return jsonify({"ok": False, "msg": "device_id and key required"})
    keys = load_keys()
    if key in keys: return jsonify({"ok": False, "msg": "Key already exists"})
    today = datetime.now().strftime("%Y-%m-%d")
    if expiry and expiry < today:
        return jsonify({"ok": False, "msg": "Expiry date is in the past"})
    keys[key] = {
        "active":  True,
        "name":    name or device_id,
        "expiry":  expiry,
        "device":  device_id,
        "note":    data.get("note", ""),
        "owner":   rid,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_keys(keys)
    return jsonify({"ok": True, "key": key})

@app.route("/api/reseller/remove-device", methods=["POST"])
def reseller_remove_device():
    rid = get_reseller_id()
    if not rid: return abort(403)
    data = request.json or {}
    key = (data.get("key") or "").strip().upper()
    keys = load_keys()
    if key not in keys: return jsonify({"ok": False, "msg": "Key not found"})
    if keys[key].get("owner") != rid:
        return jsonify({"ok": False, "msg": "Not your key"})
    del keys[key]
    save_keys(keys)
    return jsonify({"ok": True})

@app.route("/api/reseller/info", methods=["GET"])
def reseller_info():
    rid = get_reseller_id()
    if not rid: return abort(403)
    resellers = load_resellers()
    rd = resellers.get(rid, {})
    keys = load_keys()
    total = sum(1 for v in keys.values() if v.get("owner") == rid)
    active = sum(1 for v in keys.values() if v.get("owner") == rid and v.get("active"))
    return jsonify({"reseller_id": rid, "name": rd.get("name"), "total_keys": total, "active_keys": active})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

@app.route("/api/admin/resellers/update", methods=["POST"])
def admin_update_reseller():
    if not is_admin(): return abort(403)
    data = request.json or {}
    rid = (data.get("reseller_id") or "").strip().upper()
    resellers = load_resellers()
    if rid not in resellers: return jsonify({"ok": False, "msg": "Not found"})
    for field in ["name", "active", "tg_id", "note"]:
        if field in data: resellers[rid][field] = data[field]
    save_resellers(resellers)
    return jsonify({"ok": True})
