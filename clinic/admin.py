from django.contrib import admin
from . import models as m
for mod in (m.Polyclinic, m.Specialization, m.Doctor, m.Patient, m.Schedule, m.Appointment, m.ICD10):
    admin.site.register(mod)
