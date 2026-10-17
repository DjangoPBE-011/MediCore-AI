# MediCore backend (Django REST Framework)

Oilaviy poliklinikalar uchun elektron tibbiy ma'lumotnoma tizimi.

## Ishga tushirish
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # PostgreSQL ma'lumotlarini yozing (bo'sh bo'lsa SQLite)
python manage.py migrate
python manage.py seed          # namuna ma'lumotlar: admin / doctor / patient, parol Medicore123
python manage.py runserver
```
Swagger: http://localhost:8000/api/docs/

Docker: `docker compose up --build`

## Rollar (faqat 3 ta)
| Rol | Imkoniyat |
|---|---|
| admin | foydalanuvchi, poliklinika, shifokor, katalog boshqaruvi; hujjatlarni FAQAT o'qiydi; audit jurnali |
| doctor | qabul, navbat, ko'rik, retsept, ma'lumotnoma yaratish/ERI bilan tasdiqlash |
| patient | o'z kartasi, qabul, navbat, tasdiqlangan hujjatlar, kundalik, oila |

## Asosiy qoidalar (testlar bilan tekshirilgan)
- Admin ma'lumotnomani tahrirlay olmaydi va shifokor nomidan tasdiqlay olmaydi.
- Tasdiqlash uchun E-IMZO seriya raqami majburiy (oddiy tugma ERI emas).
- Tasdiqlangan hujjat o'zgarmaydi; o'chirilmaydi, faqat bekor qilinadi.
- Audit jurnalida parol va token saqlanmaydi; jurnal faqat o'qiladi.
- Shifokor o'chirilmaydi, faqat faolsizlantiriladi (kirish ham bloklanadi).
- Ikki marta yozilish baza darajasida taqiqlangan (UniqueConstraint).
- QR tekshiruv ochiq, lekin faqat minimal ma'lumot (tashxis, tahlil yo'q).
- MediCore AI tashxis qo'ymaydi: yo'naltiradi, tushuntiradi, ICD-10 taklif beradi.

## Testlar
`python manage.py test`

## Muddati o'tgan hujjatlar
`python manage.py expire_certificates` (cron bilan kuniga 1 marta)

## FCM
`FCM_SERVER_KEY` ni .env ga yozing. Kalit bo'lmasa bildirishnoma faqat bazaga yoziladi.
