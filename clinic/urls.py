from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views as v
r = DefaultRouter()
r.register('polyclinics', v.PolyclinicViewSet, 'polyclinics')
r.register('specializations', v.SpecializationViewSet, 'specializations')
r.register('doctors', v.DoctorViewSet, 'doctors')
r.register('patients', v.PatientViewSet, 'patients')
r.register('appointments', v.AppointmentViewSet, 'appointments')
r.register('queue', v.QueueViewSet, 'queue')
r.register('icd10', v.ICDViewSet, 'icd10')
r.register('records', v.RecordViewSet, 'records')
r.register('prescriptions', v.PrescriptionViewSet, 'prescriptions')
r.register('lab-results', v.LabResultViewSet, 'lab-results')
r.register('lab-orders', v.LabOrderViewSet, 'lab-orders')
r.register('metrics', v.MetricViewSet, 'metrics')
r.register('reminders', v.ReminderViewSet, 'reminders')
r.register('vaccinations', v.VaccinationViewSet, 'vaccinations')
r.register('family', v.FamilyViewSet, 'family')
r.register('reviews', v.ReviewViewSet, 'reviews')
urlpatterns = r.urls + [path('stats/', v.StatsView.as_view())]
