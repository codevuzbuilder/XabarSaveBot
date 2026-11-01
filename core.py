"""core.py — sozlamalar, ko'p-bot (tenant) bazasi, yordamchilar, tugma dizayni, umumiy funksiyalar."""
import os, re, sys, io, csv, time, json, hmac, hashlib, sqlite3, threading, traceback, html
import requests


def _load_env(path=".env"):
    """.env faylidan KEY=VALUE qatorlarini o'qiydi (token GitHub'ga tushmasligi uchun)."""
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_FILE = os.getenv("DB_FILE", "bot.db")
if not TOKEN or not ADMIN_ID:
    sys.exit("❌ BOT_TOKEN va ADMIN_ID topilmadi. .env fayl yarating (namuna: .env.example) "
             "yoki muhit o'zgaruvchilarini kiriting.")

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, partner_id INTEGER, referrer INTEGER, sub_until INTEGER DEFAULT 0,
  is_partner INTEGER DEFAULT 0, balance REAL DEFAULT 0, banned INTEGER DEFAULT 0, n_del INTEGER DEFAULT 1,
  n_edit INTEGER DEFAULT 1, joined INTEGER DEFAULT 0, via TEXT);
CREATE TABLE IF NOT EXISTS conns(id TEXT PRIMARY KEY, user_id INTEGER);
CREATE TABLE IF NOT EXISTS msgs(cid TEXT, chat INTEGER, mid INTEGER, owner INTEGER, who TEXT, kind TEXT, text TEXT,
  fid TEXT, ts INTEGER, mine INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0, old_text TEXT, chat_name TEXT,
  PRIMARY KEY(cid,chat,mid));
CREATE TABLE IF NOT EXISTS clones(token TEXT PRIMARY KEY, owner INTEGER);
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, amount REAL,
  status TEXT DEFAULT 'pending', via TEXT, method TEXT, ext_id TEXT, url TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY, days INTEGER DEFAULT 0, money REAL DEFAULT 0, lim INTEGER DEFAULT 1,
  used INTEGER DEFAULT 0, active INTEGER DEFAULT 1, owner INTEGER);
CREATE TABLE IF NOT EXISTS promo_uses(code TEXT, user_id INTEGER, PRIMARY KEY(code,user_id));
CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY AUTOINCREMENT, chat TEXT, title TEXT, link TEXT);
CREATE TABLE IF NOT EXISTS btn_style(orig TEXT PRIMARY KEY, style TEXT);
CREATE TABLE IF NOT EXISTS btn_name(orig TEXT PRIMARY KEY, new TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS btn_icon(orig TEXT PRIMARY KEY, eid TEXT);
CREATE TABLE IF NOT EXISTS rich_media(k TEXT PRIMARY KEY, mtype TEXT, fid TEXT);
CREATE TABLE IF NOT EXISTS guides(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, text TEXT, mtype TEXT, fid TEXT);
"""
# eski bazalar bilan moslik: yetishmayotgan ustunlarni avtomatik qo'shadi
MIGRATE = {
    "users": {"partner_id": "INTEGER", "referrer": "INTEGER", "sub_until": "INTEGER DEFAULT 0",
              "is_partner": "INTEGER DEFAULT 0", "balance": "REAL DEFAULT 0", "banned": "INTEGER DEFAULT 0",
              "n_del": "INTEGER DEFAULT 1", "n_edit": "INTEGER DEFAULT 1", "joined": "INTEGER DEFAULT 0", "via": "TEXT"},
    "promos": {"owner": "INTEGER"},
    "msgs": {"ts": "INTEGER DEFAULT 0", "mine": "INTEGER DEFAULT 0", "deleted": "INTEGER DEFAULT 0",
             "old_text": "TEXT", "chat_name": "TEXT"},
    "payments": {"user_id": "INTEGER", "kind": "TEXT", "amount": "REAL", "status": "TEXT DEFAULT 'pending'",
                 "via": "TEXT", "method": "TEXT", "ext_id": "TEXT", "url": "TEXT", "ts": "INTEGER DEFAULT 0"},
}
DEF = {
    "price_7": "7000", "price_30": "20000", "price_90": "50000", "price_365": "180000",
    "partner_price": "100000", "ref_percent": "10", "topup_bonus": "0",
    "min_topup": "5000", "max_topup": "5000000", "trial_days": "30", "cache_days": "30",
    "tc_base": "https://api.tezcheck.uz/api/merchant/v1", "tc_key": "", "tc_kassa": "", "tc_ttl": "30", "tc_sign": "1",
    "tc_p_balance": "/balance", "tc_p_create": "/bills", "tc_p_status": "/bills/{id}", "stars_on": "1", "star_rate": "200",
    "click_token": "", "click_on": "0", "pay_info": "Karta: 0000 0000 0000 0000 (Ism Familiya)",
    "autopay": "0", "manual_pay": "1", "bot_on": "1", "reg_on": "1", "trial_on": "1",
    "notify_deleted": "1", "notify_edited": "1", "save_media": "1", "partner_on": "1", "ref_on": "1",
    "promo_on": "1", "notify_admin_new": "1", "force_sub": "0", "icons_on": "1", "log_chat": "",
    "welcome_text": "👋 Salom! Men chatlaringizdagi o'chirilgan va tahrirlangan xabarlarni (media bilan) sizga yetkazaman.\n\n"
                    "Boshlash uchun «📲 Botni ulash» tugmasini bosing.",
    "guide_text": "📖 <b>Qo'llanma</b>\n1) «📲 Botni ulash» tugmasi orqali akkauntni ulang.\n"
                  "2) «💳 Balans to'ldirish» va «💎 Obuna olish» orqali obuna oling.\n"
                  "3) Suhbatdosh xabarni o'chirsa yoki tahrirlasa, sizga shu yerda keladi.\n"
                  "4) 🔥 O'chib ketuvchi rasm/videoni OCHISHDAN OLDIN unga istalgan javob (reply) yozing — bot nusxasini yuboradi.",
    "faq_text": "❓ <b>Savol-javob</b>\n• Bot qanday ishlaydi? — Telegram «Chatlarni avtomatlashtirish» orqali ulangan chatlarni kuzatadi.\n"
                "• Ma'lumotlar saqlanadimi? — Vaqtincha kesh, «🗑 Keshni tozalash» bilan o'chirasiz.\n"
                "• Eski yozishmalar? — «🕘 Tarixim» PDF qilib beradi.",
    "terms_text": "📜 <b>Shartlar</b>\nBotdan faqat o'z suhbatlaringizda va qonunga muvofiq foydalaning. "
                  "Boshqalarning shaxsiy ma'lumotlarini tarqatish taqiqlanadi.",
    "support_text": "🆘 Yordam uchun adminga yozing.",
    "ref_text": "🔗 <b>Referal dasturi</b>\nDo'stlaringizni taklif qiling — ularning har bir xarididan sizga ulush tushadi.",
    "partner_text": "🤝 <b>Hamkorlik</b>\nHamkor bo'ling: o'z botingizni oling va uni to'liq o'zingiz boshqaring (admin panel, narxlar, to'lov).",
}
NUM = {"price_7", "price_30", "price_90", "price_365", "partner_price", "ref_percent", "topup_bonus",
       "min_topup", "max_topup", "trial_days", "cache_days", "tc_ttl", "star_rate"}
BOTS, STATE, ROUTES, HOOKS = {}, {}, {}, {}
ctx = threading.local()


def open_db(path):
    c = sqlite3.connect(path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    for t, cols in MIGRATE.items():
        have = {r["name"] for r in c.execute(f"PRAGMA table_info({t})")}
        for col, d in cols.items():
            if col not in have: c.execute(f"ALTER TABLE {t} ADD COLUMN {col} {d}")
    for k, v in DEF.items(): c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    if not c.execute("SELECT 1 FROM settings WHERE k='mig_trial30'").fetchone():     # eski standart (1 kun) → 30 kun, bir marta
        c.execute("UPDATE settings SET v='30' WHERE k='trial_days' AND v='1'")
        c.execute("INSERT INTO settings VALUES('mig_trial30','1')")
    if not c.execute("SELECT 1 FROM settings WHERE k='mig_tcbase'").fetchone():      # eski noto'g'ri Tezcheck manzili → rasmiy manzil
        c.execute("UPDATE settings SET v=? WHERE k='tc_base' AND v='https://tezcheck.uz/api'", (DEF['tc_base'],))
        c.execute("INSERT INTO settings VALUES('mig_tcbase','1')")
    c.commit()
    return c


# ----------------------------- tenant (har bir bot — alohida baza) -----------------------------
def cur():
    b = getattr(ctx, "b", None)
    return b if b is not None else BOTS[TOKEN]


class using:
    """with using(bot): — shu bot (tenant) bazasi va sozlamalari bilan ishlash."""
    def __init__(s, b): s.b = b
    def __enter__(s): s.old = getattr(ctx, "b", None); ctx.b = s.b
    def __exit__(s, *a): ctx.b = s.old


def q(sql, a=(), one=False):
    b = cur()
    with b.lock:
        c = b.con.execute(sql, a)
        b.con.commit()
        return c.fetchone() if one else c.fetchall()


def run(sql, a=()):
    b = cur()
    with b.lock:
        c = b.con.execute(sql, a)
        b.con.commit()
        return c.rowcount


def ins(sql, a):
    b = cur()
    with b.lock:
        c = b.con.execute(sql, a)
        b.con.commit()
        return c.lastrowid


def g(k): return q("SELECT v FROM settings WHERE k=?", (k,), True)["v"]
def setv(k, v): run("UPDATE settings SET v=? WHERE k=?", (v, k))
def num(k):
    try: return float(g(k))
    except ValueError: return 0.0


def esc(x): return html.escape(str(x if x not in (None, "") else "—"), quote=False)
def money(x): return f"{int(round(float(x))):,}".replace(",", " ")
def dt(ts): return time.strftime("%d.%m.%Y %H:%M", time.localtime(ts)) if ts > time.time() else "tugagan"
def U(uid): return q("SELECT * FROM users WHERE id=?", (uid,), True)
def is_main(): return cur().t == TOKEN
def is_admin(uid): return uid == cur().owner or bool(q("SELECT 1 FROM admins WHERE id=?", (uid,), True))
def main_bot(): return BOTS[TOKEN]


def active(uid):
    if is_admin(uid): return True
    u = U(uid)
    return bool(u and u["sub_until"] > time.time())


def elog():
    err = traceback.format_exc()
    print(err)
    with open("errors.log", "a") as f:
        f.write(time.strftime("[%d.%m.%Y %H:%M:%S]\n") + err + "\n")


def notify(uid, text): cur().send(uid, text)


def log(text):
    c = g("log_chat")
    if c: cur().send(c, text)


def route(label):
    def d(f):
        ROUTES[label] = f
        return f
    return d


# ----------------------------- umumiy funksiyalar -----------------------------
def channel_link(c):
    if c["link"]: return c["link"]
    return "https://t.me/" + c["chat"].lstrip("@") if c["chat"].startswith("@") else ""


def unsub(s, uid):
    """Foydalanuvchi a'zo bo'lmagan majburiy kanallar ro'yxati."""
    if g("force_sub") != "1" or is_admin(uid): return []
    out = []
    for c in q("SELECT * FROM channels"):
        r = s.call("getChatMember", chat_id=c["chat"], user_id=uid)
        if r is not None and r.get("status") in ("left", "kicked"): out.append(c)
    return out


def reg(uid, ref=None):
    if U(uid): return False
    if g("reg_on") != "1" and not is_admin(uid): return None
    trial = int(num("trial_days") * 86400) if g("trial_on") == "1" else 0
    r = ref if (ref and ref != uid and g("ref_on") == "1" and U(ref)) else None
    run("INSERT INTO users(id,referrer,sub_until,joined) VALUES(?,?,?,?)", (uid, r, int(time.time()) + trial, int(time.time())))
    return True


def shares(u, price):
    if u["referrer"] and g("ref_on") == "1":
        x = price * num("ref_percent") / 100
        if x > 0:
            run("UPDATE users SET balance=balance+? WHERE id=?", (x, u["referrer"]))
            notify(u["referrer"], f"🎉 Referalingiz xaridi uchun +{money(x)} so'm balansingizga tushdi.")


def redeem(uid, code):
    if g("promo_on") != "1": return "🎁 Promokodlar hozircha o'chirilgan."
    p = q("SELECT * FROM promos WHERE code=?", (code,), True)
    if not p or not p["active"] or p["used"] >= p["lim"]: return "❌ Promokod topilmadi yoki tugagan."
    if not run("INSERT OR IGNORE INTO promo_uses VALUES(?,?)", (code, uid)): return "ℹ️ Bu promokodni allaqachon ishlatgansiz."
    run("UPDATE promos SET used=used+1 WHERE code=?", (code,))
    if p["days"]:
        u = U(uid)
        run("UPDATE users SET sub_until=? WHERE id=?", (max(int(time.time()), u["sub_until"]) + p["days"] * 86400, uid))
    if p["money"]: run("UPDATE users SET balance=balance+? WHERE id=?", (p["money"], uid))
    got = []
    if p["days"]: got.append(f"{p['days']} kun obuna")
    if p["money"]: got.append(f"{money(p['money'])} so'm")
    return "🎉 Promokod faollashdi: " + " + ".join(got)


def broadcast(s, uid, group, text):
    now = int(time.time())
    cond = {"all": "1=1", "active": f"sub_until>{now}", "expired": f"sub_until<={now}", "partners": "is_partner=1"}[group]
    ids = [r["id"] for r in q(f"SELECT id FROM users WHERE banned=0 AND {cond}")]

    def work():
        n = 0
        with using(s):
            for i in ids:
                if s.call("sendMessage", chat_id=i, text=text[:4000]): n += 1
                time.sleep(0.05)
            s.send(uid, f"📢 Yuborildi: {n}/{len(ids)}")
    threading.Thread(target=work, daemon=True).start()
    s.send(uid, f"📢 Yuborish boshlandi ({len(ids)} ta).")
