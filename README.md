# Xabar boti (Telegram Business)

O'chirilgan/tahrirlangan xabarlar va o'chib ketuvchi rasm-videolarni saqlab egasiga yetkazadi. Obuna, balans, avto-to'lov (Tezcheck), Click, majburiy kanallar, dizayn (rang/nom/premium emoji), tarix PDF va hamkorlik (har bir hamkor o'z botini to'liq o'zi boshqaradi).

## Fayllar (hammasi bitta papkada, asosiy papkada bo'lsin)
- `bot.py` — ishga tushirish: `python bot.py`
- `core.py` — sozlamalar, bazalar (har bir bot alohida baza), umumiy funksiyalar
- `ui.py` — tugma rangi, nomi, premium emoji, klaviatura
- `pay.py` — Tezcheck (`TC_PATHS` shu yerda), Click, avto-to'lov ustasi, fon vazifalari
- `ops.py` — admin funksiyalari va amallari
- `user.py` — foydalanuvchi tugmalari
- `buttons.py` — admin panel bo'limlari va tugmalari
- `design.py` — dizayn: tugma ranglari, nomlarini tahrirlash, premium emoji
- `history.py` — «🕘 Tarixim» (PDF)
- `pdfgen.py` — kutubxonasiz PDF yozuvchi
- `biz.py` — Business: xabarlarni saqlash, o'chirilgan/tahrirlangan, o'chib ketuvchi media
- `requirements.txt`, `Dockerfile`, `bot.service`, `bot.yml` (`.github/workflows/bot.yml`), `.gitignore`, `.env.example`

## Sozlash
1. `.env.example` ni `.env` ga nusxalang: `BOT_TOKEN`, `ADMIN_ID` ni yozing.
2. @BotFather → bot → Bot Settings → **Business Mode** → Turn on.
3. `pip install -r requirements.txt` va `python bot.py`.
4. Admin panel → 💳 To'lov tizimi → **⚡ Avto to'lov ulash**: Hisob API, keyin Kassa API ni kiriting — avto-to'lov o'zi yoqiladi.
5. **💳 Click ulash**: @BotFather → /mybots → bot → Payments → Click, so'ng berilgan provider tokenni yuboring.

## Hamkorlik (klon botlar)
Hamkor «🤖 Mening botim» orqali o'z token'ini beradi. Klon bot — alohida baza (`clone_<id>.db`), alohida narxlar, to'lov tizimlari, kanallar, dizayn va to'liq **⚙️ Admin panel** faqat shu hamkorga ko'rinadi (asosiy admin klonda admin emas).

## Eslatmalar
- Premium emoji tugmalarda ishlashi uchun bot egasida Telegram Premium bo'lishi kerak; bo'lmasa oddiy emoji ko'rinadi.
- O'chib ketuvchi media: uni OCHISHDAN OLDIN unga istalgan javob (reply) yozing.
- Bir vaqtda faqat bitta nusxa ishlasin (aks holda Telegram `409 Conflict` beradi).

## GitHub va server
`git init && git add . && git commit -m "Xabar boti" && git branch -M main && git remote add origin <URL> && git push -u origin main` (repo **Private**). `.env` va `*.db` yuklanmaydi.
- **VPS:** `bot.service` (systemd), `git pull` + `systemctl restart bot`.
- **Railway/Render:** Dockerfile; Variables: `BOT_TOKEN`, `ADMIN_ID`, `DB_FILE=/data/bot.db`; Volume `/data` ga ulang.