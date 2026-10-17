from datetime import date, time, timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from catalog.models import HealthDevice, Medicine, Place, Sanatorium
from clinic import models as m

U = get_user_model()
ICD = [('J06.9', 'O\'tkir yuqori nafas yo\'llari infeksiyasi', 'J00–J99 Nafas a\'zolari'),
       ('J02.9', 'O\'tkir faringit', 'J00–J99 Nafas a\'zolari'), ('J20.9', 'O\'tkir bronxit', 'J00–J99 Nafas a\'zolari'),
       ('J45.9', 'Bronxial astma', 'J00–J99 Nafas a\'zolari'), ('I10', 'Muhim (birlamchi) gipertenziya', 'I00–I99 Qon aylanish'),
       ('I25.9', 'Yurakning surunkali ishemik kasalligi', 'I00–I99 Qon aylanish'), ('E11', '2-tip qandli diabet', 'E00–E90 Endokrin'),
       ('E66.9', 'Semizlik', 'E00–E90 Endokrin'), ('K29.7', 'Gastrit, aniqlanmagan', 'K00–K93 Hazm'),
       ('K21.9', 'Gastroezofageal reflyuks', 'K00–K93 Hazm'), ('M54.5', 'Belning pastki qismidagi og\'riq', 'M00–M99 Suyak-mushak'),
       ('M17.9', 'Tizza artrozi', 'M00–M99 Suyak-mushak'), ('N39.0', 'Siydik yo\'llari infeksiyasi', 'N00–N99 Siydik-tanosil'),
       ('D50.9', 'Temir tanqisligi anemiyasi', 'D50–D89 Qon'), ('G43.9', 'Migren', 'G00–G99 Nerv tizimi'),
       ('L20.9', 'Atopik dermatit', 'L00–L99 Teri'), ('H10.9', 'Konyunktivit', 'H00–H59 Ko\'z'),
       ('Z00.0', 'Umumiy tibbiy ko\'rik', 'Z00–Z99 Sog\'liq holati'), ('Z02.7', 'Tibbiy ma\'lumotnoma berish', 'Z00–Z99 Sog\'liq holati')]


class Command(BaseCommand):
    help = 'Namuna ma\'lumotlar (ismlar, narxlar, telefonlar to\'qilgan)'

    def handle(self, *a, **kw):
        pc, _ = m.Polyclinic.objects.get_or_create(name='12-oilaviy poliklinika', defaults={'address': 'Chilonzor t., 12-kvartal', 'phone': '+998 71 200 12 12'})
        specs = {n: m.Specialization.objects.get_or_create(name=n, defaults={'slot_minutes': sm})[0]
                 for n, sm in [('Oilaviy shifokor', 20), ('Terapevt', 20), ('Pediatr', 25), ('Kardiolog', 30), ('Nevrolog', 30)]}
        for c, n, sec in ICD:
            m.ICD10.objects.get_or_create(code=c, defaults={'name': n, 'section': sec})

        def user(name, role, first, last, phone='', pw='Medicore123'):
            u, new = U.objects.get_or_create(username=name, defaults={'role': role, 'first_name': first, 'last_name': last, 'phone': phone})
            if new: u.set_password(pw); u.save()
            return u
        admin = user('admin', 'admin', 'Administrator', 'MediCore'); admin.is_superuser = True; admin.save()
        docs = []
        for un, f, l, sp, room in [('doctor', 'Aziza', 'Rahimova', 'Oilaviy shifokor', '108'), ('doctor2', 'Bobur', 'Saidov', 'Terapevt', '112'),
                                    ('doctor3', 'Malika', 'Normatova', 'Pediatr', '115')]:
            u = user(un, 'doctor', f, l, '+998901112233')
            d, _ = m.Doctor.objects.get_or_create(user=u, defaults={'polyclinic': pc, 'specialization': specs[sp], 'room': room, 'experience_years': 9})
            for wd in range(5):
                m.Schedule.objects.get_or_create(doctor=d, weekday=wd, defaults={'start': time(8), 'end': time(14), 'slot_minutes': specs[sp].slot_minutes})
            docs.append(d)
        pu = user('patient', 'patient', 'Dilnoza', 'Karimova', '+998901234567')
        p, _ = m.Patient.objects.get_or_create(user=pu, defaults={'polyclinic': pc, 'family_doctor': docs[0], 'birth_date': date(1998, 3, 12),
                                                                    'gender': 'f', 'blood_group': 'A+', 'allergies': 'Penitsillin', 'chronic': 'Gipertoniya'})
        today = timezone.localdate()
        m.Vaccination.objects.get_or_create(patient=p, name='Gripp', defaults={'due_date': today + timedelta(days=30)})
        for k, v1, v2 in [('bp', 118, 76), ('bp', 122, 80), ('bp', 136, 88)]:
            m.HealthMetric.objects.create(patient=p, kind=k, value=v1, value2=v2, measured_at=timezone.now() - timedelta(days=(v1 % 5)))
        for i, v in enumerate([112, 115, 119, 122, 126, 128]):
            m.LabResult.objects.get_or_create(patient=p, test='Umumiy qon tahlili', indicator='Gemoglobin', taken_at=today - timedelta(days=30 * (5 - i)),
                                              defaults={'value': v, 'unit': 'g/l', 'ref_low': 120, 'ref_high': 150})
        for n, sh, pr, op, cat in [('Vitamin C 1000', 'Immunitet uchun · 30 ta', 38000, 47500, 'vitamin'), ('Omega-3 baliq yog\'i', 'Yurak va qon tomir · 60 ta', 86000, 122000, 'vitamin'),
                                    ('Magniy B6', 'Asab tizimi uchun', 42000, 49000, 'vitamin'), ('Tomoq spreyi', 'Shamollash', 29000, 32000, 'cold')]:
            Medicine.objects.get_or_create(name=n, defaults={'short_info': sh, 'price': pr, 'old_price': op, 'category': cat})
        for n, k, a_, ph, lat, lng in [('Shifo Apteka', 'pharmacy', 'Mirzo Ulug\'bek t., 3-uy', '+998 71 233 11 22', 41.3111, 69.2797),
                                         ('Hayot Med klinikasi', 'clinic', 'Chilonzor t., 12-kvartal', '+998 71 244 55 66', 41.2756, 69.2036),
                                         ('Salomat Plus', 'pharmacy', 'Chilonzor t., 12-kvartal', '+998 90 100 20 30', 41.2790, 69.2060)]:
            Place.objects.get_or_create(name=n, defaults={'kind': k, 'address': a_, 'phone': ph, 'lat': lat, 'lng': lng})
        for n, c, pr, op in [('Massaj kreslo 3D', 'massaj', 7900000, 9500000), ('Umurtqa to\'g\'rilovchi remen', 'umurtqa', 185000, 240000), ('Nebulayzer', 'nafas', 320000, 360000)]:
            HealthDevice.objects.get_or_create(name=n, defaults={'category': c, 'price': pr, 'old_price': op})
        for n, loc, prof, pr in [('Zomin Sihatgohi', 'Zomin, Jizzax viloyati', 'Nafas yo\'llari, asab tizimi', 780000), ('Chorvoq Salomat', 'Bo\'stonliq, Toshkent v.', 'Yurak-qon tomir, umurtqa', 650000)]:
            Sanatorium.objects.get_or_create(name=n, defaults={'location': loc, 'profile': prof, 'price_per_night': pr})
        self.stdout.write(self.style.SUCCESS('Tayyor. Kirish: admin / doctor / patient, parol: Medicore123'))
