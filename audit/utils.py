SENSITIVE = ('password', 'token', 'access', 'refresh', 'secret', 'pin', 'authorization', 'key')


def scrub(d):
    if isinstance(d, dict):
        return {k: ('***' if any(s in k.lower() for s in SENSITIVE) else scrub(v)) for k, v in d.items()}
    if isinstance(d, (list, tuple)):
        return [scrub(x) for x in d]
    return d


def log(request, action, obj=None, detail=None, user=None):
    from .models import AuditLog
    u = user or getattr(request, 'user', None)
    if u is not None and not getattr(u, 'is_authenticated', False):
        u = None
    ip = None
    if request is not None:
        ip = (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
              or request.META.get('REMOTE_ADDR') or None)
    return AuditLog.objects.create(
        user=u, role=getattr(u, 'role', '') if u else '', action=action,
        object_type=obj.__class__.__name__ if obj is not None else '',
        object_id=str(getattr(obj, 'pk', '') or '') if obj is not None else '',
        detail=scrub(detail or {}), ip=ip)
