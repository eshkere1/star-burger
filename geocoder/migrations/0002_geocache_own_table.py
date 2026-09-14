from django.db import migrations, models


def drop_incomplete_geocache(apps, schema_editor):
    """Строки без координат остались от старой схемы, где они были nullable.

    Кэш пустых ответов геокодера бесполезен: адрес всё равно придётся
    спрашивать заново. Поэтому такие строки просто удаляются, а колонки
    становятся NOT NULL — запись в кэше теперь означает «координаты известны».
    """
    Geocache = apps.get_model('geocoder', 'Geocache')
    Geocache.objects.filter(lat__isnull=True).delete()
    Geocache.objects.filter(lon__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('geocoder', '0001_initial'),
        ('foodcartapp', '0047_delete_geocache'),
    ]

    operations = [
        migrations.RunPython(drop_incomplete_geocache, migrations.RunPython.noop),
        migrations.AlterModelTable(
            name='geocache',
            table=None,
        ),
        migrations.AlterModelOptions(
            name='geocache',
            options={
                'ordering': ['address'],
                'verbose_name': 'адрес в геокэше',
                'verbose_name_plural': 'геокэш адресов',
            },
        ),
        migrations.AlterField(
            model_name='geocache',
            name='address',
            field=models.CharField(max_length=100, unique=True, verbose_name='адрес'),
        ),
        migrations.AlterField(
            model_name='geocache',
            name='lat',
            field=models.FloatField(verbose_name='широта'),
        ),
        migrations.AlterField(
            model_name='geocache',
            name='lon',
            field=models.FloatField(verbose_name='долгота'),
        ),
    ]
