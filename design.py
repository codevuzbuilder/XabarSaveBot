"""design.py — dizayn: tugma ranglari (ko'k → yashil → qizil), nomlarini tahrirlash va premium emoji."""
from core import *
from ui import *
from buttons import admin_rows, cat_rows, cats

MODES = {
    "color": "🎨 <b>Tugma ranglari</b>\nTugma ustiga bosing — rangi o'zgaradi: 🔵 ko'k → 🟢 yashil → 🔴 qizil → 🔵 ...",
    "name": "✏️ <b>Tugmalarni tahrirlash</b>\nTahrirlamoqchi bo'lgan tugmani bosing, keyin yangi nomini yozasiz.",
    "emoji": "💎 <b>Premium emoji</b>\nTugmani bosing, so'ng shu tugma uchun premium emojini xabar ichida yuboring.",
}
ICON = {"primary": "🔵 ko'k", "success": "🟢 yashil", "danger": "🔴 qizil"}
DONE, BACK = "✅ Tayyor", "⬅️ Hududlar"


def areas():
    d = {"👤 Foydalanuvchi menyusi": "u", "⚙️ Admin bosh sahifa": "a"}
    for ci, cl, its in cats(): d[f"{cl} bo'limi"] = f"c{ci}"
    return d


def chooser_rows():
    ks = list(areas())
    return [ks[i:i + 2] for i in range(0, len(ks), 2)] + [[(DONE, "success")]]


def area_rows(uid, key):
    return main_rows(uid) if key == "u" else admin_rows() if key == "a" else cat_rows(int(key[1:]))


def _labels(rows): return [x if isinstance(x, str) else x[0] for r in rows for x in r]


def design_start(s, uid, mode):
    STATE[uid] = ("dzarea", mode)
    s.send(uid, MODES[mode] + "\n\nQaysi bo'lim tugmalarini o'zgartirasiz?", chooser_rows())


def show_area(s, uid, mode, key, note=""):
    STATE[uid] = ("dz", mode, key)
    s.send(uid, (note + "\n\n" if note else "") + MODES[mode], area_rows(uid, key) + [[(BACK, "primary"), (DONE, "success")]])


def design_handle(s, uid, t, m, st):
    """Dizayn rejimidagi xabarni qayta ishlaydi. True — xabar shu yerda ishlatildi."""
    k = st[0]
    if k == "dzarea":
        if match_label(t, [DONE]):
            STATE.pop(uid, None); s.send(uid, "✅ Dizayn saqlandi.", admin_rows()); return True
        lab = match_label(t, list(areas()))
        if not lab: s.send(uid, "Ro'yxatdan bo'limni tanlang."); return True
        show_area(s, uid, st[1], areas()[lab]); return True
    if k == "dz":
        mode, key = st[1], st[2]
        if match_label(t, [DONE]):
            STATE.pop(uid, None); s.send(uid, "✅ Dizayn saqlandi.", admin_rows()); return True
        if match_label(t, [BACK]): design_start(s, uid, mode); return True
        rows = area_rows(uid, key)
        orig = match_label(t, _labels(rows))
        if not orig: s.send(uid, "Tugmalardan birini bosing."); return True
        if mode == "color":
            default = dict((x, "") if isinstance(x, str) else x for r in rows for x in r).get(orig) or "primary"
            cur_st = q("SELECT style FROM btn_style WHERE orig=?", (orig,), True)
            now = (cur_st["style"] if cur_st else default)
            nxt = STYLES[(STYLES.index(now) + 1) % 3] if now in STYLES else "primary"
            run("INSERT OR REPLACE INTO btn_style VALUES(?,?)", (orig, nxt))
            show_area(s, uid, mode, key, f"🎨 «{orig}»: {ICON[nxt]}")
        elif mode == "name":
            STATE[uid] = ("dzname", orig, key)
            s.send(uid, f"✏️ «{orig}» tugmasi uchun <b>yangi nom</b> kiriting.\n(Asl nomga qaytarish uchun: <code>tiklash</code>)", [[(BACK, "primary")]])
        else:
            STATE[uid] = ("dzemoji", orig, key)
            s.send(uid, f"💎 «{orig}» tugmasi uchun <b>premium emoji</b> yuboring (faqat emoji).\n"
                        f"(Olib tashlash: <code>o'chirish</code>)", [[(BACK, "primary")]])
        return True
    if k in ("dzname", "dzemoji"):
        orig, key = st[1], st[2]
        mode = "name" if k == "dzname" else "emoji"
        if match_label(t, [BACK]): show_area(s, uid, mode, key); return True
        if k == "dzname":
            new = t.strip()
            if new.lower() == "tiklash" or new == orig:
                run("DELETE FROM btn_name WHERE orig=?", (orig,)); note = f"✅ «{orig}» asl nomiga qaytdi."
            else:
                taken = set(ROUTES) | {r["new"] for r in q("SELECT new FROM btn_name WHERE orig<>?", (orig,))}
                if not 1 <= len(new) <= 40 or new in taken:
                    s.send(uid, "❌ Nom 1–40 belgi bo'lsin va boshqa tugma nomi bilan bir xil bo'lmasin. Qayta yozing:"); return True
                run("INSERT OR REPLACE INTO btn_name VALUES(?,?)", (orig, new)); note = f"✅ «{orig}» → «{new}»"
        else:
            ids = [e["custom_emoji_id"] for e in (m.get("entities") or []) if e.get("type") == "custom_emoji"]
            if ids:
                run("INSERT OR REPLACE INTO btn_icon VALUES(?,?)", (orig, ids[0])); note = f"✅ «{orig}» uchun premium emoji saqlandi."
            elif t.lower() in ("o'chirish", "ochirish"):
                run("DELETE FROM btn_icon WHERE orig=?", (orig,)); note = f"✅ «{orig}» emojisi olib tashlandi."
            else:
                s.send(uid, "❌ Premium emoji topilmadi. Premium emojini xabar ichida yuboring (Premium kerak)."); return True
        show_area(s, uid, mode, key, note); return True
    return False


# ----------------------------- premium emoji / dizayn boshqaruvi -----------------------------
def f_icons_reload(s, uid):
    n = load_emoji(s)
    s.noicons = False
    return f"🔄 Premium emoji yangilandi: {n} ta emoji topildi." if n else \
           "⚠️ Telegram premium emoji ro'yxatini bermadi. Keyinroq urinib ko'ring."


def f_icons_report(s, uid):
    des = design()
    have, miss = [], Counter()
    for l in ROUTES:
        if l.startswith("🛒") or not lead(l): continue
        (have.append(l) if icon_for(l, des[1].get(l, l), des[2], s) else miss.update([lead(l)]))
    state = "✅ yoqilgan" if g("icons_on") == "1" and not s.noicons else "❌ o'chiq (yoki Telegram qabul qilmadi)"
    return (f"💎 Premium emoji: {state}\nRo'yxatda emoji: {len(s.emap)} ta\n"
            f"Ikonka qo'yilgan tugmalar: {len(have)} ta\n"
            f"Emojisi topilmagan: {' '.join(miss) or '—'}\n\n"
            "ℹ️ Premium emoji ishlashi uchun bot egasida Telegram Premium bo'lishi kerak. "
            "Topilmaganlarini «💎 Tugmaga premium emoji» orqali o'zingiz tanlang.")


def f_design_reset(s, uid):
    for t in ("btn_style", "btn_name", "btn_icon"): run(f"DELETE FROM {t}")
    return "♻️ Dizayn tiklandi: ranglar, nomlar va emojilar standartga qaytdi."


def f_preview(s, uid): s.send(uid, "👁 Foydalanuvchi menyusi shunday ko'rinadi:", main_rows(uid))


HOOKS.update(design=design_start, icons_reload=f_icons_reload, icons_report=f_icons_report,
             design_reset=f_design_reset, preview=f_preview)
