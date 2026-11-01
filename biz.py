"""biz.py — Telegram Business: ulangan akkauntdagi xabarlarni saqlash, o'chirilgan/tahrirlanganlarni yetkazish, o'chib ketuvchi mediani saqlash."""
import time
from core import *

MEDIA = {"photo": ("sendPhoto", "photo"), "video": ("sendVideo", "video"), "voice": ("sendVoice", "voice"),
         "video_note": ("sendVideoNote", "video_note"), "document": ("sendDocument", "document"),
         "audio": ("sendAudio", "audio"), "animation": ("sendAnimation", "animation"),
         "sticker": ("sendSticker", "sticker")}
FILE_NAMES = {"photo": "photo.jpg", "video": "video.mp4", "voice": "voice.ogg", "video_note": "note.mp4",
              "audio": "audio.mp3", "animation": "anim.mp4", "document": "file.bin", "sticker": "sticker.webp"}


def media(m):
    for k in MEDIA:
        if k in m:
            v = m[k]
            return k, (v[-1] if isinstance(v, list) else v)["file_id"]
    return None, None


class BizMixin:
    def conn(s, c):
        uid = c["user"]["id"]
        if c.get("is_enabled"):
            reg(uid)
            q("INSERT OR REPLACE INTO conns VALUES(?,?)", (c["id"], uid))
            s.send(c["user_chat_id"], "✅ Akkaunt ulandi. O'chirilgan va tahrirlangan xabarlar shu yerga keladi.\n\n"
                                      "🔥 O'chib ketuvchi rasm/videoni saqlash uchun uni OCHISHDAN OLDIN unga istalgan javob (reply) yozing.")
        else:
            q("DELETE FROM conns WHERE id=?", (c["id"],))

    def bmsg(s, m):
        c = q("SELECT user_id FROM conns WHERE id=?", (m["business_connection_id"],), True)
        if not c: return
        owner, mine = c["user_id"], m["from"]["id"] == c["user_id"]
        if mine and m.get("reply_to_message"): s.rescue(owner, m["reply_to_message"])
        kind, fid = media(m) if g("save_media") == "1" else (None, None)
        ch, fr = m["chat"], m["from"]
        chat_name = (ch.get("first_name", "") + " " + ch.get("last_name", "")).strip() or ch.get("title") or ch.get("username") or str(ch["id"])
        who = "Siz" if mine else (fr.get("first_name", "") + " " + fr.get("last_name", "")).strip()
        q("INSERT OR REPLACE INTO msgs(cid,chat,mid,owner,who,kind,text,fid,ts,mine,chat_name) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (m["business_connection_id"], ch["id"], m["message_id"], owner, who, kind, m.get("text") or m.get("caption"),
           fid, int(time.time()), int(mine), chat_name))

    def rescue(s, owner, r):
        """Egasi o'chib ketuvchi (bir martalik) mediaga javob yozsa — medianing nusxasini oddiy fayl qilib yuboradi."""
        kind, fid = media(r)
        if not (kind and fid and g("save_media") == "1" and active(owner)): return
        who = (r.get("from") or {}).get("first_name") or "suhbatdosh"
        cap = f"🔥 Saqlandi: <b>{esc(who)}</b> yuborgan media" + (f"\n{esc(r.get('caption'))}" if r.get("caption") else "")
        meth, key = MEDIA[kind]
        if s.call(meth, chat_id=owner, **{key: fid}, caption=cap, parse_mode="HTML") is None:
            data = s.fetch_file(fid)
            if data and s.upload(meth, key, FILE_NAMES.get(kind, "file"), data, chat_id=owner, caption=cap, parse_mode="HTML"): return
            s.send(owner, "⚠️ Mediani saqlab bo'lmadi: Telegram faylni bermadi. Keyingi safar mediani OCHISHDAN OLDIN javob yozing.")

    def find(s, cid, chat, mid):
        return q("SELECT * FROM msgs WHERE cid=? AND chat=? AND mid=?", (cid, chat, mid), True)

    def bedit(s, m):
        r = s.find(m["business_connection_id"], m["chat"]["id"], m["message_id"])
        if not r: return
        new, u = m.get("text") or m.get("caption"), U(r["owner"])
        if not r["mine"] and u and u["n_edit"] and g("notify_edited") == "1" and active(r["owner"]):
            s.send(r["owner"], f"✏️ <b>{esc(r['who'])}</b> xabarni tahrirladi\n\n<b>Eski:</b> {esc(r['text'])}\n<b>Yangi:</b> {esc(new)}")
        q("UPDATE msgs SET old_text=COALESCE(old_text, text), text=? WHERE cid=? AND chat=? AND mid=?", (new, r["cid"], r["chat"], r["mid"]))

    def bdel(s, d):
        for mid in d["message_ids"]:
            r = s.find(d["business_connection_id"], d["chat"]["id"], mid)
            if not r: continue
            q("UPDATE msgs SET deleted=1 WHERE cid=? AND chat=? AND mid=?", (r["cid"], r["chat"], r["mid"]))
            u = U(r["owner"])
            if r["mine"] or not (u and u["n_del"] and g("notify_deleted") == "1" and active(r["owner"])): continue
            s.send(r["owner"], f"🗑 <b>{esc(r['who'])}</b> xabarni o'chirdi:\n{esc(r['text'])}")
            if r["kind"] and r["fid"]:
                meth, key = MEDIA[r["kind"]]
                s.call(meth, chat_id=r["owner"], **{key: r["fid"]})
