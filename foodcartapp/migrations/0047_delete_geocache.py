from django.db import migrations


class Migration(migrations.Migration):
    """Geocache больше не живёт в foodcartapp — см. geocoder/0001_initial.

    Модель убирается только из состояния миграций: саму таблицу заберёт
    себе geocoder следующей же миграцией, вместе с накопленными адресами.
    """

    dependencies = [
        ('foodcartapp', '0046_rename_location_geocache'),
        ('geocoder', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name='Geocache',
                ),
            ],
            database_operations=[],
        ),
    ]
