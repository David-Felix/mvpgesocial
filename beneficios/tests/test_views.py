"""
Testes para todas as Views do GeSocial.
Cobre: autenticação, permissões, CRUD, status transitions, geração de PDFs, filtros.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from beneficios.models import (
    Beneficio, Pessoa, Documento, Memorando, MemorandoPessoa,
    ConfiguracaoGeral, HistoricoStatus, LogAcao,
    BackupConfig, BackupHistorico,
)
from .base import GeSocialTestBase

User = get_user_model()


# ═══════════════════════════════════════════
# AUTENTICAÇÃO
# ═══════════════════════════════════════════
class AuthViewsTest(GeSocialTestBase):

    def test_login_page_acessivel(self):
        resp = self.client.get('/login/')
        self.assertEqual(resp.status_code, 200)

    def test_login_valido(self):
        resp = self.client.post('/login/', {
            'username': 'admin_test', 'password': 'Admin@123',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, '/')

    def test_login_invalido(self):
        resp = self.client.post('/login/', {
            'username': 'admin_test', 'password': 'errada',
        })
        self.assertEqual(resp.status_code, 200)

    def test_logout(self):
        self.login_as('admin')
        resp = self.client.post('/logout/')
        self.assertIn(resp.status_code, [200, 302])

    def test_redirect_sem_login(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)


# ═══════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════
class DashboardViewTest(GeSocialTestBase):

    def test_dashboard_acesso(self):
        self.login_as('normal')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_context(self):
        self.login_as('admin')
        b = self.criar_beneficio()
        self.criar_pessoa(b, status='ativo')
        resp = self.client.get('/')
        self.assertIn('beneficios', resp.context)
        self.assertIn('total_mensal_geral', resp.context)
        self.assertIn('distribuicao_valor', resp.context)

    def test_dashboard_apenas_beneficios_ativos(self):
        self.login_as('admin')
        self.criar_beneficio(nome='Ativo', ativo=True)
        self.criar_beneficio(nome='Inativo', ativo=False)
        resp = self.client.get('/')
        nomes = [b['nome'] for b in resp.context['beneficios']]
        self.assertNotIn('Inativo', nomes)

    def test_dashboard_calculo_total_mensal(self):
        self.login_as('admin')
        b = self.criar_beneficio()
        self.criar_pessoa(b, cpf='529.982.247-25', valor_beneficio=Decimal('100'), status='ativo')
        self.criar_pessoa(b, cpf='276.178.580-71', valor_beneficio=Decimal('200'), status='ativo')
        self.criar_pessoa(b, cpf='845.526.170-60', valor_beneficio=Decimal('50'), status='desligado')
        resp = self.client.get('/')
        # Total mensal só conta ativos
        self.assertEqual(resp.context['total_mensal_geral'], 300)

    def test_dashboard_contagem_status(self):
        self.login_as('admin')
        b = self.criar_beneficio()
        self.criar_pessoa(b, cpf='529.982.247-25', status='ativo')
        self.criar_pessoa(b, cpf='276.178.580-71', status='em_espera')
        self.criar_pessoa(b, cpf='845.526.170-60', status='desligado')
        resp = self.client.get('/')
        self.assertEqual(resp.context['total_ativos_geral'], 1)
        self.assertEqual(resp.context['total_em_espera_geral'], 1)
        self.assertEqual(resp.context['total_desativados_geral'], 1)


# ═══════════════════════════════════════════
# PESSOA CRUD
# ═══════════════════════════════════════════
class PessoaCreateViewTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()

    def _post_data(self, **overrides):
        data = {
            'nome_completo': 'Teste Create',
            'cpf': '529.982.247-25',
            'sexo': 'F',
            'data_nascimento': '1985-03-10',
            'celular': '83999001122',
            'endereco': 'Rua Nova, 50',
            'bairro': 'Centro',
            'cidade': 'Pocinhos/PB',
            'valor_beneficio': '120.00',
            'beneficio': self.beneficio.pk,
            'status': 'ativo',
        }
        data.update(overrides)
        return data

    def test_get_form(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoa_create'))
        self.assertEqual(resp.status_code, 200)

    def test_create_sucesso(self):
        self.login_as('normal')
        resp = self.client.post(reverse('pessoa_create'), self._post_data())
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Pessoa.objects.filter(nome_completo='Teste Create').exists())

    def test_historico_status_criado(self):
        self.login_as('normal')
        self.client.post(reverse('pessoa_create'), self._post_data())
        p = Pessoa.objects.get(nome_completo='Teste Create')
        h = HistoricoStatus.objects.filter(pessoa=p).first()
        self.assertIsNotNone(h)
        self.assertIsNone(h.status_anterior)
        self.assertEqual(h.status_novo, 'ativo')

    def test_preselecao_beneficio_via_querystring(self):
        self.login_as('normal')
        resp = self.client.get(f"{reverse('pessoa_create')}?beneficio={self.beneficio.pk}")
        self.assertEqual(resp.status_code, 200)

    def test_create_com_documento(self):
        self.login_as('normal')
        pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        data = self._post_data()
        data['arquivo'] = pdf
        self.client.post(reverse('pessoa_create'), data)
        p = Pessoa.objects.get(nome_completo='Teste Create')
        self.assertTrue(hasattr(p, 'documento'))


class PessoaEditViewTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.pessoa = self.criar_pessoa(self.beneficio)

    def test_get_edit_form(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoa_edit', args=[self.pessoa.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('historico_status', resp.context)

    def test_edit_sucesso(self):
        self.login_as('normal')
        resp = self.client.post(reverse('pessoa_edit', args=[self.pessoa.pk]), {
            'nome_completo': 'Maria Editada',
            'cpf': '529.982.247-25',
            'sexo': 'F',
            'data_nascimento': '1990-05-15',
            'celular': '83999999999',
            'endereco': 'Rua Editada',
            'bairro': 'Centro',
            'cidade': 'Pocinhos/PB',
            'valor_beneficio': '200.00',
            'beneficio': self.beneficio.pk,
            'status': 'ativo',
        })
        self.assertEqual(resp.status_code, 302)
        self.pessoa.refresh_from_db()
        self.assertEqual(self.pessoa.nome_completo, 'Maria Editada')

    def test_mudanca_status_registra_historico(self):
        self.login_as('normal')
        self.client.post(reverse('pessoa_edit', args=[self.pessoa.pk]), {
            'nome_completo': self.pessoa.nome_completo,
            'cpf': '529.982.247-25',
            'sexo': 'F',
            'data_nascimento': '1990-05-15',
            'celular': '',
            'endereco': 'Rua A',
            'bairro': 'Centro',
            'cidade': 'Pocinhos/PB',
            'valor_beneficio': '150',
            'beneficio': self.beneficio.pk,
            'status': 'desligado',
        })
        h = HistoricoStatus.objects.filter(pessoa=self.pessoa).order_by('-data').first()
        self.assertEqual(h.status_anterior, 'ativo')
        self.assertEqual(h.status_novo, 'desligado')


# ═══════════════════════════════════════════
# STATUS TRANSITIONS
# ═══════════════════════════════════════════
class PessoaStatusViewsTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.pessoa = self.criar_pessoa(self.beneficio, status='ativo')

    def test_desligar(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoa_desligar', args=[self.pessoa.pk]))
        self.assertEqual(resp.status_code, 302)
        self.pessoa.refresh_from_db()
        self.assertEqual(self.pessoa.status, 'desligado')

    def test_ativar_de_desligado(self):
        self.pessoa.status = 'desligado'
        self.pessoa.save()
        self.login_as('normal')
        self.client.get(reverse('pessoa_ativar', args=[self.pessoa.pk]))
        self.pessoa.refresh_from_db()
        self.assertEqual(self.pessoa.status, 'ativo')

    def test_espera(self):
        self.login_as('normal')
        self.client.get(reverse('pessoa_espera', args=[self.pessoa.pk]))
        self.pessoa.refresh_from_db()
        self.assertEqual(self.pessoa.status, 'em_espera')

    def test_ativar_ja_ativo_nao_muda(self):
        self.login_as('normal')
        self.client.get(reverse('pessoa_ativar', args=[self.pessoa.pk]))
        self.pessoa.refresh_from_db()
        self.assertEqual(self.pessoa.status, 'ativo')

    def test_desligar_cria_historico(self):
        self.login_as('normal')
        self.client.get(reverse('pessoa_desligar', args=[self.pessoa.pk]))
        h = HistoricoStatus.objects.filter(pessoa=self.pessoa).order_by('-data').first()
        self.assertEqual(h.status_anterior, 'ativo')
        self.assertEqual(h.status_novo, 'desligado')

    def test_desligar_cria_log_acao(self):
        self.login_as('normal')
        self.client.get(reverse('pessoa_desligar', args=[self.pessoa.pk]))
        self.assertTrue(LogAcao.objects.filter(tipo='status_desligar').exists())

    def test_ativar_cria_log_acao(self):
        self.pessoa.status = 'desligado'
        self.pessoa.save()
        self.login_as('normal')
        self.client.get(reverse('pessoa_ativar', args=[self.pessoa.pk]))
        self.assertTrue(LogAcao.objects.filter(tipo='status_ativar').exists())


# ═══════════════════════════════════════════
# PESSOAS POR BENEFÍCIO (Listagem + Filtros)
# ═══════════════════════════════════════════
class PessoasPorBeneficioViewTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.p1 = self.criar_pessoa(self.beneficio, nome_completo='Ana', cpf='529.982.247-25', status='ativo', valor_beneficio=Decimal('100'))
        self.p2 = self.criar_pessoa(self.beneficio, nome_completo='Bruna', cpf='276.178.580-71', status='em_espera', valor_beneficio=Decimal('200'))
        self.p3 = self.criar_pessoa(self.beneficio, nome_completo='Carlos', cpf='845.526.170-60', status='desligado', valor_beneficio=Decimal('150'))

    def test_listagem_basica(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoas_por_beneficio', args=[self.beneficio.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_filtro_status_ativo(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoas_por_beneficio', args=[self.beneficio.pk]), {'status': 'ativo'})
        self.assertEqual(resp.status_code, 200)

    def test_filtro_nome(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoas_por_beneficio', args=[self.beneficio.pk]), {
            'nome': 'Ana', 'status': 'todos',
        })
        self.assertEqual(resp.status_code, 200)

    def test_context_stats(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoas_por_beneficio', args=[self.beneficio.pk]))
        self.assertIn('total_ativos', resp.context)
        self.assertIn('distribuicao_valor', resp.context)

    def test_beneficio_404(self):
        self.login_as('normal')
        resp = self.client.get(reverse('pessoas_por_beneficio', args=[9999]))
        self.assertEqual(resp.status_code, 404)


# ═══════════════════════════════════════════
# BENEFÍCIO CRUD
# ═══════════════════════════════════════════
class BeneficioViewsTest(GeSocialTestBase):

    def test_list_apenas_admin(self):
        self.login_as('normal')
        resp = self.client.get(reverse('beneficios_list'))
        self.assertEqual(resp.status_code, 302)  # redirect dashboard

    def test_list_admin(self):
        self.login_as('admin')
        resp = self.client.get(reverse('beneficios_list'))
        self.assertEqual(resp.status_code, 200)

    def test_create_admin(self):
        self.login_as('admin')
        resp = self.client.post(reverse('beneficio_create'), {
            'nome': 'Novo Benefício',
            'descricao': 'Descrição',
            'conta_pagadora': 'Conta 999',
            'icone': 'bi-cash-coin',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Beneficio.objects.filter(nome='Novo Benefício').exists())

    def test_create_normal_bloqueado(self):
        self.login_as('normal')
        resp = self.client.post(reverse('beneficio_create'), {
            'nome': 'Tentativa', 'icone': 'bi-cash-coin',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Beneficio.objects.filter(nome='Tentativa').exists())

    def test_limite_beneficios(self):
        """Limite de 2 benefícios (LIMITE_BENEFICIOS = 2)"""
        self.login_as('admin')
        self.criar_beneficio(nome='B1')
        self.criar_beneficio(nome='B2')
        resp = self.client.post(reverse('beneficio_create'), {
            'nome': 'B3', 'icone': 'bi-cash-coin',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Beneficio.objects.filter(nome='B3').exists())

    def test_edit_beneficio(self):
        self.login_as('admin')
        b = self.criar_beneficio()
        resp = self.client.post(reverse('beneficio_edit_form', args=[b.pk]), {
            'nome': 'Editado',
            'descricao': 'Nova desc',
            'conta_pagadora': '',
            'icone': 'bi-bus-front',
        })
        self.assertEqual(resp.status_code, 302)
        b.refresh_from_db()
        self.assertEqual(b.nome, 'Editado')

    def test_toggle_desativar(self):
        self.login_as('admin')
        b = self.criar_beneficio(ativo=True)
        self.client.get(reverse('beneficio_toggle', args=[b.pk]))
        b.refresh_from_db()
        self.assertFalse(b.ativo)

    def test_toggle_ativar(self):
        self.login_as('admin')
        b = self.criar_beneficio(ativo=False)
        self.client.get(reverse('beneficio_toggle', args=[b.pk]))
        b.refresh_from_db()
        self.assertTrue(b.ativo)

    def test_toggle_normal_bloqueado(self):
        self.login_as('normal')
        b = self.criar_beneficio(ativo=True)
        self.client.get(reverse('beneficio_toggle', args=[b.pk]))
        b.refresh_from_db()
        self.assertTrue(b.ativo)  # não mudou


# ═══════════════════════════════════════════
# USUÁRIOS CRUD
# ═══════════════════════════════════════════
class UsuarioViewsTest(GeSocialTestBase):

    def test_list_admin(self):
        self.login_as('admin')
        resp = self.client.get(reverse('usuarios_list'))
        self.assertEqual(resp.status_code, 200)

    def test_list_normal_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(reverse('usuarios_list'))
        self.assertEqual(resp.status_code, 302)

    def test_admin_nao_ve_superusers(self):
        self.login_as('admin')
        resp = self.client.get(reverse('usuarios_list'))
        usuarios = resp.context['usuarios']
        usernames = [u.username for u in usuarios]
        self.assertNotIn('superadmin', usernames)

    def test_superadmin_ve_todos(self):
        self.login_as('super')
        resp = self.client.get(reverse('usuarios_list'))
        usuarios = resp.context['usuarios']
        usernames = [u.username for u in usuarios]
        self.assertIn('superadmin', usernames)

    def test_create_usuario(self):
        self.login_as('admin')
        resp = self.client.post(reverse('usuario_create'), {
            'username': 'new_user',
            'password': 'Test@1234',
            'nome_completo': 'Novo',
            'email': '',
            'cargo': '',
            'is_staff': False,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(username='new_user').exists())

    def test_edit_usuario(self):
        self.login_as('admin')
        resp = self.client.post(reverse('usuario_edit', args=[self.normal_user.pk]), {
            'username': self.normal_user.username,
            'nome_completo': 'Editado',
            'email': 'edit@t.com',
            'cargo': 'Novo Cargo',
            'is_staff': False,
        })
        self.assertEqual(resp.status_code, 302)
        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.nome_completo, 'Editado')

    def test_editar_si_mesmo_bloqueado(self):
        self.login_as('admin')
        resp = self.client.get(reverse('usuario_edit', args=[self.admin_user.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_editar_superadmin_bloqueado_para_admin(self):
        self.login_as('admin')
        resp = self.client.get(reverse('usuario_edit', args=[self.superadmin.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_toggle_active(self):
        self.login_as('admin')
        self.client.get(reverse('usuario_toggle_active', args=[self.normal_user.pk]))
        self.normal_user.refresh_from_db()
        self.assertFalse(self.normal_user.is_active)

    def test_toggle_superadmin_bloqueado(self):
        self.login_as('admin')
        self.client.get(reverse('usuario_toggle_active', args=[self.superadmin.pk]))
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.is_active)

    def test_toggle_si_mesmo_bloqueado(self):
        self.login_as('admin')
        self.client.get(reverse('usuario_toggle_active', args=[self.admin_user.pk]))
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)


# ═══════════════════════════════════════════
# MEU PERFIL
# ═══════════════════════════════════════════
class MeuPerfilViewTest(GeSocialTestBase):

    def test_get_perfil(self):
        self.login_as('normal')
        resp = self.client.get(reverse('meu_perfil'))
        self.assertEqual(resp.status_code, 200)

    def test_post_perfil(self):
        self.login_as('normal')
        resp = self.client.post(reverse('meu_perfil'), {
            'email': 'novo@email.com',
            'cargo': 'Novo Cargo',
        })
        self.assertEqual(resp.status_code, 302)
        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.cargo, 'Novo Cargo')


# ═══════════════════════════════════════════
# TROCAR SENHA
# ═══════════════════════════════════════════
class TrocarSenhaViewTest(GeSocialTestBase):

    def test_get_form(self):
        self.login_as('normal')
        resp = self.client.get(reverse('trocar_senha'))
        self.assertEqual(resp.status_code, 200)

    def test_trocar_senha_sucesso(self):
        self.login_as('normal')
        resp = self.client.post(reverse('trocar_senha'), {
            'old_password': 'User@1234',
            'new_password1': 'NovaSenh@99',
            'new_password2': 'NovaSenh@99',
        })
        self.assertEqual(resp.status_code, 302)
        self.normal_user.refresh_from_db()
        self.assertFalse(self.normal_user.must_change_password)

    def test_trocar_senha_errada(self):
        self.login_as('normal')
        resp = self.client.post(reverse('trocar_senha'), {
            'old_password': 'errada',
            'new_password1': 'NovaSenh@99',
            'new_password2': 'NovaSenh@99',
        })
        self.assertEqual(resp.status_code, 200)  # Fica na página com erros


# ═══════════════════════════════════════════
# GERAÇÃO DE PDFs (Recibo, Memorando)
# ═══════════════════════════════════════════
class GeracaoPDFViewsTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.pessoa_ativa = self.criar_pessoa(self.beneficio, status='ativo')
        self.pessoa_desligada = self.criar_pessoa(
            self.beneficio, nome_completo='Desligada', cpf='276.178.580-71', status='desligado'
        )
        ConfiguracaoGeral.get_config()

    def test_recibo_pessoa_ativa(self):
        self.login_as('normal')
        resp = self.client.get(reverse('gerar_recibo', args=[self.pessoa_ativa.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_recibo_pessoa_desligada_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(reverse('gerar_recibo', args=[self.pessoa_desligada.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_memorando_pessoa_ativa(self):
        self.login_as('normal')
        resp = self.client.get(reverse('gerar_memorando', args=[self.pessoa_ativa.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(Memorando.objects.exists())

    def test_memorando_pessoa_desligada_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(reverse('gerar_memorando', args=[self.pessoa_desligada.pk]))
        self.assertEqual(resp.status_code, 302)


# ═══════════════════════════════════════════
# GERAÇÃO EM MASSA
# ═══════════════════════════════════════════
class GeracaoMassaViewsTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.p1 = self.criar_pessoa(self.beneficio, cpf='529.982.247-25', status='ativo')
        self.p2 = self.criar_pessoa(self.beneficio, nome_completo='Outra', cpf='276.178.580-71', status='ativo')
        ConfiguracaoGeral.get_config()

    def test_memorando_massa_ativo(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_memorando_massa', args=[self.beneficio.pk]),
            {'status': 'ativo'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_memorando_massa_status_errado_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_memorando_massa', args=[self.beneficio.pk]),
            {'status': 'todos'}
        )
        self.assertEqual(resp.status_code, 302)

    def test_recibos_massa(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_recibos_massa', args=[self.beneficio.pk]),
            {'status': 'ativo'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_recibos_massa_status_errado(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_recibos_massa', args=[self.beneficio.pk]),
            {'status': 'desligado'}
        )
        self.assertEqual(resp.status_code, 302)


# ═══════════════════════════════════════════
# REMESSA BANCO
# ═══════════════════════════════════════════
class RemessaBancoViewTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.criar_pessoa(self.beneficio, cpf='529.982.247-25', status='ativo')

    def test_remessa_csv_gerada(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_remessa_banco', args=[self.beneficio.pk]),
            {'status': 'ativo'}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])

    def test_remessa_status_errado_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_remessa_banco', args=[self.beneficio.pk]),
            {'status': 'todos'}
        )
        self.assertEqual(resp.status_code, 302)

    def test_remessa_posicao_invalida(self):
        self.login_as('normal')
        resp = self.client.get(
            reverse('gerar_remessa_banco', args=[self.beneficio.pk]),
            {'status': 'ativo', 'id_de': 'abc'}
        )
        self.assertEqual(resp.status_code, 302)


# ═══════════════════════════════════════════
# MEMORANDOS LISTA E SEGUNDA VIA
# ═══════════════════════════════════════════
class MemorandosViewTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        ConfiguracaoGeral.get_config()

    def test_memorandos_lista(self):
        self.login_as('normal')
        resp = self.client.get(reverse('memorandos_lista'))
        self.assertEqual(resp.status_code, 200)

    def test_segunda_via(self):
        self.login_as('normal')
        p = self.criar_pessoa(self.beneficio, status='ativo')
        # Gerar memorando primeiro
        from beneficios.services import registrar_memorando
        m = registrar_memorando(self.beneficio, [{
            'pessoa': p, 'nome_completo': p.nome_completo,
            'cpf': p.cpf, 'valor_beneficio': p.valor_beneficio, 'ordem': 1,
        }], self.admin_user)
        resp = self.client.get(reverse('memorando_segunda_via', args=[m.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')


# ═══════════════════════════════════════════
# CONFIGURAÇÕES GERAIS
# ═══════════════════════════════════════════
class ConfiguracoesViewTest(GeSocialTestBase):

    def test_acesso_admin(self):
        self.login_as('admin')
        resp = self.client.get(reverse('configuracoes_gerais'))
        self.assertEqual(resp.status_code, 200)

    def test_acesso_normal_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(reverse('configuracoes_gerais'))
        self.assertEqual(resp.status_code, 302)

    def test_salvar_configuracoes(self):
        self.login_as('admin')
        resp = self.client.post(reverse('configuracoes_gerais'), {
            'secretaria_nome': 'Nova Secretária',
            'secretaria_cargo': 'Secretária',
            'financas_nome': 'Novo Financeiro',
            'financas_cargo': 'Secretário',
            'email_institucional': 'teste@gov.br',
            'endereco': 'Rua Nova',
            'cep': '58000-000',
        })
        self.assertEqual(resp.status_code, 302)
        config = ConfiguracaoGeral.get_config()
        self.assertEqual(config.secretaria_nome, 'Nova Secretária')


# ═══════════════════════════════════════════
# AUDITORIA
# ═══════════════════════════════════════════
class AuditoriaViewTest(GeSocialTestBase):

    def test_acesso_admin(self):
        self.login_as('admin')
        resp = self.client.get(reverse('auditoria'))
        self.assertEqual(resp.status_code, 200)

    def test_acesso_normal_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(reverse('auditoria'))
        self.assertEqual(resp.status_code, 302)


# ═══════════════════════════════════════════
# BACKUP
# ═══════════════════════════════════════════
class BackupViewsTest(GeSocialTestBase):

    def test_config_acesso_admin(self):
        self.login_as('admin')
        resp = self.client.get(reverse('backup_config'))
        self.assertEqual(resp.status_code, 200)

    def test_config_normal_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(reverse('backup_config'))
        self.assertEqual(resp.status_code, 302)

    def test_logs_acesso_admin(self):
        self.login_as('admin')
        resp = self.client.get(reverse('backup_logs'))
        self.assertEqual(resp.status_code, 200)

    def test_logs_normal_bloqueado(self):
        self.login_as('normal')
        resp = self.client.get(reverse('backup_logs'))
        self.assertEqual(resp.status_code, 302)


# ═══════════════════════════════════════════
# SOBRE
# ═══════════════════════════════════════════
class SobreViewTest(GeSocialTestBase):

    def test_sobre(self):
        self.login_as('normal')
        resp = self.client.get(reverse('sobre'))
        self.assertEqual(resp.status_code, 200)


# ═══════════════════════════════════════════
# RELATÓRIOS
# ═══════════════════════════════════════════
class RelatoriosViewTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()
        self.criar_pessoa(self.beneficio, cpf='529.982.247-25', status='ativo')

    def test_relatorio_beneficiarios_page(self):
        self.login_as('normal')
        resp = self.client.get(reverse('relatorio_beneficiarios'))
        self.assertEqual(resp.status_code, 200)

    def test_relatorio_financeiro_page(self):
        self.login_as('normal')
        resp = self.client.get(reverse('relatorio_financeiro'))
        self.assertEqual(resp.status_code, 200)
