"""
Testes para Validators e Context Processors do GeSocial.
"""
from django.test import TestCase, RequestFactory
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from beneficios.validators import SenhaForteValidator
from beneficios.context_processors import beneficios_ativos
from beneficios.models import Beneficio
from .base import GeSocialTestBase

User = get_user_model()


# ═══════════════════════════════════════════
# SENHA FORTE VALIDATOR
# ═══════════════════════════════════════════
class SenhaForteValidatorTest(TestCase):

    def setUp(self):
        self.validator = SenhaForteValidator()

    def test_senha_forte_valida(self):
        """Não deve levantar exceção."""
        self.validator.validate('Teste@123')

    def test_sem_maiuscula(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('teste@123')
        msgs = [str(e) for e in ctx.exception.messages]
        self.assertTrue(any('maiúscula' in m for m in msgs))

    def test_sem_minuscula(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('TESTE@123')
        msgs = [str(e) for e in ctx.exception.messages]
        self.assertTrue(any('minúscula' in m for m in msgs))

    def test_sem_numero(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('Teste@abc')
        msgs = [str(e) for e in ctx.exception.messages]
        self.assertTrue(any('número' in m for m in msgs))

    def test_sem_especial(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('Teste1234')
        msgs = [str(e) for e in ctx.exception.messages]
        self.assertTrue(any('especial' in m for m in msgs))

    def test_multiplos_erros(self):
        """Senha só com letras minúsculas deve ter múltiplos erros."""
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate('aaaaaa')
        self.assertGreater(len(ctx.exception.messages), 1)

    def test_get_help_text(self):
        text = self.validator.get_help_text()
        self.assertIn('maiúscula', text)
        self.assertIn('especial', text)


# ═══════════════════════════════════════════
# CONTEXT PROCESSOR
# ═══════════════════════════════════════════
class BeneficiosAtivosContextTest(GeSocialTestBase):

    def test_retorna_beneficios_para_logado(self):
        self.criar_beneficio(nome='Ativo1', ativo=True)
        self.criar_beneficio(nome='Inativo', ativo=False)
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.admin_user
        ctx = beneficios_ativos(request)
        self.assertIn('beneficios_menu', ctx)
        nomes = [b.nome for b in ctx['beneficios_menu']]
        self.assertIn('Ativo1', nomes)
        self.assertNotIn('Inativo', nomes)

    def test_retorna_vazio_para_anonimo(self):
        factory = RequestFactory()
        request = factory.get('/')
        request.user = AnonymousUser()
        ctx = beneficios_ativos(request)
        self.assertEqual(ctx, {})

    def test_ordering_por_nome(self):
        self.criar_beneficio(nome='Zzz', ativo=True)
        self.criar_beneficio(nome='Aaa', ativo=True)
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.admin_user
        ctx = beneficios_ativos(request)
        nomes = [b.nome for b in ctx['beneficios_menu']]
        self.assertEqual(nomes, sorted(nomes))
