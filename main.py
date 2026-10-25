import time
import requests
import pandas as pd

# ==================== الإعدادات الخاصة بك ====================
TELEGRAM_BOT_TOKEN = "8954641721:AAHBWmlTuO7GOU6JuWvhDHfqjSj1lSCf8fY"
TELEGRAM_CHAT_ID = "7918037614"
BINANCE_API_KEY = "NCFYVdVIzzr5xurb9LwtpgUoHbE7bX3nr9mq7WVsLSPxetNC8FIbCWnPONVbJxdm"
# ============================================================

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

def get_binance_spot_symbols():
    urls = [
        "https://api.binance.com/api/v3/exchangeInfo",
        "https://data-api.binance.vision/api/v3/exchangeInfo"
    ]
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                symbols = []
                for s in data.get('symbols', []):
                    if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT':
                        symbols.append(s['symbol'])
                return symbols
        except Exception as e:
            continue
    print("خطأ في جلب العملات من كافة الروابط المتاحة.")
    return []

def calculate_rsi(prices, period=14):
    deltas = pd.Series(prices).diff()
    gain = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
    loss = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def analyze_market():
    print("جاري فحص سوق بايننس...")
    symbols = get_binance_spot_symbols()
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    
    if not symbols:
        return

    for symbol in symbols[:50]: 
        urls = [
            f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=50",
            f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1h&limit=50"
        ]
        
        data = None
        for url in urls:
            try:
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    break
            except:
                continue
                
        if not isinstance(data, list):
            continue
            
        try:
            closes = [float(candle[4]) for candle in data]
            current_price = closes[-1]
            
            # فلترة العملات ذات السعر المنخفض (أقل من 0.50 دولار)
            if current_price > 0.50:
                continue
                
            rsi = calculate_rsi(closes)
            
            # إذا كان مؤشر RSI أقل من 35 (منطقة ارتداد وفرصة قوية)
            if rsi < 35:
                tp1 = current_price * 1.035
                tp2 = current_price * 1.070
                sl = current_price * 0.965
                
                msg = (
                    f"🚨 *فرصة تداول فورية دقيقة* 🚨\n\n"
                    f"💎 العملة: `{symbol}`\n"
                    f"💰 السعر الحالي: `{current_price}`\n"
                    f"📊 مؤشر RSI: `{rsi:.2f}` (فرصة ارتداد محتملة)\n\n"
                    f"🎯 الأهداف المقترحة:\n"
                    f"• الهدف الأول (TP1): `{tp1:.5f}` (+3.5%)\n"
                    f"• الهدف الثاني (TP2): `{tp2:.5f}` (+7.0%)\n"
                    f"🛑 وقف الخسارة (SL): `{sl:.5f}` (-3.5%)\n\n"
                    f"🛡️ *Bot Official Signals*"
                )
                send_telegram_message(msg)
                time.sleep(1)
        except Exception as e:
            continue

if __name__ == "__main__":
    print("البوت بدأ العمل ببيانات بايننس الحقيقية...")
    while True:
        analyze_market()
        # يفحص السوق كل 30 دقيقة لتجنب حظر الـ API
        time.sleep(1800)
