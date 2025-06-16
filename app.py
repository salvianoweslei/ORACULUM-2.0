from flask import Flask, request
import requests
import traceback

app = Flask(__name__)

TELEGRAM_TOKEN = "7759153655:AAF3sb4J106-_B3WdOUhbJGOw3cg9zQHLQk"
CHAT_ID = "-4974125255"
GOOGLE_SHEETS_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbym8oShblrXl3jpSDVL-uFoNwWA3EUUJDALr8YYOAlxX9WzvYK6-LeZzxNoRs0tuWWp/exec"

def format_telegram_message(data):
    alert_type = data.get("type", "")

    if alert_type == "ENTRY":
        return f"""🚨 NEW SIGNAL DETECTED 🚨\n\n🆔 ID: {data.get('id')}\n📊 Asset: {data.get('asset')}\n📈 Direction: {data.get('direction')}\n💪 Strength: {data.get('strength')}\n📥 Entry: {data.get('entry')}\n🎯 TP: {data.get('tp')}\n🚩 SL: {data.get('sl')}"""
    elif alert_type == "CANCEL":
        return f"""⚠️ SIGNAL CANCELLED ⚠️\n\n🆔 ID: {data.get('id')}\n📈 Previous Direction: {data.get('direction')}\n💪 Strength: {data.get('strength')}\nReason: Opposite signal detected within 3 bars."""
    elif alert_type == "TP":
        return f"""🎯 TAKE PROFIT HIT 🎯\n\n🆔 ID: {data.get('id')}\n📈 Direction: {data.get('direction')}\n💪 Strength: {data.get('strength')}\n💰 Closed at: {data.get('closed_at')}"""
    elif alert_type == "SL":
        return f"""🚩 STOP LOSS HIT 🚩\n\n🆔 ID: {data.get('id')}\n📈 Direction: {data.get('direction')}\n💪 Strength: {data.get('strength')}\n💰 Closed at: {data.get('closed_at')}"""
    else:
        return str(data)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Telegram Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print("Erro ao enviar para Telegram:", e)

def post_to_google_sheets(data):
    payload = {
        "id": data.get("id", ""),
        "asset": data.get("asset", ""),
        "type": data.get("type", ""),
        "direction": data.get("direction", ""),
        "strength": data.get("strength", ""),
        "confidence": data.get("confidence", ""),
        "entry": data.get("entry", ""),
        "tp": data.get("tp", ""),
        "sl": data.get("sl", ""),
        "closed_at": data.get("closed_at", ""),
        "timestamp": data.get("timestamp", "")
    }
    try:
        response = requests.post(GOOGLE_SHEETS_WEBHOOK_URL, json=payload, timeout=5)
        print(f"Google Sheets Status: {response.status_code}, Response: {response.text}")
    except Exception as err:
        print("Erro ao enviar para Google Sheets:", err)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        raw_body = request.data.decode("utf-8")
        print("==== RAW INCOMING PAYLOAD ====")
        print(raw_body)
        print("=================================")

        json_data = None
        try:
            json_data = request.get_json(force=True)
        except Exception as parse_err:
            print("Erro ao fazer parse do JSON:", parse_err)

        if json_data and isinstance(json_data, dict) and "type" in json_data:
            message = format_telegram_message(json_data)
            send_telegram_message(message)
            post_to_google_sheets(json_data)
        else:
            print("JSON inválido ou sem campo 'type', enviando como texto simples.")
            message = raw_body if raw_body else '🚨 Alerta recebido sem conteúdo.'
            send_telegram_message(message)

        return {'ok': True}, 200

    except Exception as e:
        error_trace = traceback.format_exc()
        send_telegram_message(f"❗Erro no webhook:\n<code>{error_trace}</code>")
        return {'error': str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True)
