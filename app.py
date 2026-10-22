import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
import requests

app = Flask(__name__)

# Sunucu RAM Veritabanı (Kalıcı Tutulur)
RAM_DB = {
    "users": {},     # username -> {"role": "admin"|"user", "last_login": "..."}
    "messages": []   # [{"id": 1, "from": "...", "to": "...", "text": "...", "time": "..."}, ...]
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

    # 456456456 şifresi girilirse Admin, aksi halde normal Kullanıcı
    is_admin = (password == "456456456")
    role = "admin" if is_admin else "user"

    RAM_DB["users"][username] = {
        "role": role,
        "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return jsonify({
        "success": True,
        "username": username,
        "role": role
    })

@app.route("/api/users", methods=["GET"])
def get_users():
    return jsonify(list(RAM_DB["users"].keys()))

@app.route("/api/messages", methods=["GET", "POST"])
def messages_handler():
    if request.method == "GET":
        username = request.args.get("username", "")
        user_info = RAM_DB["users"].get(username, {})
        
        # Admin tüm mesajları görür, kullanıcı sadece kendisine ve herkese atılanları görür
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
            return jsonify({"success": False, "error": "Mesaj bilgileri eksik."}), 400

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
        return "<div style='color:white;padding:20px;font-family:sans-serif;'>Gezinmek için bir URL girin.</div>", 400

    # Otomatik protokol düzeltici
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        if "." not in target_url:
            target_url = f"https://www.{target_url}.com"
        else:
            target_url = f"https://{target_url}"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(target_url, headers=headers, timeout=15)
        content_type = resp.headers.get("Content-Type", "text/html")

        # HTML sayfaları için base tag enjekte etme (resimler ve bağlar düzgün yüklensin diye)
        if "text/html" in content_type:
            html = resp.text
            base_tag = f'<base href="{target_url}">'
            if "<head>" in html:
                html = html.replace("<head>", f"<head>{base_tag}", 1)
            else:
                html = base_tag + html
            return Response(html, content_type="text/html")

        return Response(resp.content, content_type=content_type)
    except Exception as e:
        return f"<div style='color:red;padding:15px;font-family:sans-serif;background:#222;'><b>ProxWeb Tünel Hatası:</b> {str(e)}</div>", 500

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
            return jsonify({"success": False, "error": "Dosya seçilmedi."}), 400
        data = json.load(file)
        if "users" in data and "messages" in data:
            RAM_DB = data
            return jsonify({"success": True, "message": "RAM verileri başarıyla yüklendi."})
        return jsonify({"success": False, "error": "Format geçersiz."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
