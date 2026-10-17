from datetime import datetime, timedelta
from django.utils import timezone
from .models import Appointment, QueueTicket, Schedule


def free_slots(doctor, date):
    """Shifokorning berilgan kundagi bo'sh vaqtlari (band bo'lganlari chiqarilgan)."""
    sch = Schedule.objects.filter(doctor=doctor, weekday=date.weekday()).first()
    if not sch:
        return []
    busy = set(Appointment.objects.filter(doctor=doctor, date=date, status__in=Appointment.ACTIVE)
               .values_list('time', flat=True))
    out, cur = [], datetime.combine(date, sch.start)
    end = datetime.combine(date, sch.end)
    now = timezone.localtime()
    while cur + timedelta(minutes=sch.slot_minutes) <= end:
        t = cur.time()
        past = date == now.date() and t <= now.time()
        if t not in busy and not past:
            out.append(t)
        cur += timedelta(minutes=sch.slot_minutes)
    return out


def queue_info(ticket):
    ahead = QueueTicket.objects.filter(doctor=ticket.doctor, date=ticket.date,
                                       status='waiting', number__lt=ticket.number).count()
    if ticket.status == 'called':
        ahead = 0
    slot = ticket.doctor.specialization.slot_minutes
    current = QueueTicket.objects.filter(doctor=ticket.doctor, date=ticket.date, status='called').first()
    return {'ahead': ahead, 'eta_minutes': ahead * slot, 'current_number': current.number if current else None}
