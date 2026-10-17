from django.db import models


class Medicine(models.Model):
    name = models.CharField(max_length=120)
    short_info = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='medicines/', blank=True)
    price = models.PositiveIntegerField()
    old_price = models.PositiveIntegerField(null=True, blank=True)
    discount_until = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=40, blank=True)
    prescription_only = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return round((1 - self.price / self.old_price) * 100)
        return 0


class Place(models.Model):
    class T(models.TextChoices):
        PHARMACY = 'pharmacy', 'Dorixona'
        CLINIC = 'clinic', 'Xususiy klinika'
    kind = models.CharField(max_length=10, choices=T.choices)
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    work_hours = models.CharField(max_length=60, default='08:00–22:00')
    is_24h = models.BooleanField(default=False)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    services = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)


class HealthDevice(models.Model):
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=40, blank=True)  # massaj, umurtqa, nafas, boyin
    short_info = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='devices/', blank=True)
    price = models.PositiveIntegerField()
    old_price = models.PositiveIntegerField(null=True, blank=True)
    warranty_months = models.PositiveSmallIntegerField(default=12)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    is_active = models.BooleanField(default=True)


class Sanatorium(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=160)
    profile = models.CharField(max_length=200, blank=True)  # davolash profili
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='sanatoriums/', blank=True)
    price_per_night = models.PositiveIntegerField()
    phone = models.CharField(max_length=30, blank=True)
    check_in = models.CharField(max_length=10, default='14:00')
    check_out = models.CharField(max_length=10, default='12:00')
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.5)
    is_active = models.BooleanField(default=True)
