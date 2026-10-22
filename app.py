import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
import requests

app = Flask(__name__)

# Sunucu RAM Veritabanı
RAM_DB = {
    "users": {},
    "messages": []
}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username:
        return jsonify({"success": False, "error": "Kullanıcı adı giriniz."}), 400

    is_admin = (password == "456456456")
    role = "admin" if is_admin else "user"

    RAM_DB["users"][username] = {
        "role": role,
        "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return jsonify({"success": True, "username": username, "role": role})

@app.route("/api/users", methods=["GET"])
def get_users():
    return jsonify(list(RAM_DB["users"].keys()))

@app.route("/api/messages", methods=["GET", "POST"])
def messages_handler():
    if request.method == "GET":
        username = request.args.get("username", "")
        user_info = RAM_DB["users"].get(username, {})
        
        if user_info.get("role") == "admin":
            return jsonify(RAM_DB["messages"])
        
        filtered = [
            m for m in RAM_DB["messages"] 
            if m["from"] == username or m["to"] == username or m["to"] == "ALL"
        ]
        return jsonify(filtered)

    elif request.method == "POST":
        data = request.json or {}
        sender = data.get("from", "").strip()
        recipient = data.get("to", "").strip()
        text = data.get("text", "").strip()

        if not sender or not recipient or not text:
            return jsonify({"success": False, "error": "Eksik bilgi."}), 400

        msg_obj = {
            "id": len(RAM_DB["messages"]) + 1,
            "from": sender,
            "to": recipient,
            "text": text,
            "time": datetime.now().strftime("%H:%M")
        }
        RAM_DB["messages"].append(msg_obj)
        return jsonify({"success": True, "message": msg_obj})

@app.route("/proxy")
def proxy():
    target_url = request.args.get("url", "").strip()
    if not target_url:
        return "<div style='color:white;padding:10px;font-family:sans-serif;'>URL girin.</div>", 400

    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        if "." not in target_url:
            target_url = f"https://m.{target_url}.com"
        else:
            target_url = f"https://{target_url}"

    try:
        # Mobil cihaz maskelemesi (iPhone Safari User-Agent)
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        resp = requests.get(target_url, headers=headers, timeout=15, allow_redirects=True)
        
        content_type = resp.headers.get("Content-Type", "text/html")
        
        # Yanıttan engelleyici güvenlik başlıklarını temizleme
        response_headers = []
        for key, val in resp.headers.items():
            if key.lower() not in ["x-frame-options", "content-security-policy", "transfer-encoding", "content-encoding"]:
                response_headers.append((key, val))

        if "text/html" in content_type:
            html = resp.text
            # Saatin ekranına sığacak şekilde viewport ve base yönlendirmesi enjekte etme
            base_tag = f'<base href="{target_url}"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">'
            if "<head>" in html:
                html = html.replace("<head>", f"<head>{base_tag}", 1)
            else:
                html = base_tag + html
            return Response(html, status=resp.status_code, headers=response_headers, content_type="text/html")

        return Response(resp.content, status=resp.status_code, headers=response_headers, content_type=content_type)
    except Exception as e:
        return f"<div style='color:red;padding:10px;font-family:sans-serif;background:#111;font-size:12px;'><b>Proxy Hatası:</b> {str(e)}</div>", 500

@app.route("/api/admin/export", methods=["GET"])
def admin_export():
    return Response(
        json.dumps(RAM_DB, indent=2, ensure_ascii=False),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=ram_db_backup.json"}
    )

@app.route("/api/admin/import", methods=["POST"])
def admin_import():
    global RAM_DB
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"success": False, "error": "Dosya yok."}), 400
        data = json.load(file)
        if "users" in data and "messages" in data:
            RAM_DB = data
            return jsonify({"success": True, "message": "RAM Yüklendi."})
        return jsonify({"success": False, "error": "Format hatalı."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
