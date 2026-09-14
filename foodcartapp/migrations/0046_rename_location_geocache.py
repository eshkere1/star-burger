from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('foodcartapp', '0045_location'),
    ]

    operations = [
        # Переименование, а не пересоздание: адреса, уже отданные геокодером,
        # переезжают вместе с таблицей и спрашивать их заново не придётся.
        migrations.RenameModel(
            old_name='Location',
            new_name='Geocache',
        ),
        migrations.AlterModelOptions(
            name='geocache',
            options={
                'verbose_name': 'адрес в геокэше',
                'verbose_name_plural': 'геокэш адресов',
            },
        ),
    ]
