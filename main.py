import os
import time
import json
import threading
import telebot
from telebot import types
import requests
import pandas as pd
from datetime import datetime

# ==================== الإعدادات الخاصة بك ====================
TELEGRAM_BOT_TOKEN = "8954641721:AAHBWmlTuO7GOU6JuWvhDHfqjSj1lSCf8fY"
BINANCE_API_KEY = "NCFYVdVIzzr5xurb9LwtpgUoHbE7bX3nr9mq7WVsLSPxetNC8FIbCWnPONVbJxdm"
# ============================================================

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

user_states = {}
user_cooldowns = {}
COOLDOWN_TIME = 60  # تقليل وقت الانتظار إلى دقيقة واحدة

HISTORY_FILE = "deals_history.json"

def load_deals():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_deals(deals):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(deals, f, ensure_ascii=False, indent=4)
    except:
        pass

def get_binance_spot_symbols():
    urls = [
        "https://api.binance.com/api/v3/exchangeInfo",
        "https://data-api.binance.vision/api/v3/exchangeInfo"
    ]
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=5)
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

def get_current_price(symbol):
    urls = [
        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"
    ]
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=3)
            if res.status_code == 200:
                return float(res.json()['price'])
        except:
            continue
    return None

def track_deals_background():
    while True:
        try:
            deals = load_deals()
            updated = False
            for deal in deals:
                if deal.get('status') == 'ACTIVE':
                    symbol = deal['symbol']
                    price = get_current_price(symbol)
                    if price:
                        if price <= deal['sl']:
                            deal['status'] = 'FAILED'
                            deal['achieved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            deal['result_note'] = "ضربت وقف الخسارة (SL) ❌ (-3.5%)"
                            updated = True
                        elif price >= deal['tp2']:
                            deal['status'] = 'SUCCESS_ALL'
                            deal['achieved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            deal['result_note'] = "حققت كافة الأهداف (TP1 & TP2) ✨ (+7.0%)"
                            updated = True
                        elif price >= deal['tp1']:
                            deal['status'] = 'SUCCESS_TP1'
                            deal['achieved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            deal['result_note'] = "حققت الهدف الأول (TP1) 🎯 (+3.5%)"
                            updated = True
                        time.sleep(0.3)
            if updated:
                save_deals(deals)
        except:
            pass
        time.sleep(60)

threading.Thread(target=track_deals_background, daemon=True).start()

def main_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_market = types.InlineKeyboardButton("📊 تحليل السوق", callback_data="btn_market")
    btn_single = types.InlineKeyboardButton("🔍 تحليل عملة واحدة", callback_data="btn_single")
    btn_success = types.InlineKeyboardButton("🏆 الصفقات الناجحة", callback_data="btn_success")
    btn_failed = types.InlineKeyboardButton("❌ الصفقات الفاشلة", callback_data="btn_failed")
    btn_exit = types.InlineKeyboardButton("🚫 إنهاء العملية", callback_data="btn_exit")
    
    markup.add(btn_market, btn_single)
    markup.add(btn_success, btn_failed)
    markup.add(btn_exit)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "مرحباً بك في SENZA CRYPTO SIGNALS!\n\n"
        "اختر الخيار المطلوب من الأزرار أدناه:\n"
        "• تحليل السوق: جلب الفرص ذات السعر المنخفض بسرعة.\n"
        "• تحليل عملة واحدة: فحص أي عملة بدقة.\n"
        "• الصفقات الناجحة والفاشلة: لمتابعة الأداء بكل شفافية.\n\n"
        "هذا البوت مجاني من w3t_o."
    )
    bot.reply_to(message, welcome_text, reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "btn_market":
        current_time = datetime.now()
        if user_id in user_cooldowns:
            elapsed_time = (current_time - user_cooldowns[user_id]).total_seconds()
            if elapsed_time < COOLDOWN_TIME:
                remaining_time = int(COOLDOWN_TIME - elapsed_time)
                bot.answer_callback_query(call.id, f"⏳ الرجاء الانتظار {remaining_time} ثانية لحماية الخادم.", show_alert=True)
                return

        user_cooldowns[user_id] = current_time
        bot.answer_callback_query(call.id, "جاري فحص السوق...")
        bot.send_message(chat_id, "🔍 جاري فحص السوق وإحضار أفضل الصفقات الرخيصة فوراً...")

        symbols = get_binance_spot_symbols()
        if not symbols:
            bot.send_message(chat_id, "❌ تعذر الاتصال بسوق بايننس حالياً.")
            return

        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        found_opportunities = []
        deals = load_deals()

        # فحص أول 30 عملة فقط لضمان السرعة الفائقة وعدم التعليق
        for symbol in symbols[:30]:
            if len(found_opportunities) >= 3:
                break

            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=15"
            try:
                res = requests.get(url, headers=headers, timeout=3)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and len(data) >= 5:
                        closes = [float(candle[4]) for candle in data]
                        current_price = closes[-1]
                        
                        # التركيز على العملات رخيصة الثمن (أقل من 1 دولار)
                        if current_price > 1.00:
                            continue
                        
                        price_change = ((closes[-1] - closes[0]) / closes[0]) * 100
                        
                        if price_change >= -2.0:
                            tp1 = current_price * 1.035
                            tp2 = current_price * 1.070
                            sl = current_price * 0.965
                            
                            opp_msg = (
                                f"🚨 صفقة رخيصة واعدة 🚨\n\n"
                                f"💎 العملة: {symbol}\n"
                                f"💰 السعر الحالي: {current_price}\n"
                                f"📈 التغير: {price_change:.2f}%\n\n"
                                f"🎯 الأهداف:\n"
                                f"• TP1: {tp1:.5f} (+3.5%)\n"
                                f"• TP2: {tp2:.5f} (+7.0%)\n"
                                f"🛑 SL: {sl:.5f} (-3.5%)\n\n"
                                f"🛡️ SENZA CRYPTO SIGNALS"
                            )
                            found_opportunities.append(opp_msg)

                            if not any(d.get('symbol') == symbol and d.get('status') == 'ACTIVE' for d in deals):
                                deals.append({
                                    "symbol": symbol,
                                    "entry": current_price,
                                    "tp1": tp1,
                                    "tp2": tp2,
                                    "sl": sl,
                                    "status": "ACTIVE",
                                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "result_note": ""
                                })
            except:
                continue

        save_deals(deals)

        if found_opportunities:
            for opp in found_opportunities:
                bot.send_message(chat_id, opp)
                time.sleep(0.3)
        else:
            bot.send_message(chat_id, "📉 لم يتم العثور على فرص مناسبة في الوقت الحالي، جرب بعد لحظات.")

    elif call.data == "btn_single":
        user_states[user_id] = "waiting_for_symbol"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "✍️ أرسل الآن اسم العملة التي تريد تحليلها (مثال: PEPEUSDT أو DOGEUSDT):")

    elif call.data == "btn_success":
        bot.answer_callback_query(call.id, "جاري جلب الصفقات الناجحة...")
        deals = load_deals()
        successful_deals = [d for d in deals if d.get('status') in ['SUCCESS_TP1', 'SUCCESS_ALL']]

        if not successful_deals:
            bot.send_message(chat_id, "🏆 سجل الصفقات الناجحة\n\nلا توجد صفقات محققة للأهداف حتى الآن.")
            return

        report = "🏆 سجل الصفقات الناجحة 🏆\n\n"
        for idx, deal in enumerate(reversed(successful_deals[-10:]), 1):
            report += (
                f"{idx}. 💎 العملة: {deal.get('symbol')}\n"
                f"   💰 الدخول: {deal.get('entry')}\n"
                f"   ✨ النتيجة: {deal.get('result_note')}\n"
                f"   📅 التاريخ: {deal.get('achieved_at', deal.get('created_at'))}\n"
                f"----------------------------------------\n"
            )
        report += "\n🛡️ SENZA CRYPTO SIGNALS"
        bot.send_message(chat_id, report)

    elif call.data == "btn_failed":
        bot.answer_callback_query(call.id, "جاري جلب الصفقات الفاشلة...")
        deals = load_deals()
        failed_deals = [d for d in deals if d.get('status') == 'FAILED']

        if not failed_deals:
            bot.send_message(chat_id, "❌ سجل الصفقات الفاشلة\n\nرائع! لا توجد صفقات ضربت وقف الخسارة.")
            return

        report = "❌ سجل الصفقات الفاشلة ❌\n\n"
        for idx, deal in enumerate(reversed(failed_deals[-10:]), 1):
            report += (
                f"{idx}. 💎 العملة: {deal.get('symbol')}\n"
                f"   💰 الدخول: {deal.get('entry')}\n"
                f"   ⚠️ النتيجة: {deal.get('result_note')}\n"
                f"   📅 التاريخ: {deal.get('achieved_at', deal.get('created_at'))}\n"
                f"----------------------------------------\n"
            )
        report += "\n🛡️ SENZA CRYPTO SIGNALS"
        bot.send_message(chat_id, report)

    elif call.data == "btn_exit":
        user_states.pop(user_id, None)
        bot.answer_callback_query(call.id, "تم إنهاء العملية بنجاح.")
        bot.send_message(chat_id, "✅ تم إنهاء العملية وإغلاق القائمة النشطة. أرسل /start لاستئناف العمل.")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_states.get(user_id) == "waiting_for_symbol":
        symbol = message.text.strip().upper()
        if not symbol.endswith("USDT"):
            symbol += "USDT"

        user_states.pop(user_id, None)
        bot.send_message(chat_id, f"🔍 جاري فحص العملة {symbol}...")
        
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=15"
        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        try:
            res = requests.get(url, headers=headers, timeout=3)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) >= 5:
                    closes = [float(candle[4]) for candle in data]
                    current_price = closes[-1]

                    tp1 = current_price * 1.035
                    tp2 = current_price * 1.070
                    sl = current_price * 0.965
                    
                    analysis_report = (
                        f"🎯 تحليل العملة المطلوبة 🎯\n\n"
                        f"💎 العملة: {symbol}\n"
                        f"💰 السعر الحالي: {current_price}\n\n"
                        f"🎯 الأهداف المقترحة:\n"
                        f"• الهدف الأول (TP1): {tp1:.5f} (+3.5%)\n"
                        f"• الهدف الثاني (TP2): {tp2:.5f} (+7.0%)\n"
                        f"🛑 وقف الخسارة (SL): {sl:.5f} (-3.5%)\n\n"
                        f"🛡️ SENZA CRYPTO SIGNALS"
                    )
                    bot.send_message(chat_id, analysis_report)

                    deals = load_deals()
                    if not any(d.get('symbol') == symbol and d.get('status') == 'ACTIVE' for d in deals):
                        deals.append({
                            "symbol": symbol,
                            "entry": current_price,
                            "tp1": tp1,
                            "tp2": tp2,
                            "sl": sl,
                            "status": "ACTIVE",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "result_note": ""
                        })
                        save_deals(deals)
                    return
        except:
            pass
        bot.send_message(chat_id, f"❌ تعذر العثور على بيانات للعملة {symbol}. تأكد من صحة الرمز.")
    else:
        bot.reply_to(message, "الرجاء استخدام الأوامر أو الضغط على الأزرار التفاعلية عبر إرسال /start", reply_markup=main_menu_keyboard())

def start_bot_safely():
    try:
        bot.remove_webhook()
        time.sleep(2)
    except:
        pass

    while True:
        try:
            print("جاري تشغيل البوت SENZA CRYPTO SIGNALS بنجاح...")
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            err_str = str(e)
            if "409" in err_str or "Conflict" in err_str:
                print("تم اكتشاف جلسة سابقة معلقة، يتم الانتظار 5 ثوانٍ...")
                time.sleep(5)
            else:
                print(f"حدث انقطاع مؤقت: {e}، إعادة الاتصال بعد 3 ثوانٍ...")
                time.sleep(3)

if __name__ == "__main__":
    start_bot_safely()
