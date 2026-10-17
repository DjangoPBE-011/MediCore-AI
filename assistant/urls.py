from django.urls import path
from . import views as v
urlpatterns = [
    path('triage/', v.TriageView.as_view()),
    path('explain-lab/', v.ExplainLabView.as_view()),
    path('draft-note/', v.DraftNoteView.as_view()),
    path('drug-check/', v.DrugCheckView.as_view()),
]
