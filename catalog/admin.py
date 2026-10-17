from django.contrib import admin
from . import models as m
for mod in (m.Medicine, m.Place, m.HealthDevice, m.Sanatorium):
    admin.site.register(mod)
