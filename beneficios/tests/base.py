"""
Helpers e factories para criação de objetos de teste.
"""
from decimal import Decimal
from django.utils import timezone
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from beneficios.models import (
    Beneficio, Pessoa, Documento, Memorando, MemorandoPessoa,
    ConfiguracaoGeral, HistoricoStatus, LogAcao,
    BackupConfig, BackupHistorico, BackupLog,
)
from datetime import date

User = get_user_model()


class GeSocialTestBase(TestCase):
    """Classe base com helpers para todos os testes do GeSocial."""

    @classmethod
    def setUpTestData(cls):
        """Dados compartilhados entre testes (somente leitura)."""
        cls.superadmin = User.objects.create_superuser(
            username='superadmin',
            password='Super@123',
            must_change_password=False,
        )
        cls.admin_user = User.objects.create_user(
            username='admin_test',
            password='Admin@123',
            is_staff=True,
            must_change_password=False,
        )
        cls.normal_user = User.objects.create_user(
            username='usuario_test',
            password='User@1234',
            is_staff=False,
            must_change_password=False,
        )

    def setUp(self):
        self.client = Client()

    # ── Factories ──

    @staticmethod
    def criar_beneficio(**kwargs):
        defaults = {
            'nome': 'Auxílio Transporte',
            'descricao': '',
            'conta_pagadora': 'Conta 12345',
            'icone': 'bi-bus-front',
            'ativo': True,
        }
        defaults.update(kwargs)
        return Beneficio.objects.create(**defaults)

    @staticmethod
    def criar_pessoa(beneficio, **kwargs):
        defaults = {
            'nome_completo': 'Maria da Silva',
            'cpf': '529.982.247-25',
            'sexo': 'F',
            'data_nascimento': date(1990, 5, 15),
            'celular': '83999999999',
            'endereco': 'Rua Teste, 123',
            'bairro': 'Centro',
            'cidade': 'Pocinhos/PB',
            'valor_beneficio': Decimal('150.00'),
            'beneficio': beneficio,
            'status': 'ativo',
        }
        defaults.update(kwargs)
        return Pessoa.objects.create(**defaults)

    @staticmethod
    def criar_config():
        return ConfiguracaoGeral.get_config()

    def login_as(self, user_type='admin'):
        """Login rápido. user_type: 'super', 'admin', 'normal'"""
        mapping = {
            'super': self.superadmin,
            'admin': self.admin_user,
            'normal': self.normal_user,
        }
        self.client.force_login(mapping[user_type])

    # CPFs válidos para testes
    CPFS_VALIDOS = [
        '529.982.247-25',
        '276.178.580-71',
        '845.526.170-60',
        '321.654.987-04',
        '111.444.777-35',
    ]
