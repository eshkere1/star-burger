from django.db import migrations, models


class Migration(migrations.Migration):
    """Geocache переезжает из foodcartapp в geocoder.

    Таблица пока остаётся прежней — `foodcartapp_geocache`, — поэтому модель
    создаётся только в состоянии миграций, без единого запроса к базе. Адреса,
    уже отданные геокодером, переезжают вместе с таблицей и спрашивать их
    заново не придётся.
    """

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Geocache',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('address', models.CharField(db_index=True, max_length=100, unique=True, verbose_name='адрес')),
                        ('lat', models.FloatField(blank=True, null=True, verbose_name='широта')),
                        ('lon', models.FloatField(blank=True, null=True, verbose_name='долгота')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='дата обновления')),
                    ],
                    options={
                        'verbose_name': 'адрес в геокэше',
                        'verbose_name_plural': 'геокэш адресов',
                        'db_table': 'foodcartapp_geocache',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
