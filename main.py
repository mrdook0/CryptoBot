import time
import telebot
import requests
import pandas as pd
from datetime import datetime, timedelta

# ==================== الإعدادات الخاصة بك ====================
TELEGRAM_BOT_TOKEN = "8954641721:AAHBWmlTuO7GOU6JuWvhDHfqjSj1lSCf8fY"
BINANCE_API_KEY = "NCFYVdVIzzr5xurb9LwtpgUoHbE7bX3nr9mq7WVsLSPxetNC8FIbCWnPONVbJxdm"
# ============================================================

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# قاموس لتتبع وقت آخر طلب لكل مستخدم (لتطبيق الـ Cooldown)
user_cooldowns = {}
COOLDOWN_TIME = 180  # 3 دقائق بالثواني

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
        except:
            continue
    return []

def calculate_rsi(prices, period=14):
    deltas = pd.Series(prices).diff()
    gain = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
    loss = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "مرحباً بك في بوت التداول الرسمي! 🤖\n\n"
        "يمكنك استخدام الأمر التالي للبحث عن أفضل الفرص الحالية في السوق:\n"
        "📊 /top - جلب أفضل 3 فرص تداول (RSI منخفض وسعر مناسب)\n\n"
        "🛡️ *ملاحظة:* يوجد نظام حماية بانتظار 3 دقائق بين كل طلب بحث لحماية النظام."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
def get_top_opportunities(message):
    user_id = message.from_user.id
    current_time = datetime.now()

    # التحقق من نظام الـ Cooldown
    if user_id in user_cooldowns:
        elapsed_time = (current_time - user_cooldowns[user_id]).total_seconds()
        if elapsed_time < COOLDOWN_TIME:
            remaining_time = int(COOLDOWN_TIME - elapsed_time)
            minutes = remaining_time // 60
            seconds = remaining_time % 60
            bot.reply_to(message, f"⏳ عذراً، يجب عليك الانتظار `{minutes} دقيقة و {seconds} ثانية` قبل طلب فحص جديد لحماية الخادم.", parse_mode="Markdown")
            return

    # تحديث وقت آخر طلب للمستخدم
    user_cooldowns[user_id] = current_time

    bot.reply_to(message, "🔍 جاري فحص السوق والبحث عن أفضل 3 فرص متاحة الآن... قد يستغرق ذلك بضع ثوانٍ.")

    symbols = get_binance_spot_symbols()
    if not symbols:
        bot.reply_to(message, "❌ تعذر الاتصال بسوق بايننس حالياً. حاول مرة أخرى لاحقاً.")
        return

    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    found_opportunities = []

    # نفحص مجموعة من العملات لجلب أفضل 3 فرص فقط
    for symbol in symbols[:60]:
        if len(found_opportunities) >= 3:
            break

        urls = [
            f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=50",
            f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1h&limit=50"
        ]
        
        data = None
        for url in urls:
            try:
                res = requests.get(url, headers=headers, timeout=5)
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
            
            if current_price > 0.50:
                continue
                
            rsi = calculate_rsi(closes)
            
            if rsi < 35:
                tp1 = current_price * 1.035
                tp2 = current_price * 1.070
                sl = current_price * 0.965
                
                opp_msg = (
                    f"🚨 *فرصة تداول قوية* 🚨\n\n"
                    f"💎 العملة: `{symbol}`\n"
                    f"💰 السعر الحالي: `{current_price}`\n"
                    f"📊 مؤشر RSI: `{rsi:.2f}`\n\n"
                    f"🎯 الأهداف:\n"
                    f"• TP1: `{tp1:.5f}` (+3.5%)\n"
                    f"• TP2: `{tp2:.5f}` (+7.0%)\n"
                    f"🛑 SL: `{sl:.5f}` (-3.5%)\n\n"
                    f"🛡️ *Bot Official Signals*"
                )
                found_opportunities.append(opp_msg)
        except:
            continue

    if found_opportunities:
        for opp in found_opportunities:
            bot.send_message(message.chat.id, opp, parse_mode="Markdown")
            time.sleep(0.5)
    else:
        bot.reply_to(message, "📉 لم يتم العثور على فرص تطابق الشروط بدقة عالية في هذه اللحظة. جرب مرة أخرى لاحقاً.")

if __name__ == "__main__":
    print("البوت التفاعلي يعمل الآن وينتظر الأوامر...")
    # استخدام طريقة Polling لتلقي الأوامر من التليقرام
    bot.infinity_polling()
