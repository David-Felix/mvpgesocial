"""
Testes para services.py do GeSocial.
"""
from decimal import Decimal
from datetime import datetime

from django.test import TestCase
from django.db import IntegrityError

from beneficios.services import gerar_numero_memorando, registrar_memorando
from beneficios.models import Memorando, MemorandoPessoa, ConfiguracaoGeral
from .base import GeSocialTestBase


class GerarNumeroMemorandoTest(GeSocialTestBase):

    def test_primeiro_memorando_do_ano(self):
        numero, ano, seq = gerar_numero_memorando()
        self.assertEqual(seq, 1)
        self.assertEqual(ano, datetime.now().year)
        self.assertEqual(numero, f'00001/{ano}')

    def test_incremento_sequencial(self):
        b = self.criar_beneficio()
        ConfiguracaoGeral.get_config()
        Memorando.objects.create(
            numero=f'00001/{datetime.now().year}',
            ano=datetime.now().year, sequencia=1,
            beneficio=b, beneficio_nome=b.nome,
            valor_total=Decimal('100'), quantidade_pessoas=1,
            usuario=self.admin_user,
        )
        numero, _, seq = gerar_numero_memorando()
        self.assertEqual(seq, 2)

    def test_formato_5_digitos(self):
        numero, _, _ = gerar_numero_memorando()
        partes = numero.split('/')
        self.assertEqual(len(partes[0]), 5)


class RegistrarMemorandoTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.pessoa = self.criar_pessoa(self.beneficio)
        ConfiguracaoGeral.get_config()

    def test_registrar_memorando_basico(self):
        pessoas_dados = [{
            'pessoa': self.pessoa,
            'nome_completo': self.pessoa.nome_completo,
            'cpf': self.pessoa.cpf,
            'valor_beneficio': self.pessoa.valor_beneficio,
            'ordem': 1,
        }]
        m = registrar_memorando(self.beneficio, pessoas_dados, self.admin_user)
        self.assertIsNotNone(m.pk)
        self.assertEqual(m.quantidade_pessoas, 1)
        self.assertEqual(m.valor_total, self.pessoa.valor_beneficio)
        self.assertEqual(m.beneficio_nome, self.beneficio.nome)

    def test_snapshot_config_salvo(self):
        config = ConfiguracaoGeral.get_config()
        config.secretaria_nome = 'Teste Snapshot'
        config.save()
        m = registrar_memorando(self.beneficio, [{
            'pessoa': self.pessoa,
            'nome_completo': 'X',
            'cpf': '000',
            'valor_beneficio': Decimal('100'),
            'ordem': 1,
        }], self.admin_user)
        self.assertEqual(m.secretaria_nome, 'Teste Snapshot')

    def test_snapshot_pessoas_criado(self):
        m = registrar_memorando(self.beneficio, [{
            'pessoa': self.pessoa,
            'nome_completo': self.pessoa.nome_completo,
            'cpf': self.pessoa.cpf,
            'valor_beneficio': self.pessoa.valor_beneficio,
            'ordem': 1,
        }], self.admin_user)
        mp = MemorandoPessoa.objects.filter(memorando=m)
        self.assertEqual(mp.count(), 1)
        self.assertEqual(mp.first().nome_completo, self.pessoa.nome_completo)

    def test_multiple_pessoas(self):
        p2 = self.criar_pessoa(self.beneficio, nome_completo='Outra', cpf='276.178.580-71')
        dados = [
            {'pessoa': self.pessoa, 'nome_completo': self.pessoa.nome_completo,
             'cpf': self.pessoa.cpf, 'valor_beneficio': Decimal('100'), 'ordem': 1},
            {'pessoa': p2, 'nome_completo': p2.nome_completo,
             'cpf': p2.cpf, 'valor_beneficio': Decimal('200'), 'ordem': 2},
        ]
        m = registrar_memorando(self.beneficio, dados, self.admin_user)
        self.assertEqual(m.quantidade_pessoas, 2)
        self.assertEqual(m.valor_total, Decimal('300'))

    def test_transacao_atomica(self):
        """Se falhar no meio, nada é salvo."""
        count_before = Memorando.objects.count()
        try:
            registrar_memorando(self.beneficio, [{
                'pessoa': self.pessoa,
                'nome_completo': 'X',
                'cpf': 'Y',
                'valor_beneficio': 'invalido',  # Vai dar erro
                'ordem': 1,
            }], self.admin_user)
        except Exception:
            pass
        self.assertEqual(Memorando.objects.count(), count_before)

    def test_conta_pagadora_snapshot(self):
        self.beneficio.conta_pagadora = 'Conta Especial 999'
        self.beneficio.save()
        m = registrar_memorando(self.beneficio, [{
            'pessoa': self.pessoa, 'nome_completo': 'X', 'cpf': 'Y',
            'valor_beneficio': Decimal('50'), 'ordem': 1,
        }], self.admin_user)
        self.assertEqual(m.conta_pagadora, 'Conta Especial 999')
