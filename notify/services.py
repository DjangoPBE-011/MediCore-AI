import json
import logging
import urllib.request
from django.conf import settings
from .models import DeviceToken, Notification

log = logging.getLogger(__name__)


def notify(user, title, body='', kind=''):
    """Bildirishnomani bazaga yozadi va (kalit sozlangan bo'lsa) FCM orqali push yuboradi."""
    n = Notification.objects.create(user=user, title=title, body=body, kind=kind)
    key = settings.FCM_SERVER_KEY
    if key:
        tokens = list(DeviceToken.objects.filter(user=user).values_list('token', flat=True))
        for t in tokens:
            try:
                req = urllib.request.Request(
                    'https://fcm.googleapis.com/fcm/send',
                    data=json.dumps({'to': t, 'notification': {'title': title, 'body': body}}).encode(),
                    headers={'Content-Type': 'application/json', 'Authorization': f'key={key}'})
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:  # push xatosi asosiy jarayonni to'xtatmasin
                log.warning('FCM xato: %s', e)
    return n
