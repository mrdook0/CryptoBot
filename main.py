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
COOLDOWN_TIME = 180  # 3 دقائق

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

def advanced_technical_analysis(closes):
    series = pd.Series(closes)
    
    deltas = series.diff()
    gain = (deltas.where(deltas > 0, 0)).rolling(window=14).mean()
    loss = (-deltas.where(deltas < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    ema_50 = series.ewm(span=50, adjust=False).mean().iloc[-1]
    ema_200 = series.ewm(span=200, adjust=False).mean().iloc[-1]

    sma_20 = series.rolling(window=20).mean().iloc[-1]
    std_20 = series.rolling(window=20).std().iloc[-1]
    upper_band = sma_20 + (std_20 * 2)
    lower_band = sma_20 - (std_20 * 2)
    current_price = closes[-1]

    score = 0
    reasons = []

    if current_rsi < 38:
        score += 2
        reasons.append("مؤشر RSI في منطقة تشبع بيعي (ارتداد محتمل)")
    elif current_rsi > 65:
        score -= 1
        reasons.append("مؤشر RSI مرتفع نسبياً")

    if current_price > ema_50:
        score += 1
        reasons.append("السعر فوق متوسط EMA 50 (اتجاه قصير إيجابي)")
        
    if current_price <= lower_band * 1.01:
        score += 2
        reasons.append("السعر لامس حد بولينجر السفلي (دعم قوي)")

    return current_rsi, ema_50, ema_200, score, reasons

def get_current_price(symbol):
    urls = [
        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"
    ]
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=5)
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
                        time.sleep(0.5)
            if updated:
                save_deals(deals)
        except:
            pass
        time.sleep(120)

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
        "مرحباً بك في Senza Crypto Signals!💸\n\n"
        "اختر الخيار المطلوب من الأزرار أدناه:\n"
        "• تحليل السوق: جلب أفضل الفرص الحالية عبر فحص السوق.\n"
        "• تحليل عملة واحدة: إدخال اسم عملة لفحصها بدقة عميقة.\n"
        "• الصفقات الناجحة والفاشلة: لمتابعة سجل الأداء بكل شفافية.\n\n"
        "هذا البوت مجاني من w3t_o؛ استخدامه على مسؤوليتك الخاصة."
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
                minutes = remaining_time // 60
                seconds = remaining_time % 60
                bot.answer_callback_query(call.id, f"⏳ الرجاء الانتظار {minutes}د و {seconds}ث لحماية الخادم.", show_alert=True)
                return

        user_cooldowns[user_id] = current_time
        bot.answer_callback_query(call.id, "جاري تحليل السوق...")
        bot.send_message(chat_id, "🔍 جاري فحص السوق والبحث عن أفضل الفرص ذات الموثوقية العالية...")

        symbols = get_binance_spot_symbols()
        if not symbols:
            bot.send_message(chat_id, "❌ تعذر الاتصال بسوق بايننس حالياً.")
            return

        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        found_opportunities = []
        deals = load_deals()

        for symbol in symbols[:80]:
            if len(found_opportunities) >= 3:
                break

            urls = [
                f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=100",
                f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1h&limit=100"
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
                    
            if not isinstance(data, list) or len(data) < 50:
                continue
                
            try:
                closes = [float(candle[4]) for candle in data]
                current_price = closes[-1]
                
                if current_price > 1.00:
                    continue
                    
                rsi, ema50, ema200, score, reasons = advanced_technical_analysis(closes)
                
                if score >= 2:
                    tp1 = current_price * 1.035
                    tp2 = current_price * 1.070
                    sl = current_price * 0.965
                    
                    reasons_text = "\n".join([f"• {r}" for r in reasons])
                    opp_msg = (
                        f"🚨 فرصة تحليل سوق دقيقة 🚨\n\n"
                        f"💎 العملة: {symbol}\n"
                        f"💰 السعر الحالي: {current_price}\n"
                        f"📊 مؤشر RSI: {rsi:.2f}\n"
                        f"📈 الأسباب الفنية:\n{reasons_text}\n\n"
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
                time.sleep(0.5)
        else:
            bot.send_message(chat_id, "📉 لا توجد فرص تطابق المعايير الفنية بدقة حالياً. جرب لاحقاً.")

    elif call.data == "btn_single":
        user_states[user_id] = "waiting_for_symbol"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "✍️ أرسل الآن اسم العملة التي تريد تحليلها بدقة (مثال: BTCUSDT أو PEPEUSDT):")

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
        if user_id in user_states:
            del user_states[user_id]
        bot.answer_callback_query(call.id, "تم إنهاء العملية بنجاح.")
        bot.send_message(chat_id, "✅ تم إنهاء العملية وإغلاق القائمة النشطة. يمكنك إرسال /start في أي وقت لاستئناف العمل.")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_states.get(user_id) == "waiting_for_symbol":
        symbol = message.text.strip().upper()
        if not symbol.endswith("USDT"):
            symbol += "USDT"

        bot.send_message(chat_id, f"🔍 جاري إجراء تحليل فني عميق ومتقدم للعملة {symbol} باستخدام عدة مؤشرات...")
        
        urls = [
            f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=100",
            f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1h&limit=100"
        ]
        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        data = None
        for url in urls:
            try:
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    break
            except:
                continue

        if not isinstance(data, list) or len(data) < 50:
            bot.send_message(chat_id, f"❌ تعذر العثور على بيانات كافية للعملة {symbol}. تأكد من صحة الرمز.")
            user_states.pop(user_id, None)
            return

        try:
            closes = [float(candle[4]) for candle in data]
            current_price = closes[-1]
            rsi, ema50, ema200, score, reasons = advanced_technical_analysis(closes)

            tp1 = current_price * 1.035
            tp2 = current_price * 1.070
            sl = current_price * 0.965

            reasons_text = "\n".join([f"• {r}" for r in reasons]) if reasons else "• تحليل السعر الحالي واستقرار الدعم."
            
            analysis_report = (
                f"🎯 تحليل عميق ودقيق لعملة واحدة 🎯\n\n"
                f"💎 العملة: {symbol}\n"
                f"💰 السعر الحالي: {current_price}\n"
                f"📊 مؤشر RSI: {rsi:.2f}\n"
                f"📉 متوسط EMA 50: {ema50:.5f}\n"
                f"📈 تقييم الزخم الفني: {'إيجابي قوي ✨' if score >= 2 else 'حذر / محايد ⚠️'}\n\n"
                f"🔍 أبرز الملاحظات الفنية:\n{reasons_text}\n\n"
                f"🎯 الأهداف المقترحة بدقة:\n"
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

        except Exception as e:
            bot.send_message(chat_id, f"❌ حدث خطأ أثناء تحليل البيانات: {e}")

        user_states.pop(user_id, None)
    else:
        bot.reply_to(message, "الرجاء استخدام الأوامر أو الضغط على الأزرار التفاعلية عبر إرسال /start", reply_markup=main_menu_keyboard())

if __name__ == "__main__":
    print("البوت التفاعلي SENZA CRYPTO SIGNALS يعمل الآن...")
    # إزالة أي اتصالات معلقة سابقة لمنع حدوث خطأ Conflict 409
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(skip_pending=True)
if __name__ == "__main__":
    print("البوت التفاعلي Senza Crypto Signals يعمل الآن...")
    while True:
        try:
            bot.remove_webhook()
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"حدث خطأ، إعادة المحاولة خلال 5 ثوانٍ: {e}")
            time.sleep(5)
