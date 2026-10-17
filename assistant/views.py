"""MediCore AI. Qoidalarga asoslangan yordamchi. TASHXIS QO'YMAYDI: faqat yo'naltiradi va tushuntiradi."""
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsDoctor
from clinic.models import ICD10, Patient

DISCLAIMER = 'Bu tashxis emas. Aniq xulosa uchun shifokorga murojaat qiling.'
EMERGENCY = ['ko\'krak og\'rig', 'nafas ololmay', 'hushdan ket', 'qon ket', 'insult', 'falaj', 'zaharlan']
ROUTES = [
    (('yo\'tal', 'tomoq', 'harorat', 'shamoll', 'burun'), 'Terapevt', 'Oilaviy shifokor'),
    (('bosim', 'yurak', 'puls', 'hansira'), 'Kardiolog', 'Oilaviy shifokor'),
    (('bola', 'farzand', 'chaqaloq'), 'Pediatr', 'Oilaviy shifokor'),
    (('qand', 'chanqoq', 'vazn'), 'Endokrinolog', 'Terapevt'),
    (('qorin', 'oshqozon', 'ko\'ngil'), 'Gastroenterolog', 'Terapevt'),
    (('bel', 'bo\'g\'im', 'umurtqa', 'tizza'), 'Nevrolog', 'Travmatolog'),
]
INTERACTIONS = {
    frozenset(['ibuprofen', 'aspirin']): 'NSAID dorilarini birga qabul qilish oshqozon-ichak qon ketish xavfini oshiradi',
    frozenset(['ibuprofen', 'atorvastatin']): 'Ehtiyot bo\'ling: buyrak va jigar ko\'rsatkichlarini kuzating',
    frozenset(['warfarin', 'aspirin']): 'Qon ketish xavfi yuqori',
}
ALLERGY_GROUPS = {'penitsillin': ['amoksitsillin', 'ampitsillin', 'penitsillin'], 'aspirin': ['aspirin', 'ibuprofen']}


class TriageView(APIView):
    def post(self, request):
        text = (request.data.get('text') or '').lower()
        if any(k in text for k in EMERGENCY):
            return Response({'emergency': True, 'advice': 'Zudlik bilan 103 ga qo\'ng\'iroq qiling', 'disclaimer': DISCLAIMER})
        for keys, spec, alt in ROUTES:
            if any(k in text for k in keys):
                return Response({'emergency': False, 'specialization': spec, 'alternative': alt,
                                 'advice': f'{spec} qabuliga yozilish tavsiya etiladi', 'disclaimer': DISCLAIMER})
        return Response({'emergency': False, 'specialization': 'Oilaviy shifokor', 'alternative': 'Terapevt',
                         'advice': 'Avval oilaviy shifokor ko\'rigidan o\'ting', 'disclaimer': DISCLAIMER})


class ExplainLabView(APIView):
    def post(self, request):
        try:
            v = float(request.data['value'])
            lo = float(request.data['ref_low']) if request.data.get('ref_low') not in (None, '') else None
            hi = float(request.data['ref_high']) if request.data.get('ref_high') not in (None, '') else None
        except (KeyError, ValueError):
            return Response({'detail': 'value majburiy'}, status=400)
        name = request.data.get('indicator', 'Ko\'rsatkich')
        if lo is not None and v < lo: txt = f'{name} me\'yordan past ({v}; me\'yor {lo}–{hi}).'
        elif hi is not None and v > hi: txt = f'{name} me\'yordan yuqori ({v}; me\'yor {lo}–{hi}).'
        else: txt = f'{name} me\'yor oralig\'ida ({v}).'
        return Response({'explanation': txt + ' Natijani shifokor bilan muhokama qiling.', 'disclaimer': DISCLAIMER})


class DraftNoteView(APIView):
    """Shifokor uchun: matndan yozuv qoralamasi va ICD-10 TAKLIFLARI. Yakuniy tashxisni shifokor tanlaydi."""
    permission_classes = [IsDoctor]
    def post(self, request):
        text = (request.data.get('text') or '').strip()
        words = [w for w in text.lower().replace(',', ' ').split() if len(w) > 3]
        hits = []
        for icd in ICD10.objects.filter(is_active=True):
            if any(w[:5] in icd.name.lower() for w in words):
                hits.append({'id': icd.id, 'code': icd.code, 'name': icd.name})
        return Response({'draft': {'complaint': text, 'objective': '', 'recommendations': ''},
                         'icd10_suggestions': hits[:5],
                         'disclaimer': 'AI tashxis qo\'ymaydi. Variantlar faqat yordam; qaror shifokorniki.'})


class DrugCheckView(APIView):
    permission_classes = [IsDoctor]
    def post(self, request):
        meds = [m.strip().lower() for m in request.data.get('medicines', [])]
        warnings = []
        pat = Patient.objects.filter(pk=request.data.get('patient')).first()
        if pat and pat.allergies:
            al = pat.allergies.lower()
            for grp, members in ALLERGY_GROUPS.items():
                if grp in al:
                    for m in meds:
                        if any(x in m for x in members):
                            warnings.append({'level': 'danger', 'medicine': m, 'text': f'Allergiya: {pat.allergies}'})
        for pair, text in INTERACTIONS.items():
            if all(any(p in m for m in meds) for p in pair):
                warnings.append({'level': 'caution', 'medicine': ' + '.join(sorted(pair)), 'text': text})
        return Response({'warnings': warnings, 'ok': not warnings,
                         'disclaimer': 'Ogohlantirishlar yordamchi; yakuniy qaror shifokorniki.'})
