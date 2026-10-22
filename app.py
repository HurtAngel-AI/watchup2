import os
import json
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from playwright.async_api import async_playwright

app = Flask(__name__)

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

async def fetch_page_screenshot(target_url):
    async with async_playwright() as p:
        # Mobil cihaz ekranını simüle eden sanal tarayıcı
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 360, "height": 640},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=15000)
        except Exception:
            pass # Zaman aşımında yine de yüklenen kadarını al
            
        content = await page.content()
        await browser.close()
        return content

@app.route("/proxy")
def proxy():
    target_url = request.args.get("url", "").strip()
    if not target_url:
        return "<div style='color:white;padding:10px;'>URL girin.</div>", 400

    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = f"https://m.{target_url}.com" if "." not in target_url else f"https://{target_url}"

    try:
        html = asyncio.run(fetch_page_screenshot(target_url))
        base_tag = f'<base href="{target_url}"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">'
        
        if "<head>" in html:
            html = html.replace("<head>", f"<head>{base_tag}", 1)
        else:
            html = base_tag + html
            
        return Response(html, content_type="text/html")
    except Exception as e:
        return f"<div style='color:red;padding:10px;background:#111;'><b>Sanal Tarayıcı Hatası:</b> {str(e)}</div>", 500

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
