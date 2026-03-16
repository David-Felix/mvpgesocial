"""
Testes para todos os Models do GeSocial.
"""
from decimal import Decimal
from datetime import time

from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.auth import get_user_model

from beneficios.models import (
    Beneficio, Pessoa, Documento, Memorando, MemorandoPessoa,
    ConfiguracaoGeral, HistoricoStatus, LogAcao,
    BackupConfig, BackupHistorico, BackupLog,
)
from .base import GeSocialTestBase

User = get_user_model()


# ═══════════════════════════════════════════
# USER MODEL
# ═══════════════════════════════════════════
class UserModelTest(GeSocialTestBase):

    def test_must_change_password_default_true(self):
        user = User.objects.create_user(username='novo', password='Teste@123')
        self.assertTrue(user.must_change_password)

    def test_primeiro_nome_com_nome_completo(self):
        self.admin_user.nome_completo = 'João Carlos Santos'
        self.admin_user.save()
        self.assertEqual(self.admin_user.primeiro_nome, 'João')

    def test_primeiro_nome_fallback_username(self):
        self.admin_user.nome_completo = ''
        self.admin_user.save()
        self.assertEqual(self.admin_user.primeiro_nome, 'admin_test')

    def test_campos_opcionais(self):
        user = User.objects.create_user(
            username='minimo', password='Test@1234',
            nome_completo='', cargo='',
        )
        self.assertEqual(user.nome_completo, '')
        self.assertEqual(user.cargo, '')

    def test_superadmin_flags(self):
        self.assertTrue(self.superadmin.is_superuser)
        self.assertTrue(self.superadmin.is_staff)


# ═══════════════════════════════════════════
# BENEFICIO MODEL
# ═══════════════════════════════════════════
class BeneficioModelTest(GeSocialTestBase):

    def test_criar_beneficio(self):
        b = self.criar_beneficio(nome='Renda Solidária')
        self.assertEqual(b.nome, 'Renda Solidária')
        self.assertTrue(b.ativo)

    def test_nome_exibicao_com_descricao(self):
        b = self.criar_beneficio(nome='AT', descricao='Auxílio Transporte Mensal')
        self.assertEqual(b.nome_exibicao, 'Auxílio Transporte Mensal')

    def test_nome_exibicao_sem_descricao(self):
        b = self.criar_beneficio(nome='Renda Solidária', descricao='')
        self.assertEqual(b.nome_exibicao, 'Renda Solidária')

    def test_str_usa_nome_exibicao(self):
        b = self.criar_beneficio(nome='AT', descricao='Transporte')
        self.assertEqual(str(b), 'Transporte')

    def test_ordering_por_nome(self):
        self.criar_beneficio(nome='Zzz')
        self.criar_beneficio(nome='Aaa')
        nomes = list(Beneficio.objects.values_list('nome', flat=True))
        self.assertEqual(nomes, sorted(nomes))

    def test_icone_choices_validos(self):
        icones_validos = [c[0] for c in Beneficio.ICONE_CHOICES]
        b = self.criar_beneficio(icone='bi-cash-coin')
        self.assertIn(b.icone, icones_validos)

    def test_timestamps_auto(self):
        b = self.criar_beneficio()
        self.assertIsNotNone(b.created_at)
        self.assertIsNotNone(b.updated_at)


# ═══════════════════════════════════════════
# PESSOA MODEL
# ═══════════════════════════════════════════
class PessoaModelTest(GeSocialTestBase):

    def test_criar_pessoa(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b)
        self.assertEqual(p.nome_completo, 'Maria da Silva')
        self.assertEqual(p.status, 'ativo')

    def test_cpf_ultimos_4_auto_preenchido(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b, cpf='529.982.247-25')
        # Os últimos 4 dígitos numéricos: 7250 -> wait
        # CPF: 52998224725 -> últimos 4: 4725
        cpf_numeros = ''.join(filter(str.isdigit, '529.982.247-25'))
        self.assertEqual(p.cpf_ultimos_4, cpf_numeros[-4:])

    def test_status_choices(self):
        choices = dict(Pessoa.STATUS_CHOICES)
        self.assertIn('ativo', choices)
        self.assertIn('em_espera', choices)
        self.assertIn('desligado', choices)

    def test_sexo_choices(self):
        choices = dict(Pessoa.SEXO_CHOICES)
        self.assertIn('M', choices)
        self.assertIn('F', choices)
        self.assertIn('O', choices)

    def test_valor_beneficio_default_zero(self):
        b = self.criar_beneficio()
        p = Pessoa.objects.create(
            nome_completo='Teste', cpf='276.178.580-71',
            sexo='M', endereco='Rua A', bairro='Centro',
            cidade='Pocinhos/PB', beneficio=b,
        )
        self.assertEqual(p.valor_beneficio, Decimal('0'))

    def test_on_delete_protect_beneficio(self):
        b = self.criar_beneficio()
        self.criar_pessoa(b)
        with self.assertRaises(Exception):
            b.delete()

    def test_ordering_por_nome_completo(self):
        b = self.criar_beneficio()
        self.criar_pessoa(b, nome_completo='Zuleide', cpf='276.178.580-71')
        self.criar_pessoa(b, nome_completo='Ana', cpf='845.526.170-60')
        nomes = list(Pessoa.objects.values_list('nome_completo', flat=True))
        self.assertEqual(nomes, sorted(nomes))

    def test_str_representation(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b, nome_completo='João')
        self.assertIn('João', str(p))


# ═══════════════════════════════════════════
# DOCUMENTO MODEL
# ═══════════════════════════════════════════
class DocumentoModelTest(GeSocialTestBase):

    def test_one_to_one_pessoa(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b)
        from django.core.files.uploadedfile import SimpleUploadedFile
        arquivo = SimpleUploadedFile('doc.pdf', b'%PDF-test', content_type='application/pdf')
        doc = Documento.objects.create(pessoa=p, arquivo=arquivo)
        self.assertEqual(doc.pessoa, p)
        self.assertEqual(p.documento, doc)

    def test_cascade_delete_com_pessoa(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b)
        from django.core.files.uploadedfile import SimpleUploadedFile
        arquivo = SimpleUploadedFile('doc.pdf', b'%PDF-test', content_type='application/pdf')
        Documento.objects.create(pessoa=p, arquivo=arquivo)
        p.delete()
        self.assertEqual(Documento.objects.count(), 0)


# ═══════════════════════════════════════════
# MEMORANDO MODEL
# ═══════════════════════════════════════════
class MemorandoModelTest(GeSocialTestBase):

    def test_criar_memorando(self):
        b = self.criar_beneficio()
        m = Memorando.objects.create(
            numero='00001/2026', ano=2026, sequencia=1,
            beneficio=b, beneficio_nome=b.nome,
            conta_pagadora='Conta 123',
            valor_total=Decimal('300.00'), quantidade_pessoas=2,
            usuario=self.admin_user,
        )
        self.assertEqual(m.numero, '00001/2026')

    def test_unique_constraint_ano_sequencia(self):
        b = self.criar_beneficio()
        Memorando.objects.create(
            numero='00001/2026', ano=2026, sequencia=1,
            beneficio=b, beneficio_nome=b.nome,
            valor_total=Decimal('100'), quantidade_pessoas=1,
            usuario=self.admin_user,
        )
        with self.assertRaises(IntegrityError):
            Memorando.objects.create(
                numero='00001x/2026', ano=2026, sequencia=1,
                beneficio=b, beneficio_nome=b.nome,
                valor_total=Decimal('100'), quantidade_pessoas=1,
                usuario=self.admin_user,
            )

    def test_beneficio_set_null_on_delete(self):
        b = self.criar_beneficio(nome='Temp')
        m = Memorando.objects.create(
            numero='00001/2026', ano=2026, sequencia=1,
            beneficio=b, beneficio_nome='Temp',
            valor_total=Decimal('100'), quantidade_pessoas=1,
            usuario=self.admin_user,
        )
        # Precisa remover pessoas antes de deletar benefício
        Pessoa.objects.filter(beneficio=b).delete()
        b.delete()
        m.refresh_from_db()
        self.assertIsNone(m.beneficio)
        self.assertEqual(m.beneficio_nome, 'Temp')

    def test_snapshot_config(self):
        b = self.criar_beneficio()
        m = Memorando.objects.create(
            numero='00002/2026', ano=2026, sequencia=2,
            beneficio=b, beneficio_nome=b.nome,
            valor_total=Decimal('100'), quantidade_pessoas=1,
            usuario=self.admin_user,
            secretaria_nome='Teste Secretária',
        )
        self.assertEqual(m.secretaria_nome, 'Teste Secretária')

    def test_ordering_desc_created_at(self):
        meta = Memorando._meta
        self.assertEqual(meta.ordering, ['-created_at'])


# ═══════════════════════════════════════════
# MEMORANDO PESSOA MODEL
# ═══════════════════════════════════════════
class MemorandoPessoaModelTest(GeSocialTestBase):

    def test_criar_snapshot_pessoa(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b)
        m = Memorando.objects.create(
            numero='00001/2026', ano=2026, sequencia=1,
            beneficio=b, beneficio_nome=b.nome,
            valor_total=Decimal('150'), quantidade_pessoas=1,
            usuario=self.admin_user,
        )
        mp = MemorandoPessoa.objects.create(
            memorando=m, pessoa=p,
            nome_completo=p.nome_completo,
            valor_beneficio=p.valor_beneficio,
            ordem=1,
        )
        self.assertEqual(mp.nome_completo, 'Maria da Silva')

    def test_cascade_delete_com_memorando(self):
        b = self.criar_beneficio()
        m = Memorando.objects.create(
            numero='00001/2026', ano=2026, sequencia=1,
            beneficio=b, beneficio_nome=b.nome,
            valor_total=Decimal('100'), quantidade_pessoas=1,
            usuario=self.admin_user,
        )
        MemorandoPessoa.objects.create(
            memorando=m, pessoa=None,
            nome_completo='Teste', valor_beneficio=Decimal('100'), ordem=1,
        )
        m.delete()
        self.assertEqual(MemorandoPessoa.objects.count(), 0)

    def test_pessoa_set_null_on_delete(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b)
        m = Memorando.objects.create(
            numero='00001/2026', ano=2026, sequencia=1,
            beneficio=b, beneficio_nome=b.nome,
            valor_total=Decimal('150'), quantidade_pessoas=1,
            usuario=self.admin_user,
        )
        mp = MemorandoPessoa.objects.create(
            memorando=m, pessoa=p,
            nome_completo=p.nome_completo,
            valor_beneficio=p.valor_beneficio, ordem=1,
        )
        p.delete()
        mp.refresh_from_db()
        self.assertIsNone(mp.pessoa)
        self.assertEqual(mp.nome_completo, 'Maria da Silva')


# ═══════════════════════════════════════════
# CONFIGURAÇÃO GERAL (Singleton)
# ═══════════════════════════════════════════
class ConfiguracaoGeralTest(GeSocialTestBase):

    def test_singleton_pk_sempre_1(self):
        config = ConfiguracaoGeral.get_config()
        self.assertEqual(config.pk, 1)
        config2 = ConfiguracaoGeral(pk=99)
        config2.save()
        config2.refresh_from_db()
        self.assertEqual(config2.pk, 1)

    def test_get_config_cria_se_nao_existe(self):
        ConfiguracaoGeral.objects.all().delete()
        config = ConfiguracaoGeral.get_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.pk, 1)

    def test_defaults(self):
        config = ConfiguracaoGeral.get_config()
        self.assertIn('Zélia', config.secretaria_nome)
        self.assertEqual(config.cep, '58150-000')

    def test_str(self):
        config = ConfiguracaoGeral.get_config()
        self.assertEqual(str(config), 'Configurações Gerais')


# ═══════════════════════════════════════════
# HISTÓRICO STATUS
# ═══════════════════════════════════════════
class HistoricoStatusTest(GeSocialTestBase):

    def test_registrar_historico(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b)
        h = HistoricoStatus.objects.create(
            pessoa=p, status_anterior=None, status_novo='ativo',
            data=timezone.now(), usuario=self.admin_user,
        )
        self.assertIsNone(h.status_anterior)
        self.assertEqual(h.status_novo, 'ativo')

    def test_cascade_delete_com_pessoa(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b)
        HistoricoStatus.objects.create(
            pessoa=p, status_anterior=None, status_novo='ativo',
            data=timezone.now(), usuario=self.admin_user,
        )
        p.delete()
        self.assertEqual(HistoricoStatus.objects.count(), 0)

    def test_ordering_desc_data(self):
        self.assertEqual(HistoricoStatus._meta.ordering, ['-data'])


# ═══════════════════════════════════════════
# LOG AÇÃO
# ═══════════════════════════════════════════
class LogAcaoTest(GeSocialTestBase):

    def test_criar_log(self):
        log = LogAcao.objects.create(
            usuario=self.admin_user, tipo='remessa_banco',
            descricao='Remessa gerada', ip='127.0.0.1',
        )
        self.assertEqual(log.tipo, 'remessa_banco')
        self.assertIsNotNone(log.created_at)

    def test_usuario_set_null_on_delete(self):
        user = User.objects.create_user(username='temp_log', password='T@123456')
        user.must_change_password = False
        user.save()
        log = LogAcao.objects.create(
            usuario=user, tipo='status_ativar', descricao='Teste',
        )
        user.delete()
        log.refresh_from_db()
        self.assertIsNone(log.usuario)

    def test_tipos_validos(self):
        tipos = [c[0] for c in LogAcao.TIPO_CHOICES]
        self.assertIn('memorando_individual', tipos)
        self.assertIn('remessa_banco', tipos)
        self.assertIn('status_ativar', tipos)
        self.assertIn('status_desligar', tipos)


# ═══════════════════════════════════════════
# BACKUP CONFIG (Singleton)
# ═══════════════════════════════════════════
class BackupConfigTest(GeSocialTestBase):

    def test_singleton(self):
        config = BackupConfig.get_config()
        self.assertEqual(config.pk, 1)

    def test_rclone_destino_property(self):
        config = BackupConfig.get_config()
        config.rclone_nome_remote = 'DRIVE'
        config.rclone_pasta = 'BackupGESOCIAL'
        self.assertEqual(config.rclone_destino, 'DRIVE:BackupGESOCIAL')

    def test_rclone_destino_strip(self):
        config = BackupConfig.get_config()
        config.rclone_nome_remote = ' DRIVE: '
        config.rclone_pasta = ' /pasta/ '
        self.assertEqual(config.rclone_destino, 'DRIVE:pasta')

    def test_defaults(self):
        config = BackupConfig.get_config()
        self.assertEqual(config.rclone_pasta, 'BackupGESOCIAL')
        self.assertFalse(config.agendamento_db_ativo)


# ═══════════════════════════════════════════
# BACKUP HISTORICO
# ═══════════════════════════════════════════
class BackupHistoricoTest(GeSocialTestBase):

    def test_criar_historico(self):
        bh = BackupHistorico.objects.create(
            tipo='manual', tipo_backup='banco',
            itens='banco', status='executando',
            arquivo_nome='BK_DB_2026.tar.zst.gpg',
        )
        self.assertEqual(bh.status, 'executando')

    def test_tamanho_formatado_bytes(self):
        bh = BackupHistorico(tamanho_bytes=500)
        self.assertEqual(bh.tamanho_formatado, '500 B')

    def test_tamanho_formatado_kb(self):
        bh = BackupHistorico(tamanho_bytes=2048)
        self.assertEqual(bh.tamanho_formatado, '2.0 KB')

    def test_tamanho_formatado_mb(self):
        bh = BackupHistorico(tamanho_bytes=5 * 1024 * 1024)
        self.assertEqual(bh.tamanho_formatado, '5.0 MB')

    def test_tamanho_formatado_gb(self):
        bh = BackupHistorico(tamanho_bytes=2 * 1024 * 1024 * 1024)
        self.assertEqual(bh.tamanho_formatado, '2.00 GB')

    def test_tamanho_formatado_none(self):
        bh = BackupHistorico(tamanho_bytes=None)
        self.assertEqual(bh.tamanho_formatado, '-')


# ═══════════════════════════════════════════
# BACKUP LOG
# ═══════════════════════════════════════════
class BackupLogTest(GeSocialTestBase):

    def test_criar_log(self):
        bh = BackupHistorico.objects.create(
            tipo='manual', tipo_backup='banco',
            itens='banco', status='executando',
        )
        log = BackupLog.objects.create(
            backup=bh, etapa='inicio', status='sucesso', mensagem='OK',
        )
        self.assertEqual(log.etapa, 'inicio')

    def test_cascade_delete(self):
        bh = BackupHistorico.objects.create(
            tipo='manual', tipo_backup='banco',
            itens='banco', status='sucesso',
        )
        BackupLog.objects.create(backup=bh, etapa='inicio', status='sucesso')
        bh.delete()
        self.assertEqual(BackupLog.objects.count(), 0)
