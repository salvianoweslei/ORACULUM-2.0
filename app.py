from flask import Flask, request
import requests
import traceback
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = "7759153655:AAF3sb4J106-_B3WdOUhbJGOw3cg9zQHLQk"
CHAT_ID = "-4974125255"
GOOGLE_SHEETS_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbw9Ot6CdTZZM8Sj53Emr5LXNZS2ufN3oGJCtw2PUnFjl8KtHC11SnwtIwASyyVkB5Ya/exec"

# Memória de sinais recebidos (buffer por ativo)
signal_buffer = {}
SIGNAL_EXPIRATION_SECONDS = 120  # tempo de validade dos sinais no buffer

def format_telegram_message(data):
    alert_type = data.get("type", "")
    if alert_type == "ENTRY":
        return f"""\U0001F6A8 NEW SIGNAL DETECTED \U0001F6A8\n\n\U0001F194 ID: {data.get('id')}\n\U0001F4CA Asset: {data.get('asset')}\n\U0001F4C8 Direction: {data.get('direction')}\n\U0001F4AA Strength: {data.get('strength')}\n\U0001F4E5 Entry: {data.get('entry')}\n\U0001F3AF TP: {data.get('tp')}\n\U0001F6A9 SL: {data.get('sl')}"""
    elif alert_type == "CANCEL":
        return f"""\u26A0\uFE0F SIGNAL CANCELLED \u26A0\uFE0F\n\n\U0001F194 ID: {data.get('id')}\n\U0001F4C8 Previous Direction: {data.get('direction')}\n\U0001F4AA Strength: {data.get('strength')}\nReason: Opposite signal detected within 3 bars."""
    elif alert_type == "TP":
        return f"""\U0001F3AF TAKE PROFIT HIT \U0001F3AF\n\n\U0001F194 ID: {data.get('id')}\n\U0001F4C8 Direction: {data.get('direction')}\n\U0001F4AA Strength: {data.get('strength')}\n\U0001F4B0 Closed at: {data.get('closed_at')}"""
    elif alert_type == "SL":
        return f"""\U0001F6A9 STOP LOSS HIT \U0001F6A9\n\n\U0001F194 ID: {data.get('id')}\n\U0001F4C8 Direction: {data.get('direction')}\n\U0001F4AA Strength: {data.get('strength')}\n\U0001F4B0 Closed at: {data.get('closed_at')}"""
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
        data = None
        try:
            data = request.get_json(force=True)
        except Exception as e:
            print("Erro ao interpretar JSON:", e)
            raw_data = request.data.decode("utf-8").strip()
            if raw_data:
                send_telegram_message(f"\u26A0\ufe0f Alerta recebido sem JSON válido:\n\n<code>{raw_data}</code>")
            else:
                send_telegram_message("\u26A0\ufe0f Alerta recebido sem conteúdo.")
            return {'error': 'Invalid JSON'}, 400

        asset = data.get("asset", "")
        direction = data.get("direction", "")
        signal_type = data.get("type", "")
        strength = int(data.get("strength", "0"))
        signal_id = data.get("id", "")
        source = signal_id.split("_")[-1]  # OCR ou CND

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
                if (ocr_data["data"].get("direction") == cnd_data["data"].get("direction") and
                    abs(int(ocr_data["data"].get("strength", "0"))) >= 2 and
                    abs(int(cnd_data["data"].get("strength", "0"))) >= 2):

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
        send_telegram_message(f"\u2757Erro no webhook:\n<code>{error_trace}</code>")
        return {'error': str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True)
