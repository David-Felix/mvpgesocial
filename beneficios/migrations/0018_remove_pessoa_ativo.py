from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0017_populate_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pessoa',
            name='ativo',
        ),
    ]