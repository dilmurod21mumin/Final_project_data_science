import telebot
import joblib
import pandas as pd
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sklearn.base import BaseEstimator, ClassifierMixin  # kerak bo'ladi

# ProbaPredictor klassini qayta e'lon qilamiz
class ProbaPredictor(BaseEstimator, ClassifierMixin):
    """Saved inside churn_pipeline.pkl to make .predict() return probability."""
    def __init__(self, model):
        self.model = model
    def fit(self, X, y=None):
        return self
    def predict(self, X):
        return self.model.predict_proba(X)[:, 1]
    def predict_proba(self, X):
        return self.model.predict_proba(X)

# Modelni (preprocessing + classifier + ProbaPredictor) yuklaymiz
MODEL_PATH = 'churn_pipeline.pkl'         
model = joblib.load(MODEL_PATH)

# TelegramBot token
TOKEN = '8150677891:AAEff5-CLcWo7P2bQ7UpFds8WQQUjMP82tA'
bot   = telebot.TeleBot(TOKEN)

#  Model xususiyatlari va UI matnlari
features = ['gender','SeniorCitizen','Partner','Dependents','tenure','PhoneService',
            'MultipleLines','InternetService','OnlineSecurity','OnlineBackup',
            'DeviceProtection','TechSupport','StreamingTV','StreamingMovies',
            'Contract','PaperlessBilling','PaymentMethod','MonthlyCharges','TotalCharges']

instructions = {  
    'gender': "👤 Jinsingizni tanlang:",
    'SeniorCitizen': "👴 Yoshi katta (senior) fuqaromisiz?",
    'Partner': "💍 Sizning turmush o‘rtog‘ingiz bormi?",
    'Dependents': "👶 Sizga qaram (bola, qarindosh) mavjudmi?",
    'tenure': "📅 Necha oydan beri bizning xizmatimizdasiz? (0 - 72 oralig‘ida son kiriting)",
    'PhoneService': "📞 Telefon xizmati bormi?",
    'MultipleLines': "📱 Bir nechta telefon liniyalari mavjudmi?",
    'InternetService': "🌐 Internet xizmati turi:",
    'OnlineSecurity': "🔐 Onlayn xavfsizlik xizmati:",
    'OnlineBackup': "💾 Onlayn nusxa ko‘chirish xizmati:",
    'DeviceProtection': "🛡 Qurilma himoyasi xizmati:",
    'TechSupport': "🧰 Texnik yordam xizmati:",
    'StreamingTV': "📺 Onlayn TV xizmati:",
    'StreamingMovies': "🎬 Onlayn kino xizmati:",
    'Contract': "📄 Shartnoma turi:",
    'PaperlessBilling': "📧 Qog‘ozsiz to‘lovdan foydalanasizmi?",
    'PaymentMethod': "💳 To‘lov usulingiz:",
    'MonthlyCharges': "💵 Oylik to‘lovni kiriting (masalan: 70.5):",
    'TotalCharges': "💰 Umumiy to‘langan summani kiriting (masalan: 3500):"
}

options = { 
    'gender': ['Erkak', 'Ayol'],
    'SeniorCitizen': ['Ha', 'Yo‘q'],
    'Partner': ['Ha', 'Yo‘q'],
    'Dependents': ['Ha', 'Yo‘q'],
    'PhoneService': ['Bor', 'Yo‘q'],
    'MultipleLines': ['Bor', 'Yo‘q', 'Telefon yo‘q'],
    'InternetService': ['DSL', 'Optik tolali', 'Yo‘q'],
    'OnlineSecurity': ['Bor', 'Yo‘q', 'Internet yo‘q'],
    'OnlineBackup': ['Bor', 'Yo‘q', 'Internet yo‘q'],
    'DeviceProtection': ['Bor', 'Yo‘q', 'Internet yo‘q'],
    'TechSupport': ['Bor', 'Yo‘q', 'Internet yo‘q'],
    'StreamingTV': ['Bor', 'Yo‘q', 'Internet yo‘q'],
    'StreamingMovies': ['Bor', 'Yo‘q', 'Internet yo‘q'],
    'Contract': ['Oylik', '1 yil', '2 yil'],
    'PaperlessBilling': ['Ha', 'Yo‘q'],
    'PaymentMethod': ['Elektron chek', 'Pochta orqali chek', 'Bank avtomatik', 'Kredit karta']
}

user_data = {}

# Bot buyruqlari
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "📊 Salom! Men Telecom mijozning ketishini bashorat qiluvchi botman.\n"
        "➡️ Bashoratni boshlash uchun /predict ni yuboring."
    )

@bot.message_handler(commands=['predict'])
def handle_predict(message):
    chat_id = message.chat.id
    user_data[chat_id] = []
    ask_next_feature(message, 0)

def ask_next_feature(message, idx):
    chat_id = message.chat.id
    if idx:
        user_data[chat_id].append(message.text)

    if idx < len(features):
        feat = features[idx]
        prompt = instructions.get(feat, f"{feat} ni kiriting:")
        markup = ReplyKeyboardRemove()

        if feat in options:
            markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for opt in options[feat]:
                markup.add(KeyboardButton(opt))

        bot.send_message(chat_id, prompt, reply_markup=markup)
        bot.register_next_step_handler(message, lambda m: ask_next_feature(m, idx + 1))
    else:
        bot.send_message(chat_id, "✅ Barcha ma'lumotlar olindi. Natijani hisoblamoqdamiz...")
        predict_result(chat_id)

def predict_result(chat_id):
    df_input = pd.DataFrame([user_data[chat_id]], columns=features)

    # SeniorCitizen: Ha/Yo‘q → 1/0
    if df_input['SeniorCitizen'].iloc[0] in ['Ha', 'Yo‘q']:
        df_input['SeniorCitizen'] = df_input['SeniorCitizen'].map({'Ha': 1, 'Yo‘q': 0})

    # Raqamli ustunlarni son ko'rinishiga o'tkazish
    num_cols = ['SeniorCitizen', 'tenure', 'MonthlyCharges', 'TotalCharges']
    df_input[num_cols] = df_input[num_cols].apply(pd.to_numeric, errors='coerce')

    df_input[num_cols] = df_input[num_cols].fillna(df_input[num_cols].median())
    
    try:
        # Endi faqat predict — preprocessing pipeline ichida bo‘ladi
        score = model.predict(df_input)[0]          # 0 ↔ 1 ehtimollik
        foiz  = round(score * 100, 2)
        natija = "🚨 Mijoz ketadi!" if score > 0.5 else "✅ Mijoz qoladi."
        bot.send_message(chat_id, f"🔮 Natija: {natija}\n📈 Ketish ehtimolligi: {foiz}%")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Xatolik yuz berdi: {e}")

#  Botni ishga tushurish
print("🤖 Bot ishga tushdi...")
bot.infinity_polling()