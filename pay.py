"""pay.py — Tezcheck, Click, Telegram Stars, avto-to'lov ustalari va fon vazifalari."""
import os, re, time, json, math, hmac, hashlib, sqlite3
from urllib.parse import urlparse
import requests
from core import *


class TcError(Exception):
    pass


def _pick(d, keys):
    if isinstance(d, dict):
        for k in keys:
            if d.get(k) not in (None, ""): return d[k]


# ----------------------------- Tezcheck (Hisob API kaliti + Kassa kodi) -----------------------------
def tc_req(method, path, payload=None, headers=None):
    """Tezcheck so'rovi: Bearer Hisob API kaliti (+ ixtiyoriy HMAC imzo). Xatoda manzil va javob matni xabarda bo'ladi."""
    url = g("tc_base").rstrip("/") + path
    body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
    h = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer " + g("tc_key")}
    if g("tc_sign") == "1":
        ts = str(int(time.time()))
        msg = "\n".join([method, urlparse(url).path, ts, hashlib.sha256(body.encode()).hexdigest()])
        h["X-Timestamp"], h["X-Signature"] = ts, hmac.new(g("tc_key").encode(), msg.encode(), hashlib.sha256).hexdigest()
    h.update(headers or {})
    try: r = requests.request(method, url, data=body or None, headers=h, timeout=30)
    except requests.RequestException as e: raise TcError(f"{method} {url} → ulanish xatosi: {e}")
    try: j = r.json()
    except ValueError: j = None
    if r.status_code >= 400: raise TcError(f"{method} {url} → HTTP {r.status_code}: {(r.text or '')[:160]}")
    if not isinstance(j, dict): return {"value": j}
    for k in ("data", "result"):
        if isinstance(j.get(k), dict): return j[k]
    return j


def tc_create(pid, amount):
    j = tc_req("POST", g("tc_p_create"),
               {"amount": int(amount) * 100, "currency": "UZS", "external_reference": str(pid),
                "cash_desk": g("tc_kassa"), "description": "Balans to'ldirish"},
               {"Idempotency-Key": f"{cur().t.split(':')[0]}-topup-{pid}"})
    url = _pick(j, ("pay_url", "payment_url", "checkout_url", "url", "link", "payment_link"))
    if not url or not str(url).startswith("http"): raise TcError("to'lov havolasi kelmadi: " + str(j)[:160])
    return str(_pick(j, ("id", "bill_id", "uuid")) or pid), url


def tc_state(p):
    j = tc_req("GET", g("tc_p_status").format(id=p["ext_id"]))
    st = str(_pick(j, ("status", "state")) or "").lower()
    if st in ("paid", "success", "succeeded", "completed", "done", "approved") or j.get("paid") is True: return "paid"
    if st in ("expired", "canceled", "cancelled", "failed", "rejected"): return "failed"
    return "pending"


def tc_balance():
    j = tc_req("GET", g("tc_p_balance"))
    return _pick(j, ("balance", "amount", "available", "value")) or j


def tc_diag():
    """Ulanishni tekshiradi va har bir so'rov natijasini (HTTP kod, javob) ko'rsatadi."""
    lines, codes = [f"🌐 {g('tc_base')}", f"🔏 Imzo: {'yoqilgan' if g('tc_sign') == '1' else 'o‘chiq'}"], []
    for path in ("/me", "/cash-desks", g("tc_p_balance")):
        try:
            tc_req("GET", path); lines.append(f"✅ {path} — 200"); codes.append(200)
        except TcError as e:
            m = re.search(r"HTTP (\d+)", str(e)); codes.append(int(m.group(1)) if m else 0)
            lines.append(f"❌ {path} — {str(e).split('→')[-1].strip()[:150]}")
    hint = ""
    if codes and all(c == 404 for c in codes):
        hint = "\n\n💡 Hammasi 404 — API manzil noto'g'ri. «🌐 Tezcheck API manzil» ni tekshiring (taxminiy: https://api.tezcheck.uz/api/merchant/v1)."
    elif any(c in (401, 403) for c in codes):
        hint = "\n\n💡 401/403 — Hisob API kaliti noto'g'ri yoki imzo mos emas. «🔏 Imzo yoq/o'ch» ni almashtirib ko'ring."
    return "\n".join(lines) + hint


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


# ----------------------------- Click (BotFather → Payments → Click) va Telegram Stars -----------------------------
def click_invoice(s, uid, amt):
    pid = ins("INSERT INTO payments(user_id,kind,amount,via,method,ts) VALUES(?,?,?,?,?,?)",
              (uid, "topup", amt, s.t, "click", int(time.time())))
    r = s.call("sendInvoice", chat_id=uid, title="Balans to'ldirish", description=f"{money(amt)} so'm",
               payload=f"topup:{pid}", provider_token=g("click_token"), currency="UZS",
               prices=[{"label": "Balans", "amount": int(amt) * 100}])
    if r is None:
        run("UPDATE payments SET status='failed' WHERE id=?", (pid,))
        s.send(s.owner, f"⚠️ Click xatosi: {esc(s.err)}")
        return False
    return True


def stars_for(amt): return max(1, math.ceil(amt / max(num("star_rate"), 1)))


def stars_invoice(s, uid, amt):
    """Telegram Stars (XTR): provider token kerak emas. Stars soni = so'm / kurs (yuqoriga yaxlitlanadi)."""
    n = stars_for(amt)
    pid = ins("INSERT INTO payments(user_id,kind,amount,via,method,ext_id,ts) VALUES(?,?,?,?,?,?,?)",
              (uid, "topup", amt, s.t, "stars", str(n), int(time.time())))
    r = s.call("sendInvoice", chat_id=uid, title="Balans to'ldirish", description=f"{money(amt)} so'm — ⭐ {n} Stars",
               payload=f"topup:{pid}", currency="XTR", prices=[{"label": "Balans", "amount": n}])
    if r is None:
        run("UPDATE payments SET status='failed' WHERE id=?", (pid,))
        s.send(s.owner, f"⚠️ Stars xatosi: {esc(s.err)}")
        return 0
    return n


def _paid_ok(p, currency, total):
    """To'lov summasi va valyutasi bazadagi buyurtmaga mosligini tekshiradi."""
    if not p or p["status"] != "pending": return False
    if p["method"] == "click": return currency == "UZS" and total == int(p["amount"]) * 100
    if p["method"] == "stars": return currency == "XTR" and total == int(p["ext_id"] or 0)
    return False


def _payment_of(payload):
    m = re.match(r"topup:(\d+)$", payload or "")
    return q("SELECT * FROM payments WHERE id=?", (int(m.group(1)),), True) if m else None


def pre_checkout(s, pq):
    ok = _paid_ok(_payment_of(pq.get("invoice_payload")), pq.get("currency"), pq.get("total_amount"))
    args = {"pre_checkout_query_id": pq["id"], "ok": ok}
    if not ok: args["error_message"] = "To'lov topilmadi yoki muddati o'tgan. Qaytadan urinib ko'ring."
    s.call("answerPreCheckoutQuery", **args)


def successful_payment(s, m):
    sp = m["successful_payment"]
    p = _payment_of(sp.get("invoice_payload"))
    if _paid_ok(p, sp.get("currency"), sp.get("total_amount")): credit(p["id"])
    elif not (p and p["status"] == "approved"):
        s.send(s.owner, f"⚠️ Mos kelmagan to'lov keldi: {esc(sp)}")


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
        return s.send(uid, "✅ Hisob API saqlandi.\n2/2 — <b>Kassa API</b> (kassa kodi) ni kiriting:", WIZ_BACK)
    if st[1] == "tc2":
        setv("tc_kassa", t); setv("autopay", "1")
        STATE.pop(uid, None)
        return s.send(uid, "✅ <b>Avto to'lov yoqildi!</b>\n\n" + tc_diag())
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
