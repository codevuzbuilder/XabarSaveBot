"""pay.py — Tezcheck (hisob/kassa API), Click (Telegram to'lov), avto-to'lov ulash ustasi, fon vazifalari."""
import os, time, json, sqlite3
import requests
from core import *

# ======================= TEZCHECK (hujjatga moslang) =======================
# Hisob API (balans) va Kassa API (schot yaratish / holat) yo'llari.
# Tezcheck hujjatidagi haqiqiy yo'llar bilan almashtiring.
TC_PATHS = {
    "balance": ("GET", "/account/balance"),         # hisob API
    "create": ("POST", "/cashbox/invoice"),         # kassa API: schot yaratish
    "status": ("GET", "/cashbox/invoice/{id}"),     # kassa API: schot holati
}
# ===========================================================================


def _pick(d, keys):
    if isinstance(d, dict):
        for k in keys:
            if d.get(k) not in (None, ""): return d[k]


def tc_call(name, payload=None, **fmt):
    meth, path = TC_PATHS[name]
    key = g("tc_key") if name == "balance" else g("tc_kassa")     # hisob API / kassa API
    body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
    h = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer " + key}
    r = requests.request(meth, g("tc_base").rstrip("/") + path.format(**fmt), data=body or None, headers=h, timeout=30)
    try: j = r.json()
    except ValueError: raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400: raise RuntimeError(f"HTTP {r.status_code}: {str(j)[:200]}")
    if not isinstance(j, dict): return {"value": j}
    for k in ("data", "result"):
        if isinstance(j.get(k), dict): return j[k]
    return j


def tc_create(pid, amount):
    j = tc_call("create", {"amount": int(amount), "order_id": str(pid), "description": "Balans to'ldirish"})
    url = _pick(j, ("pay_url", "payment_url", "checkout_url", "url", "link"))
    if not url: raise RuntimeError("to'lov havolasi kelmadi: " + str(j)[:200])
    return str(_pick(j, ("id", "invoice_id", "transaction_id", "order_id")) or pid), url


def tc_state(p):
    j = tc_call("status", id=p["ext_id"])
    st = str(_pick(j, ("status", "state")) or "").lower()
    if st in ("paid", "success", "succeeded", "completed", "done", "approved") or j.get("paid") is True: return "paid"
    if st in ("expired", "canceled", "cancelled", "failed", "rejected"): return "failed"
    return "pending"


def tc_balance():
    j = tc_call("balance")
    return _pick(j, ("balance", "amount", "available", "value")) or j


def credit(pid):
    if not run("UPDATE payments SET status='approved' WHERE id=? AND status='pending'", (pid,)): return False
    p = q("SELECT * FROM payments WHERE id=?", (pid,), True)
    add = p["amount"] * (1 + num("topup_bonus") / 100)
    run("UPDATE users SET balance=balance+? WHERE id=?", (add, p["user_id"]))
    notify(p["user_id"], f"✅ Hisobingiz <b>{money(add)}</b> so'mga to'ldirildi!")
    log(f"💵 To'lov #{pid}: {p['user_id']} — {money(p['amount'])} so'm ({p['method']})")
    return True


def check_payment(p):
    st = tc_state(p)
    if st == "paid": credit(p["id"])
    elif st == "failed" or time.time() - p["ts"] > num("tc_ttl") * 60:
        if run("UPDATE payments SET status='expired' WHERE id=? AND status='pending'", (p["id"],)):
            notify(p["user_id"], f"⌛ To'lov #{p['id']} muddati tugadi yoki bekor qilindi.")


# ----------------------------- Click (Telegram to'lovlari, BotFather → Payments → Click) -----------------------------
def click_invoice(s, uid, amt):
    pid = ins("INSERT INTO payments(user_id,kind,amount,via,method,ts) VALUES(?,?,?,?,?,?)",
              (uid, "topup", amt, s.t, "click", int(time.time())))
    r = s.call("sendInvoice", chat_id=uid, title="Balans to'ldirish", description=f"{money(amt)} so'm",
               payload=f"topup:{pid}", provider_token=g("click_token"), currency="UZS",
               prices=[{"label": "Balans", "amount": int(amt) * 100}])
    if r is None:
        run("UPDATE payments SET status='failed' WHERE id=?", (pid,))
        main_err = s.err
        s.send(s.owner, f"⚠️ Click xatosi: {esc(main_err)}")
        return False
    return True


def pre_checkout(s, pq):
    m = re.match(r"topup:(\d+)$", pq.get("invoice_payload", ""))
    p = q("SELECT * FROM payments WHERE id=?", (int(m.group(1)),), True) if m else None
    ok = bool(p and p["status"] == "pending" and p["method"] == "click" and pq.get("total_amount") == int(p["amount"]) * 100)
    args = {"pre_checkout_query_id": pq["id"], "ok": ok}
    if not ok: args["error_message"] = "To'lov topilmadi yoki muddati o'tgan. Qaytadan urinib ko'ring."
    s.call("answerPreCheckoutQuery", **args)


def successful_payment(s, m):
    sp = m["successful_payment"]
    mt = re.match(r"topup:(\d+)$", sp.get("invoice_payload", ""))
    if mt and credit(int(mt.group(1))): return
    if not mt: s.send(s.owner, f"⚠️ Noma'lum to'lov keldi: {esc(sp)}")


# ----------------------------- avto to'lov ulash ustalari -----------------------------
WIZ_BACK = [[("⬅️ Admin panel", "primary")]]


def wizard_start(s, uid, kind):
    if kind == "tc":
        STATE[uid] = ("wiz", "tc1")
        s.send(uid, "⚡ <b>Avto to'lov (tezcheck.uz)</b>\n1/2 — <b>Hisob API</b> kalitini kiriting:", WIZ_BACK)
    else:
        STATE[uid] = ("wiz", "click")
        s.send(uid, "💳 <b>Click ulash</b>\n@BotFather → /mybots → botingiz → <b>Payments</b> → <b>Click</b> ni ulang "
                    "va berilgan <b>provider token</b>ni shu yerga yuboring:", WIZ_BACK)


def wizard_step(s, uid, st, m):
    t = (m.get("text") or "").strip()
    s.call("deleteMessage", chat_id=uid, message_id=m["message_id"])     # maxfiy kalit chatda qolmasin
    if st[1] == "tc1":
        setv("tc_key", t)
        STATE[uid] = ("wiz", "tc2")
        return s.send(uid, "✅ Hisob API saqlandi.\n2/2 — <b>Kassa API</b> kalitini kiriting:", WIZ_BACK)
    if st[1] == "tc2":
        setv("tc_kassa", t); setv("autopay", "1")
        STATE.pop(uid, None)
        try: res = f"Hisob balansi: <b>{esc(tc_balance())}</b>"
        except Exception as e: res = f"⚠️ Tekshiruvda xato: {esc(e)}\n(kalitlarni va fayl boshidagi TC_PATHS yo'llarini tekshiring)"
        return s.send(uid, f"✅ <b>Avto to'lov yoqildi!</b>\n{res}")
    if st[1] == "click":
        r = s.call("createInvoiceLink", title="Test", description="Test", payload="test", provider_token=t,
                   currency="UZS", prices=[{"label": "Test", "amount": 100000}])
        STATE.pop(uid, None)
        if r is None: return s.send(uid, f"❌ Token qabul qilinmadi: {esc(s.err)}")
        setv("click_token", t); setv("click_on", "1")
        return s.send(uid, "✅ <b>Click ulandi va yoqildi!</b> Endi foydalanuvchilar «💳 Click orqali» tugmasini ko'radi.")


# ----------------------------- fon vazifalari -----------------------------
def poller():
    while True:
        time.sleep(15)
        for b in list(BOTS.values()):
            try:
                with using(b):
                    if g("autopay") != "1" or not g("tc_key"): continue
                    for p in q("SELECT * FROM payments WHERE status='pending' AND method='tc'"):
                        try: check_payment(p)
                        except Exception: elog()
            except Exception: elog()


def backup_to_admin(b, chat=None):
    """Shu bot bazasining zaxira nusxasini uning egasiga yuboradi."""
    dst = sqlite3.connect("backup_tmp.db")
    with b.lock: b.con.backup(dst)
    dst.close()
    with open("backup_tmp.db", "rb") as f: data = f.read()
    os.remove("backup_tmp.db")
    b.upload("sendDocument", "document", "bot_backup.db", data, chat_id=chat or b.owner,
             caption=time.strftime("💾 Zaxira %d.%m.%Y %H:%M"), disable_notification="true")


def cleaner():
    hours = 0
    while True:
        for b in list(BOTS.values()):
            try:
                with using(b):
                    run("DELETE FROM msgs WHERE ts<?", (int(time.time() - num("cache_days") * 86400),))
                    n = int(os.getenv("BACKUP_HOURS", "0") or 0)     # 0 = o'chiq
                    if n and hours and hours % n == 0: backup_to_admin(b)
            except Exception: elog()
        hours += 1
        time.sleep(3600)
