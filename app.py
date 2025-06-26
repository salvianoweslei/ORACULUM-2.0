from flask import Flask, request
import requests
import traceback
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = "7759153655:AAF3sb4J106-_B3WdOUhbJGOw3cg9zQHLQk"
CHAT_ID = "-4974125255"
GOOGLE_SHEETS_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw9Ot6CdTZZM8Sj53Emr5LXNZS2ufN3oGJCtw2PUnFjl8KtHC11SnwtIwASyyVkB5Ya/exec"

signal_buffer = {}
SIGNAL_EXPIRATION_SECONDS = 120

STRENGTH_MAP = {"STRONG": 3, "MEDIUM": 2, "WEAK": 1}

def format_telegram_message(data):
    alert_type = data.get("type", "")
    if alert_type == "ENTRY":
        return f"""🚨 NEW SIGNAL DETECTED 🚨\n\n🆔 ID: {data.get('id')}\n📊 Asset: {data.get('asset')}\n📈 Direction: {data.get('direction')}\n💪 Strength: {data.get('strength')}\n📥 Entry: {data.get('entry')}\n🎯 TP: {data.get('tp')}\n🚩 SL: {data.get('sl')}""
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
    requests.post(url, json=payload)

def post_to_google_sheets(data):
    payload = {
        "id": data.get("id", ""),
        "asset": data.get("asset", "XAUUSD"),
        "type": data.get("type", "Signal Alert"),
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
        requests.post(GOOGLE_SHEETS_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as err:
        print("Erro ao enviar para Google Sheets:", err)

@app.route('/webhook', methods=['POST'])
def webhook():
    global signal_buffer
    try:
        data = request.get_json(force=True)

        if not isinstance(data, dict):
            return {'error': 'Invalid JSON structure'}, 400

        asset = data.get("asset", "")
        direction = data.get("direction", "")
        signal_type = data.get("type", "")
        signal_id = data.get("id", "")
        source = signal_id.split("_")[-1]  # OCR ou CND
        strength_label = data.get("strength", "")
        strength = STRENGTH_MAP.get(str(strength_label).upper(), 0)

        now = datetime.utcnow()

        if signal_type == "ENTRY":
            if asset not in signal_buffer:
                signal_buffer[asset] = {}

            signal_buffer[asset][source] = {
                "data": data,
                "timestamp": now
            }

            ocr_data = signal_buffer[asset].get("OCR")
            cnd_data = signal_buffer[asset].get("CND")

            if ocr_data and cnd_data:
                dir_match = ocr_data["data"].get("direction") == cnd_data["data"].get("direction")
                str_ocr = STRENGTH_MAP.get(ocr_data["data"].get("strength", "").upper(), 0)
                str_cnd = STRENGTH_MAP.get(cnd_data["data"].get("strength", "").upper(), 0)

                if dir_match and str_ocr >= 2 and str_cnd >= 2:
                    message = format_telegram_message(ocr_data["data"])
                    send_telegram_message(message)
                    post_to_google_sheets(ocr_data["data"])
                    signal_buffer[asset] = {}

        elif signal_type in ["TP", "SL", "CANCEL"]:
            message = format_telegram_message(data)
            send_telegram_message(message)
            post_to_google_sheets(data)

        for sym in list(signal_buffer.keys()):
            for src in list(signal_buffer[sym].keys()):
                if (now - signal_buffer[sym][src]["timestamp"]).total_seconds() > SIGNAL_EXPIRATION_SECONDS:
                    del signal_buffer[sym][src]

        return {'ok': True}, 200

    except Exception as e:
        error_trace = traceback.format_exc()
        send_telegram_message(f"❗Erro no webhook:\n<code>{error_trace}</code>")
        return {'error': str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True)
