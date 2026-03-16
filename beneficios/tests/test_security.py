"""
Testes de segurança, permissões e proteção contra ataques do GeSocial.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from beneficios.models import Beneficio, Pessoa, ConfiguracaoGeral
from .base import GeSocialTestBase

User = get_user_model()


# ═══════════════════════════════════════════
# PROTEÇÃO DE ROTAS - USUÁRIO NÃO LOGADO
# ═══════════════════════════════════════════
class RotasNaoLogadoTest(TestCase):
    """Todas as rotas protegidas devem redirecionar para login."""

    ROTAS_PROTEGIDAS = [
        '/',
        '/pessoa/nova/',
        '/beneficios/',
        '/beneficios/novo/',
        '/usuarios/',
        '/usuarios/novo/',
        '/perfil/',
        '/memorandos/',
        '/configuracoes/',
        '/auditoria/',
        '/backup/config/',
        '/backup/logs/',
        '/sobre/',
        '/relatorios/beneficiarios/',
        '/relatorios/financeiro/',
        '/trocar-senha/',
    ]

    def test_rotas_protegidas_redirect_login(self):
        for rota in self.ROTAS_PROTEGIDAS:
            resp = self.client.get(rota)
            self.assertEqual(
                resp.status_code, 302,
                f'Rota {rota} deveria redirecionar (302), retornou {resp.status_code}'
            )
            self.assertIn('/login/', resp.url, f'Rota {rota} não redireciona para login')


# ═══════════════════════════════════════════
# PROTEÇÃO DE ROTAS - USUÁRIO NORMAL
# ═══════════════════════════════════════════
class RotasNormalBloqueadoTest(GeSocialTestBase):
    """Usuário normal não deve acessar áreas de admin."""

    ROTAS_ADMIN = [
        '/beneficios/',
        '/beneficios/novo/',
        '/usuarios/',
        '/usuarios/novo/',
        '/configuracoes/',
        '/auditoria/',
        '/backup/config/',
        '/backup/logs/',
    ]

    def test_rotas_admin_bloqueadas_para_normal(self):
        self.login_as('normal')
        for rota in self.ROTAS_ADMIN:
            resp = self.client.get(rota)
            self.assertEqual(
                resp.status_code, 302,
                f'Rota {rota} deveria bloquear usuário normal (302)'
            )


# ═══════════════════════════════════════════
# PROTEÇÃO DE OBJETOS
# ═══════════════════════════════════════════
class ProtecaoObjetosTest(GeSocialTestBase):

    def test_pessoa_404_inexistente(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoa_edit', args=[99999]))
        self.assertEqual(resp.status_code, 404)

    def test_beneficio_404_inexistente(self):
        self.login_as('admin')
        resp = self.client.get(reverse('beneficio_edit_form', args=[99999]))
        self.assertEqual(resp.status_code, 404)

    def test_memorando_404_inexistente(self):
        self.login_as('normal')
        resp = self.client.get(reverse('memorando_segunda_via', args=[99999]))
        self.assertEqual(resp.status_code, 404)


# ═══════════════════════════════════════════
# PROTEÇÃO CONTRA MANIPULAÇÃO DE PARÂMETROS
# ═══════════════════════════════════════════
class ManipulacaoParametrosTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.criar_pessoa(self.beneficio, cpf='529.982.247-25', status='ativo')

    def test_remessa_posicao_string_bloqueada(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_remessa_banco', args=[self.beneficio.pk]),
            {'status': 'ativo', 'id_de': 'DROP TABLE'}
        )
        self.assertEqual(resp.status_code, 302)

    def test_documentos_massa_posicao_invalida(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_documentos_massa', args=[self.beneficio.pk]),
            {'status': 'ativo', 'id_de': '<script>'}
        )
        self.assertEqual(resp.status_code, 302)

    def test_massa_sem_status_ativo_bloqueado(self):
        """Tentar gerar em massa sem filtro ativo = bloqueado."""
        self.login_as('normal')
        for view_name in ['gerar_memorando_massa', 'gerar_recibos_massa', 'gerar_documentos_massa']:
            resp = self.client.get(
                reverse(view_name, args=[self.beneficio.pk]),
                {'status': 'desligado'}
            )
            self.assertEqual(
                resp.status_code, 302,
                f'{view_name} deveria bloquear status != ativo'
            )


# ═══════════════════════════════════════════
# PROTEÇÃO CONTRA ESCALAÇÃO DE PRIVILÉGIOS
# ═══════════════════════════════════════════
class EscalacaoPrivilegiosTest(GeSocialTestBase):

    def test_admin_nao_edita_superadmin(self):
        self.login_as('admin')
        resp = self.client.post(reverse('usuario_edit', args=[self.superadmin.pk]), {
            'username': 'superadmin', 'nome_completo': 'Hackeado',
            'email': '', 'cargo': '', 'is_staff': True,
        })
        self.assertEqual(resp.status_code, 302)
        self.superadmin.refresh_from_db()
        self.assertNotEqual(self.superadmin.nome_completo, 'Hackeado')

    def test_admin_nao_desativa_superadmin(self):
        self.login_as('admin')
        self.client.get(reverse('usuario_toggle_active', args=[self.superadmin.pk]))
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.is_active)

    def test_usuario_nao_edita_si_mesmo_via_usuario_edit(self):
        self.login_as('admin')
        resp = self.client.get(reverse('usuario_edit', args=[self.admin_user.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_usuario_nao_desativa_si_mesmo(self):
        self.login_as('admin')
        self.client.get(reverse('usuario_toggle_active', args=[self.admin_user.pk]))
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    def test_username_readonly_no_edit(self):
        """Tentativa de alterar username via POST é ignorada."""
        self.login_as('admin')
        self.client.post(reverse('usuario_edit', args=[self.normal_user.pk]), {
            'username': 'hackeado_username',
            'nome_completo': 'OK',
            'email': '',
            'cargo': '',
            'is_staff': False,
        })
        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.username, 'usuario_test')

    def test_usuario_create_sempre_superuser_false(self):
        """Mesmo enviando is_superuser=True no POST, deve ser False."""
        self.login_as('admin')
        self.client.post(reverse('usuario_create'), {
            'username': 'tentativa_super',
            'password': 'Test@1234',
            'nome_completo': '',
            'email': '',
            'cargo': '',
            'is_staff': True,
        })
        u = User.objects.get(username='tentativa_super')
        self.assertFalse(u.is_superuser)


# ═══════════════════════════════════════════
# VALIDAÇÕES DE NEGÓCIO
# ═══════════════════════════════════════════
class RegrasNegocioTest(GeSocialTestBase):

    def test_recibo_bloqueado_pessoa_desligada(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b, status='desligado')
        self.login_as('normal')
        resp = self.client.get(reverse('gerar_recibo', args=[p.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_memorando_bloqueado_pessoa_em_espera(self):
        b = self.criar_beneficio()
        p = self.criar_pessoa(b, status='em_espera')
        self.login_as('normal')
        resp = self.client.get(reverse('gerar_memorando', args=[p.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_beneficio_disabled_edicao_pessoa(self):
        """Benefício não pode ser alterado após cadastro."""
        b1 = self.criar_beneficio(nome='B1')
        b2 = self.criar_beneficio(nome='B2')
        p = self.criar_pessoa(b1)
        self.login_as('normal')
        self.client.post(reverse('pessoa_edit', args=[p.pk]), {
            'nome_completo': p.nome_completo,
            'cpf': '529.982.247-25',
            'sexo': 'F',
            'data_nascimento': '1990-01-01',
            'celular': '',
            'endereco': 'Rua A',
            'bairro': 'Centro',
            'cidade': 'Pocinhos/PB',
            'valor_beneficio': '100',
            'beneficio': b2.pk,  # Tenta mudar
            'status': 'ativo',
        })
        p.refresh_from_db()
        self.assertEqual(p.beneficio, b1)  # Não mudou

    def test_limite_beneficios_race_condition(self):
        """Dupla verificação no POST da criação de benefício."""
        self.login_as('admin')
        self.criar_beneficio(nome='B1')
        self.criar_beneficio(nome='B2')
        # GET retorna redirect (limite atingido)
        resp = self.client.get(reverse('beneficio_create'))
        self.assertEqual(resp.status_code, 302)
        # POST também verifica
        resp = self.client.post(reverse('beneficio_create'), {
            'nome': 'B3', 'icone': 'bi-cash-coin',
        })
        self.assertFalse(Beneficio.objects.filter(nome='B3').exists())
