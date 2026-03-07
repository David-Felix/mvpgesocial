from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import encrypted_model_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('beneficios', '0015_user_must_change_password'),  # Ajuste para a última migração existente
    ]

    operations = [
        # Adicionar campo status
        migrations.AddField(
            model_name='pessoa',
            name='status',
            field=models.CharField(
                choices=[('ativo', 'Ativo'), ('em_espera', 'Em Espera'), ('desligado', 'Desligado')],
                default='ativo',
                max_length=20,
            ),
        ),
        # Criar model HistoricoStatus
        migrations.CreateModel(
            name='HistoricoStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status_anterior', models.CharField(blank=True, choices=[('ativo', 'Ativo'), ('em_espera', 'Em Espera'), ('desligado', 'Desligado'), ('cadastrado', 'Cadastrado')], max_length=20, null=True)),
                ('status_novo', models.CharField(choices=[('ativo', 'Ativo'), ('em_espera', 'Em Espera'), ('desligado', 'Desligado')], max_length=20)),
                ('data', models.DateTimeField()),
                ('pessoa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='historico_status', to='beneficios.pessoa')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Histórico de Status',
                'verbose_name_plural': 'Históricos de Status',
                'ordering': ['-data'],
            },
        ),
        # Remover unique do CPF
        migrations.AlterField(
            model_name='pessoa',
            name='cpf',
            field=encrypted_model_fields.fields.EncryptedCharField(max_length=14, verbose_name='CPF'),
        ),
    ]