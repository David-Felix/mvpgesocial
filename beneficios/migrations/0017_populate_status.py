from django.db import migrations
from datetime import datetime
from django.utils.timezone import make_aware


def popular_status(apps, schema_editor):
    Pessoa = apps.get_model('beneficios', 'Pessoa')
    HistoricoStatus = apps.get_model('beneficios', 'HistoricoStatus')
    
    data_inicial = make_aware(datetime(2026, 1, 15, 0, 0, 0))
    
    for pessoa in Pessoa.objects.all():
        # Popular status baseado no campo ativo
        if pessoa.ativo:
            pessoa.status = 'ativo'
        else:
            pessoa.status = 'desligado'
        pessoa.save(update_fields=['status'])
        
        # Criar histórico inicial
        HistoricoStatus.objects.create(
            pessoa=pessoa,
            status_anterior=None,
            status_novo=pessoa.status,
            data=data_inicial,
            usuario=None
        )


def reverter_status(apps, schema_editor):
    Pessoa = apps.get_model('beneficios', 'Pessoa')
    HistoricoStatus = apps.get_model('beneficios', 'HistoricoStatus')
    
    for pessoa in Pessoa.objects.all():
        pessoa.ativo = (pessoa.status == 'ativo')
        pessoa.save(update_fields=['ativo'])
    
    HistoricoStatus.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0016_status_historico'),
    ]

    operations = [
        migrations.RunPython(popular_status, reverter_status),
    ]