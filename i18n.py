"""i18n.py — ko'p tillilik (8 til): xabarlar va tugma nomlari tarjimasi; o'zbek-kirill avtomatik o'giriladi."""
import re
from core import *
from lang_data import UZ, RU
from lang_data2 import EN, TR
from lang_data3 import KK, TG
from lang_data4 import KY

LANGS = [("uz", "🇺🇿 O'zbekcha"), ("uzc", "🇺🇿 Ўзбекча"), ("ru", "🇷🇺 Русский"), ("en", "🇬🇧 English"),
         ("tr", "🇹🇷 Türkçe"), ("kk", "🇰🇿 Қазақша"), ("tg", "🇹🇯 Тоҷикӣ"), ("ky", "🇰🇬 Кыргызча")]
CODES = [c for c, _ in LANGS]
MSG = {"ru": RU, "en": EN, "tr": TR, "kk": KK, "tg": TG, "ky": KY}
# Telegram language_code → bot tili
AUTO = {"uz": "uz", "ru": "ru", "en": "en", "tr": "tr", "kk": "kk", "tg": "tg", "ky": "ky"}
DAYS = {"uz": "kun", "uzc": "кун", "ru": "дн.", "en": "days", "tr": "gün", "kk": "күн", "tg": "рӯз", "ky": "күн"}

_L = ["📲 Botni ulash", "💎 Obuna olish", "💳 Balans to'ldirish", "👤 Profilim", "📅 Obunam", "🧾 To'lovlarim",
      "🎁 Promokod", "🔗 Referal", "🤝 Hamkorlik", "🤖 Mening botim", "🕘 Tarixim", "📊 Statistikam",
      "🗑 Keshni tozalash", "📖 Qo'llanma", "❓ Savol-javob", "🆘 Yordam", "📜 Shartlar", "🏠 Menyu",
      "✅ A'zo bo'ldim", "✅ To'lovni tekshirish", "💳 Click orqali", "⭐ Stars orqali", "🧾 Chek bilan to'lov",
      "⚡ Checkout orqali", "⚡ InPay orqali", "✅ Hamkor bo'lish", "🌐 Tilni almashtirish", "🤖 Bot sahifasi"]
_T = {
 "ru": "📲 Подключить бота|💎 Купить подписку|💳 Пополнить баланс|👤 Мой профиль|📅 Моя подписка|🧾 Мои платежи|🎁 Промокод|🔗 Рефералы|🤝 Партнёрство|🤖 Мой бот|🕘 Моя история|📊 Моя статистика|🗑 Очистить кэш|📖 Инструкция|❓ Вопросы и ответы|🆘 Помощь|📜 Условия|🏠 Меню|✅ Я подписался|✅ Проверить платёж|💳 Через Click|⭐ Через Stars|🧾 По чеку|⚡ Через Checkout|⚡ Через InPay|✅ Стать партнёром|🌐 Сменить язык|🤖 Страница бота",
 "en": "📲 Connect bot|💎 Buy subscription|💳 Top up balance|👤 My profile|📅 My subscription|🧾 My payments|🎁 Promo code|🔗 Referral|🤝 Partnership|🤖 My bot|🕘 My history|📊 My stats|🗑 Clear cache|📖 Guide|❓ FAQ|🆘 Help|📜 Terms|🏠 Menu|✅ I joined|✅ Check payment|💳 Via Click|⭐ Via Stars|🧾 By receipt|⚡ Via Checkout|⚡ Via InPay|✅ Become a partner|🌐 Change language|🤖 Bot page",
 "tr": "📲 Botu bağla|💎 Abonelik al|💳 Bakiye yükle|👤 Profilim|📅 Aboneliğim|🧾 Ödemelerim|🎁 Promosyon kodu|🔗 Referans|🤝 Ortaklık|🤖 Botum|🕘 Geçmişim|📊 İstatistiklerim|🗑 Önbelleği temizle|📖 Kılavuz|❓ SSS|🆘 Yardım|📜 Şartlar|🏠 Menü|✅ Katıldım|✅ Ödemeyi kontrol et|💳 Click ile|⭐ Stars ile|🧾 Dekont ile|⚡ Checkout ile|⚡ InPay ile|✅ Ortak ol|🌐 Dili değiştir|🤖 Bot sayfası",
 "kk": "📲 Ботты қосу|💎 Жазылым алу|💳 Балансты толтыру|👤 Профилім|📅 Жазылымым|🧾 Төлемдерім|🎁 Промокод|🔗 Рефералдық|🤝 Серіктестік|🤖 Менің ботым|🕘 Тарихым|📊 Статистикам|🗑 Кэшті тазалау|📖 Нұсқаулық|❓ Сұрақ-жауап|🆘 Көмек|📜 Шарттар|🏠 Мәзір|✅ Қосылдым|✅ Төлемді тексеру|💳 Click арқылы|⭐ Stars арқылы|🧾 Чекпен төлеу|⚡ Checkout арқылы|⚡ InPay арқылы|✅ Серіктес болу|🌐 Тілді ауыстыру|🤖 Бот беті",
 "tg": "📲 Пайваст кардани бот|💎 Харидани обуна|💳 Пур кардани баланс|👤 Профили ман|📅 Обунаи ман|🧾 Пардохтҳои ман|🎁 Промокод|🔗 Реферал|🤝 Ҳамкорӣ|🤖 Боти ман|🕘 Таърихи ман|📊 Омори ман|🗑 Тоза кардани кэш|📖 Дастур|❓ Савол-ҷавоб|🆘 Кумак|📜 Шартҳо|🏠 Меню|✅ Узв шудам|✅ Санҷиши пардохт|💳 Тавассути Click|⭐ Тавассути Stars|🧾 Бо чек|⚡ Тавассути Checkout|⚡ Тавассути InPay|✅ Ҳамкор шудан|🌐 Иваз кардани забон|🤖 Саҳифаи бот",
 "ky": "📲 Ботту туташтыруу|💎 Жазылуу сатып алуу|💳 Балансты толуктоо|👤 Профилим|📅 Жазылуум|🧾 Төлөмдөрүм|🎁 Промокод|🔗 Реферал|🤝 Өнөктөштүк|🤖 Менин ботум|🕘 Тарыхым|📊 Статистикам|🗑 Кэшти тазалоо|📖 Колдонмо|❓ Суроо-жооп|🆘 Жардам|📜 Шарттар|🏠 Меню|✅ Кошулдум|✅ Төлөмдү текшерүү|💳 Click аркылуу|⭐ Stars аркылуу|🧾 Чек менен|⚡ Checkout аркылуу|⚡ InPay аркылуу|✅ Өнөктөш болуу|🌐 Тилди алмаштыруу|🤖 Бот барагы",
}
LAB = {lg: dict(zip(_L, v.split("|"))) for lg, v in _T.items()}

# ----------------------------- o'zbek lotin → kirill -----------------------------
_PROT = re.compile(r"(<[^>]*>|\{[^}]*\}|https?://\S+|@\w+|/\w+|\b(?:ID|PDF|Stars|Click|InPay|Checkout|Premium|Telegram|Chat automation)\b)")
_APOS = "'ʼ’‘`ʻ"
_S = dict(zip("abdefghijklmnopqrstuvxyz", "абдефгҳижклмнопқрстувхйз"))
_S["g"] = "г"


def _case(src, out): return out.upper() if src[:1].isupper() and (len(src) == 1 or src[1:].isupper() or len(out) == 1) else out.capitalize() if src[:1].isupper() else out


def _lat2cyr(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c, nx = s[i], s[i + 1] if i + 1 < n else ""
        lo, pair = c.lower(), (c + nx).lower()
        start = i == 0 or not s[i - 1].isalpha()
        if lo in "og" and nx in _APOS: out.append(_case(c, "ў" if lo == "o" else "ғ")); i += 2; continue
        if pair in ("sh", "ch"): out.append(_case(c + nx, "ш" if pair == "sh" else "ч")); i += 2; continue
        if pair == "ng": out.append(_case(c + nx, "нг")); i += 2; continue
        if pair in ("yo", "yu", "ya"): out.append(_case(c + nx, {"yo": "ё", "yu": "ю", "ya": "я"}[pair])); i += 2; continue
        if pair == "ye" and start: out.append(_case(c, "е")); i += 2; continue
        if lo == "e" and start: out.append(_case(c, "э")); i += 1; continue
        if c in _APOS: out.append("ъ"); i += 1; continue
        out.append(_case(c, _S[lo]) if lo in _S else c); i += 1
    return "".join(out)


def cyr(text):
    return "".join(p if (i % 2) else _lat2cyr(p) for i, p in enumerate(_PROT.split(text)))


# ----------------------------- tarjima funksiyalari -----------------------------
def cur_lang(): return getattr(ctx, "lang", None) or "uz"


def ulang(uid):
    u = U(uid) if uid else None
    try: l = u["lang"] if u else None
    except (IndexError, KeyError): l = None
    return l if l in CODES else "uz"


class lang_as:
    """with lang_as('ru'): — vaqtincha til (tugma nomlari shu tilda chiqadi)."""
    def __init__(s, lang): s.lang = lang
    def __enter__(s): s.old = getattr(ctx, "lang", None); ctx.lang = s.lang
    def __exit__(s, *a): ctx.lang = s.old


def tr(key, uid=None, lang=None, **kw):
    lg = lang or (ulang(uid) if uid else cur_lang())
    base = UZ[key]
    txt = cyr(base) if lg == "uzc" else MSG.get(lg, {}).get(key, base) if lg != "uz" else base
    try: return txt.format(**kw) if kw else txt
    except Exception as e:
        print(f'tr() format xato ({key}): {e}'); return txt


def lab(label, lang=None):
    """Tugma nomini tilga o'giradi (🛒 N kun ham)."""
    lg = lang or cur_lang()
    if lg == "uz": return label
    m = re.fullmatch(r"🛒 (\d+) kun", label)
    if m: return f"🛒 {m.group(1)} {DAYS.get(lg, 'kun')}"
    return cyr(label) if lg == "uzc" else LAB.get(lg, {}).get(label, label)


_REV = {}


def rev_labels():
    """Tarjima qilingan (va emojisiz kelgan) tugma matni → asl o'zbekcha nom."""
    if not _REV:
        for lg in CODES:
            for l in list(_L) + [f"🛒 {d} kun" for d in (7, 30, 90, 365)]:
                t = lab(l, lg)
                _REV.setdefault(t, l)
                _REV.setdefault(re.sub(r"^[^\w\s'’`\"«(\[]+\s*", "", t), l)
    return _REV
