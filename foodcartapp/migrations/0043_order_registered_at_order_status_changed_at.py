import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodcartapp', '0042_order_comment'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='registered_at',
            field=models.DateTimeField(auto_now_add=True, db_index=True, default=django.utils.timezone.now, verbose_name='дата создания'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='status_changed_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='дата изменения статуса'),
        ),
        migrations.AlterModelOptions(
            name='order',
            options={'ordering': ['-registered_at'], 'verbose_name': 'заказ', 'verbose_name_plural': 'заказы'},
        ),
    ]
