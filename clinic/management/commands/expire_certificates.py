from django.core.management.base import BaseCommand
from django.utils import timezone
from certs.models import Certificate


class Command(BaseCommand):
    help = 'Muddati o\'tgan tasdiqlangan ma\'lumotnomalarni "Muddati tugagan" holatiga o\'tkazadi'
    def handle(self, *a, **kw):
        n = Certificate.objects.filter(status='approved', valid_until__lt=timezone.localdate()).update(status='expired')
        self.stdout.write(f'{n} ta hujjat yangilandi')
