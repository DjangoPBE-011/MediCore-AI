from datetime import date, time, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from audit.models import AuditLog
from certs.models import Certificate
from . import models as m

U = get_user_model()


def next_weekday(wd=0):
    d = timezone.localdate() + timedelta(days=3)
    while d.weekday() != wd:
        d += timedelta(days=1)
    return d


class Base(APITestCase):
    def setUp(self):
        self.pc = m.Polyclinic.objects.create(name='12-poliklinika')
        self.sp = m.Specialization.objects.create(name='Oilaviy shifokor', slot_minutes=20)
        self.admin = U.objects.create_user('admin', password='Pass12345!', role='admin')
        self.du = U.objects.create_user('doc', password='Pass12345!', role='doctor', first_name='Aziza', last_name='Rahimova')
        self.doc = m.Doctor.objects.create(user=self.du, polyclinic=self.pc, specialization=self.sp, room='108')
        self.du2 = U.objects.create_user('doc2', password='Pass12345!', role='doctor')
        self.doc2 = m.Doctor.objects.create(user=self.du2, polyclinic=self.pc, specialization=self.sp)
        self.pu = U.objects.create_user('pat', password='Pass12345!', role='patient', first_name='Dilnoza', last_name='Karimova')
        self.pat = m.Patient.objects.create(user=self.pu, polyclinic=self.pc, allergies='Penitsillin')
        self.pu2 = U.objects.create_user('pat2', password='Pass12345!', role='patient')
        self.pat2 = m.Patient.objects.create(user=self.pu2, polyclinic=self.pc)
        for wd in range(7):
            m.Schedule.objects.create(doctor=self.doc, weekday=wd, start=time(8), end=time(12), slot_minutes=20)

    def as_(self, user):
        self.client.force_authenticate(user)
        return self.client


class AuthTests(Base):
    def test_login_and_me(self):
        r = self.client.post('/api/auth/login/', {'username': 'pat', 'password': 'Pass12345!'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)
        self.assertEqual(r.data['user']['role'], 'patient')

    def test_audit_never_stores_password_or_token(self):
        self.client.post('/api/auth/login/', {'username': 'pat', 'password': 'Pass12345!'})
        self.client.post('/api/auth/login/', {'username': 'pat', 'password': 'wrong'})
        dump = ' '.join(str(a.detail) for a in AuditLog.objects.all())
        self.assertNotIn('Pass12345', dump)
        self.assertNotIn('wrong', dump)

    def test_register_always_patient(self):
        r = self.client.post('/api/auth/register/', {'phone': '+998901110000', 'password': 'Strong#Pass99', 'first_name': 'A', 'last_name': 'B', 'role': 'admin'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['role'], 'patient')

    def test_only_admin_manages_users(self):
        self.assertEqual(self.as_(self.pu).get('/api/auth/users/').status_code, 403)
        self.assertEqual(self.as_(self.admin).get('/api/auth/users/').status_code, 200)

    def test_unauthenticated(self):
        self.assertEqual(self.client.get('/api/appointments/').status_code, 401)


class DoctorRulesTests(Base):
    def test_doctor_cannot_be_deleted(self):
        r = self.as_(self.admin).delete(f'/api/doctors/{self.doc.pk}/')
        self.assertEqual(r.status_code, 405)

    def test_deactivate_blocks_login_and_hides(self):
        self.as_(self.admin).patch(f'/api/doctors/{self.doc.pk}/', {'is_active': False})
        self.du.refresh_from_db()
        self.assertFalse(self.du.is_active)
        ids = [d['id'] for d in self.as_(self.pu).get('/api/doctors/').data['results']]
        self.assertNotIn(self.doc.pk, ids)

    def test_patient_cannot_create_doctor(self):
        self.assertEqual(self.as_(self.pu).post('/api/doctors/', {}).status_code, 403)


class AppointmentTests(Base):
    def book(self, user, t='09:00', d=None):
        d = d or next_weekday()
        return self.as_(user).post('/api/appointments/', {'doctor': self.doc.pk, 'date': str(d), 'time': t})

    def test_booking_and_double_booking_prevented(self):
        self.assertEqual(self.book(self.pu).status_code, 201)
        r = self.book(self.pu2)
        self.assertEqual(r.status_code, 400)

    def test_slot_outside_schedule(self):
        self.assertEqual(self.book(self.pu, '15:00').status_code, 400)

    def test_slots_exclude_booked(self):
        self.book(self.pu)
        r = self.as_(self.pu).get(f'/api/doctors/{self.doc.pk}/slots/?date={next_weekday()}')
        self.assertNotIn('09:00', r.data['slots'])
        self.assertIn('09:20', r.data['slots'])

    def test_cancel_frees_slot(self):
        a = self.book(self.pu).data['id']
        self.assertEqual(self.as_(self.pu).post(f'/api/appointments/{a}/cancel/').status_code, 200)
        self.assertEqual(self.book(self.pu2).status_code, 201)

    def test_status_flow_and_permissions(self):
        a = self.book(self.pu).data['id']
        self.assertEqual(self.as_(self.pu).post(f'/api/appointments/{a}/confirm/').status_code, 403)
        self.assertEqual(self.as_(self.du).post(f'/api/appointments/{a}/confirm/').data['status'], 'confirmed')
        self.assertEqual(self.as_(self.du).post(f'/api/appointments/{a}/start/').data['status'], 'in_progress')
        self.assertEqual(self.as_(self.du).post(f'/api/appointments/{a}/finish/').data['status'], 'done')
        self.assertEqual(self.as_(self.du).post(f'/api/appointments/{a}/start/').status_code, 400)

    def test_users_see_only_own(self):
        self.book(self.pu)
        self.assertEqual(len(self.as_(self.pu2).get('/api/appointments/').data['results']), 0)
        self.assertEqual(len(self.as_(self.du2).get('/api/appointments/').data['results']), 0)
        self.assertEqual(len(self.as_(self.du).get('/api/appointments/').data['results']), 1)

    def test_late_cancel_blocked_for_patient(self):
        now = timezone.localtime() + timedelta(minutes=30)
        a = m.Appointment.objects.create(patient=self.pat, doctor=self.doc, date=now.date(), time=now.time().replace(second=0, microsecond=0), status='confirmed')
        self.assertEqual(self.as_(self.pu).post(f'/api/appointments/{a.pk}/cancel/').status_code, 400)

    def test_review_only_after_done(self):
        self.assertEqual(self.as_(self.pu).post('/api/reviews/', {'doctor': self.doc.pk, 'rating': 5}).status_code, 400)
        m.Appointment.objects.create(patient=self.pat, doctor=self.doc, date=timezone.localdate(), time=time(8), status='done')
        self.assertEqual(self.as_(self.pu).post('/api/reviews/', {'doctor': self.doc.pk, 'rating': 5}).status_code, 201)


class QueueTests(Base):
    def test_take_ticket_and_position(self):
        a = self.as_(self.pu).post('/api/queue/take/', {'doctor': self.doc.pk}).data
        b = self.as_(self.pu2).post('/api/queue/take/', {'doctor': self.doc.pk}).data
        self.assertEqual((a['number'], b['number']), (1, 2))
        self.assertEqual(b['info']['ahead'], 1)
        self.assertEqual(self.as_(self.pu).post('/api/queue/take/', {'doctor': self.doc.pk}).status_code, 400)

    def test_call_next(self):
        self.as_(self.pu).post('/api/queue/take/', {'doctor': self.doc.pk})
        self.as_(self.pu2).post('/api/queue/take/', {'doctor': self.doc.pk})
        r = self.as_(self.du).post('/api/queue/call_next/')
        self.assertEqual(r.data['current']['number'], 1)
        r = self.as_(self.du).post('/api/queue/call_next/')
        self.assertEqual(r.data['current']['number'], 2)
        board = self.as_(self.du).get('/api/queue/board/').data
        self.assertEqual(board['stats']['done'], 1)
        self.assertEqual(self.as_(self.pu).post('/api/queue/call_next/').status_code, 403)


class CertTests(Base):
    def make(self, **kw):
        r = self.as_(self.du).post('/api/certificates/', {'patient': self.pat.pk, 'kind': 'pool', 'conclusion': 'Sog\'lom', 'valid_until': str(timezone.localdate() + timedelta(days=30)), **kw})
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def approved(self):
        cid = self.make()
        self.as_(self.du).post(f'/api/certificates/{cid}/submit/')
        r = self.as_(self.du).post(f'/api/certificates/{cid}/approve/', {'signature_serial': 'EIMZO-123'})
        self.assertEqual(r.data['status'], 'approved')
        return cid

    def test_full_flow(self):
        cid = self.approved()
        c = Certificate.objects.get(pk=cid)
        self.assertTrue(c.number.startswith('OP'))
        self.assertIsNotNone(c.signed_at)

    def test_approve_requires_eri_signature(self):
        cid = self.make()
        self.as_(self.du).post(f'/api/certificates/{cid}/submit/')
        self.assertEqual(self.as_(self.du).post(f'/api/certificates/{cid}/approve/').status_code, 400)

    def test_admin_cannot_edit_or_approve(self):
        cid = self.make()
        self.as_(self.du).post(f'/api/certificates/{cid}/submit/')
        a = self.as_(self.admin)
        self.assertEqual(a.post(f'/api/certificates/{cid}/approve/', {'signature_serial': 'X'}).status_code, 403)
        self.assertEqual(a.patch(f'/api/certificates/{cid}/', {'conclusion': 'x'}).status_code, 403)
        self.assertEqual(a.post('/api/certificates/', {'patient': self.pat.pk}).status_code, 403)
        self.assertEqual(a.get('/api/certificates/').status_code, 200)

    def test_other_doctor_cannot_approve(self):
        cid = self.make()
        self.as_(self.du).post(f'/api/certificates/{cid}/submit/')
        self.assertEqual(self.as_(self.du2).post(f'/api/certificates/{cid}/approve/', {'signature_serial': 'X'}).status_code, 404)

    def test_approved_is_immutable(self):
        cid = self.approved()
        self.assertEqual(self.as_(self.du).patch(f'/api/certificates/{cid}/', {'conclusion': 'x'}).status_code, 400)
        self.assertEqual(self.as_(self.du).delete(f'/api/certificates/{cid}/').status_code, 405)

    def test_patient_sees_only_approved_own(self):
        draft = self.make()
        ok = self.approved()
        ids = [c['id'] for c in self.as_(self.pu).get('/api/certificates/').data['results']]
        self.assertEqual(ids, [ok])
        self.assertEqual(len(self.as_(self.pu2).get('/api/certificates/').data['results']), 0)

    def test_reject_needs_reason_and_resubmit(self):
        cid = self.make()
        self.as_(self.du).post(f'/api/certificates/{cid}/submit/')
        self.assertEqual(self.as_(self.du).post(f'/api/certificates/{cid}/reject/').status_code, 400)
        self.assertEqual(self.as_(self.du).post(f'/api/certificates/{cid}/reject/', {'reason': 'To\'liq emas'}).data['status'], 'rejected')
        self.assertEqual(self.as_(self.du).patch(f'/api/certificates/{cid}/', {'conclusion': 'Yangi'}).status_code, 200)
        self.assertEqual(self.as_(self.du).post(f'/api/certificates/{cid}/submit/').data['status'], 'pending')

    def test_expired_status(self):
        cid = self.approved()
        Certificate.objects.filter(pk=cid).update(valid_until=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.as_(self.pu).get(f'/api/certificates/{cid}/').data['effective_status'], 'expired')

    def test_pdf_only_when_approved(self):
        cid = self.make()
        self.assertEqual(self.as_(self.du).get(f'/api/certificates/{cid}/pdf/').status_code, 400)
        cid = self.approved()
        r = self.as_(self.pu).get(f'/api/certificates/{cid}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_public_verify_minimal_data(self):
        dx = m.ICD10.objects.create(code='J06.9', name='OREVI')
        cid = self.make(diagnosis=dx.pk, conclusion='Maxfiy xulosa')
        self.as_(self.du).post(f'/api/certificates/{cid}/submit/')
        self.as_(self.du).post(f'/api/certificates/{cid}/approve/', {'signature_serial': 'S1'})
        token = Certificate.objects.get(pk=cid).qr_token
        self.client.force_authenticate(None)
        r = self.client.get(f'/api/verify/{token}/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['valid'])
        body = str(r.data)
        self.assertNotIn('Maxfiy', body); self.assertNotIn('J06', body); self.assertNotIn('Karimova', body)
        self.assertEqual(self.client.get('/api/verify/nonexistent/').status_code, 404)

    def test_cancelled_not_valid(self):
        cid = self.approved()
        self.as_(self.du).post(f'/api/certificates/{cid}/cancel/', {'reason': 'xato'})
        self.client.force_authenticate(None)
        self.assertFalse(self.client.get(f'/api/verify/{Certificate.objects.get(pk=cid).qr_token}/').data['valid'])

    def test_share_link_selective_and_expiry(self):
        cid = self.approved()
        r = self.as_(self.pu).post('/api/shares/', {'certificate': cid, 'show_conclusion': False, 'hours': 1})
        self.assertEqual(r.status_code, 201)
        tok = r.data['token']
        self.client.force_authenticate(None)
        d = self.client.get(f'/api/shared/{tok}/').data
        self.assertNotIn('conclusion', d); self.assertNotIn('diagnosis', d)
        from certs.models import ShareLink
        ShareLink.objects.filter(token=tok).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.get(f'/api/shared/{tok}/').status_code, 410)

    def test_cannot_share_foreign_certificate(self):
        cid = self.approved()
        self.assertIn(self.as_(self.pu2).post('/api/shares/', {'certificate': cid}).status_code, (403, 404))

    def test_audit_trail_written(self):
        cid = self.approved()
        acts = set(AuditLog.objects.values_list('action', flat=True))
        self.assertTrue({'certificate_create', 'certificate_submit', 'certificate_approve'} <= acts)

    def test_audit_read_only_admin_only(self):
        self.approved()
        self.assertEqual(self.as_(self.du).get('/api/audit/').status_code, 403)
        self.assertEqual(self.as_(self.admin).get('/api/audit/').status_code, 200)
        self.assertEqual(self.as_(self.admin).post('/api/audit/', {}).status_code, 405)


class DataScopeTests(Base):
    def test_patient_cannot_write_records(self):
        r = self.as_(self.pu).post('/api/records/', {'patient': self.pat.pk})
        self.assertEqual(r.status_code, 403)

    def test_patient_sees_own_records_only(self):
        m.MedicalRecord.objects.create(patient=self.pat, doctor=self.doc, complaint='x')
        m.MedicalRecord.objects.create(patient=self.pat2, doctor=self.doc, complaint='y')
        self.assertEqual(len(self.as_(self.pu).get('/api/records/').data['results']), 1)

    def test_patient_cannot_change_clinical_links(self):
        r = self.as_(self.pu).patch('/api/patients/me/', {'polyclinic': None, 'address': 'Toshkent'})
        self.assertEqual(r.data['address'], 'Toshkent')
        self.pat.refresh_from_db()
        self.assertEqual(self.pat.polyclinic_id, self.pc.pk)

    def test_catalog_write_admin_only(self):
        body = {'name': 'Dori', 'price': 1000}
        self.assertEqual(self.as_(self.pu).post('/api/medicines/', body).status_code, 403)
        self.assertEqual(self.as_(self.admin).post('/api/medicines/', body).status_code, 201)
        self.assertEqual(len(self.as_(self.pu).get('/api/medicines/').data['results']), 1)

    def test_icd_catalog(self):
        m.ICD10.objects.create(code='J06.9', name='O\'RVI')
        self.assertEqual(len(self.as_(self.du).get('/api/icd10/?q=J06').data['results']), 1)
        self.assertEqual(self.as_(self.du).post('/api/icd10/', {'code': 'X', 'name': 'x'}).status_code, 403)


class AssistantTests(Base):
    def test_triage_emergency(self):
        r = self.as_(self.pu).post('/api/assistant/triage/', {'text': 'Ko\'krak og\'rig\'i bor'})
        self.assertTrue(r.data['emergency'])

    def test_triage_never_diagnoses(self):
        r = self.as_(self.pu).post('/api/assistant/triage/', {'text': 'yo\'tal va harorat'})
        self.assertIn('disclaimer', r.data)
        self.assertNotIn('diagnosis', r.data)

    def test_drug_check_allergy(self):
        r = self.as_(self.du).post('/api/assistant/drug-check/', {'patient': self.pat.pk, 'medicines': ['Amoksitsillin 500', 'Paratsetamol']})
        self.assertEqual(r.data['warnings'][0]['level'], 'danger')
        self.assertEqual(self.as_(self.pu).post('/api/assistant/drug-check/', {}).status_code, 403)

    def test_metric_status(self):
        r = self.as_(self.pu).post('/api/metrics/', {'kind': 'bp', 'value': 140, 'value2': 90, 'measured_at': timezone.now().isoformat()})
        self.assertEqual(r.data['status'], 'high')

    def test_notifications_isolated(self):
        from notify.services import notify
        notify(self.pu, 'a'); notify(self.pu2, 'b')
        self.assertEqual(len(self.as_(self.pu).get('/api/notifications/').data['results']), 1)

    def test_swagger(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
