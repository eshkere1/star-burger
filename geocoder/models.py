from django.db import models


class Geocache(models.Model):
    """Координаты адреса, уже полученные от геокодера.

    Яндекс отвечает на один и тот же адрес одинаково, а запросы к нему
    лимитированы и небыстры. Поэтому адрес спрашивается у геокодера один
    раз, а дальше берётся отсюда.
    """

    address = models.CharField(
        'адрес',
        max_length=100,
        unique=True,
    )
    lat = models.FloatField(
        'широта',
    )
    lon = models.FloatField(
        'долгота',
    )
    updated_at = models.DateTimeField(
        'дата обновления',
        auto_now=True,
    )

    class Meta:
        verbose_name = 'адрес в геокэше'
        verbose_name_plural = 'геокэш адресов'
        ordering = ['address']

    def __str__(self):
        return self.address
