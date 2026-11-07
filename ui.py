"""ui.py — tugma dizayni: rang, nom, premium emoji (ikonka), klaviatura va inline tugmalar, bosh menyu."""
from collections import Counter
from core import *
from i18n import *


# ----------------------------- tugma dizayni: rang, nom, premium emoji -----------------------------
_LEAD = re.compile(r"^([^\w\s'’`\"«(\[]+)\s*")
STYLES = ["primary", "success", "danger"]
# premium emoji ro'yxatida aynan shu emoji bo'lmasa, o'xshash variantlar sinab ko'riladi
EMOJI_ALT = {k: v.split() for k, v in {
    "📲": "📱 💬", "💎": "💯 ⭐", "💳": "💰 💵", "💰": "💵 ⭐", "📅": "🗓 📆", "🧾": "📝 📰", "🎁": "🎉 🏆",
    "🔗": "📎 🔥", "🤝": "👍 ❤", "🤖": "⚡ 🎯", "🔔": "📢", "✏": "📝", "🕘": "🗓 📆", "📊": "📈 📰",
    "🗑": "❌", "📖": "📚", "❓": "❗", "🆘": "❗ ❓", "📜": "📝 📰", "⚙": "🔧", "🛠": "🔧 ⚙", "🏠": "⭐ 🏁",
    "⬅": "🔙", "✅": "✔", "⚡": "🔥", "🚫": "❌ ⛔", "➕": "✅", "➖": "❌", "👥": "👍", "👤": "👍",
    "🔎": "🔍", "📋": "📝", "🎨": "🎯", "🔑": "🔐", "🌐": "🔗", "🧪": "🎯", "💼": "💰", "🔌": "⚡",
    "🎟": "🎁", "📣": "📢", "📢": "🔔", "💲": "💰", "💵": "💰", "🏪": "💰", "🔥": "⚡", "💾": "📌",
}.items()}


def lead(t):
    m = _LEAD.match(t)
    return m.group(1).strip() if m else ""


def strip_lead(t): return _LEAD.sub("", t, 1) if _LEAD.match(t) else t
def norm(e): return e.replace("\ufe0f", "").strip()


INLINE = {"inline:connect": "📲 Botni ulash", "inline:bot": "🤖 Bot sahifasi"}


def inline_default(key):
    """Inline tugmalarning standart nomi (ichki kalit → ko'rinadigan matn)."""
    if key in INLINE: return INLINE[key]
    if key.startswith("inline:ch:"):
        r = q("SELECT title FROM channels WHERE id=?", (key[10:],), True)
        return f"📢 {r['title'][:28]}" if r else None


def disp(label):
    """Tugmaning hozirgi ko'rinadigan nomi (admin o'zgartirgan yoki standart)."""
    r = q("SELECT new FROM btn_name WHERE orig=?", (label,), True)
    return r["new"] if r else (inline_default(label) or label)


def design():
    return ({r["orig"]: r["style"] for r in q("SELECT * FROM btn_style")},
            {r["orig"]: r["new"] for r in q("SELECT * FROM btn_name")},
            {r["orig"]: r["eid"] for r in q("SELECT * FROM btn_icon")})


def _ambig():
    c = Counter(strip_lead(l) for l in ROUTES)
    return {k for k, v in c.items() if v > 1}


def icon_for(label, text, icons, b):
    if g("icons_on") != "1" or b.noicons: return None
    if label in icons: return icons[label]
    e = norm(lead(text))
    if not e: return None
    for cand in [e] + [norm(x) for x in EMOJI_ALT.get(e, [])]:
        if cand in b.emap: return b.emap[cand]


def _btn(label, st, des=None):
    b = cur()
    styles, names, icons = des or design()
    text = names.get(label)
    if text is None: text = lab(inline_default(label) or label, cur_lang())
    btn = {"text": text, "style": styles.get(label) or st or "primary"}
    eid = icon_for(label, text, icons, b)
    if eid and (label in icons or strip_lead(text) not in _ambig()):
        rest = strip_lead(text) if lead(text) else text
        btn["icon_custom_emoji_id"], btn["text"] = eid, (rest or text)
    return btn


def kb(rows):
    des = design()
    return {"keyboard": [[_btn(*((x, "") if isinstance(x, str) else x), des) for x in r] for r in rows],
            "resize_keyboard": True}


def ikb(rows):
    """Inline (havolali) tugmalar. Admin o'zgartirgan URL bazadan olinadi, aks holda standart URL."""
    des = design()
    urls = {r["k"]: r["url"] for r in q("SELECT * FROM inline_urls")}
    out = []
    for r in rows:
        line = []
        for n, default_url, st in r:
            line.append({**_btn(n, st, des), "url": urls.get(n, default_url)})
        out.append(line)
    return {"inline_keyboard": out}


def resolve(t):
    """Tugma matnini (nomi o'zgargan, tarjima qilingan yoki premium emoji tufayli emojisiz kelgan bo'lsa ham) asl nomga qaytaradi."""
    if t in ROUTES: return t
    names = {r["new"]: r["orig"] for r in q("SELECT * FROM btn_name")}
    if t in names: return names[t]
    ren = {r["orig"]: r["new"] for r in q("SELECT * FROM btn_name")}
    for orig in ROUTES:
        if strip_lead(ren.get(orig, orig)) == t: return orig
    return rev_labels().get(t, t)


def match_label(t, labels):
    """Dinamik tugmalar (tarix, hududlar, inline) uchun: bosilgan matnga mos asl nomni topadi."""
    ren = {r["orig"]: r["new"] for r in q("SELECT * FROM btn_name")}
    for l in labels:
        base = ren.get(l) or inline_default(l) or l
        for sh in {base, lab(base, cur_lang())}:
            if t in (l, sh, strip_lead(l), strip_lead(sh)): return l


def main_rows(uid):
    rows = [[("📲 Botni ulash", "primary"), ("💎 Obuna olish", "success")],
            [("💳 Balans to'ldirish", "success"), ("👤 Profilim", "primary")],
            ["📅 Obunam", "🧾 To'lovlarim"],
            [("🎁 Promokod", "primary"), ("🔗 Referal", "primary")]]
    if is_main(): rows.append([("🤝 Hamkorlik", "success"), ("🤖 Mening botim", "primary")])
    rows += [[("🕘 Tarixim", "success"), "📊 Statistikam"],
             [("🗑 Keshni tozalash", "danger"), "📖 Qo'llanma"],
             ["❓ Savol-javob", "🆘 Yordam"], ["📜 Shartlar"]]
    if is_admin(uid): rows.append([("⚙️ Admin panel", "danger")])
    return rows


def load_emoji(s):
    """Telegram'ning premium (custom) emoji ro'yxatini yuklaydi: emoji → custom_emoji_id (tugma ikonkalari uchun)."""
    r = s.call("getForumTopicIconStickers") or []
    s.emap = {norm(x["emoji"]): x["custom_emoji_id"] for x in r if x.get("emoji") and x.get("custom_emoji_id")}
    return len(s.emap)
