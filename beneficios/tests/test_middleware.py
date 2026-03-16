"""
Testes para Middleware do GeSocial.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from .base import GeSocialTestBase

User = get_user_model()


class ForcarTrocaSenhaMiddlewareTest(GeSocialTestBase):

    def _criar_user_must_change(self, username):
        return User.objects.create_user(
            username=username, password='Temp@1234',
            must_change_password=True,
        )

    def test_redireciona_must_change_password(self):
        user = self._criar_user_must_change('obrigado')
        self.client.force_login(user)
        resp = self.client.get('/')
        self.assertRedirects(resp, reverse('trocar_senha'))

    def test_permite_trocar_senha_url(self):
        user = self._criar_user_must_change('obrigado2')
        self.client.force_login(user)
        resp = self.client.get(reverse('trocar_senha'))
        self.assertEqual(resp.status_code, 200)

    def test_permite_logout(self):
        user = self._criar_user_must_change('obrigado3')
        self.client.force_login(user)
        resp = self.client.post('/logout/')
        self.assertIn(resp.status_code, [200, 302])

    def test_permite_static(self):
        user = self._criar_user_must_change('obrigado4')
        self.client.force_login(user)
        resp = self.client.get('/static/css/style.css')
        self.assertNotEqual(resp.status_code, 302)

    def test_nao_redireciona_sem_flag(self):
        self.login_as('normal')
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)

    def test_bloqueia_perfil_com_flag(self):
        user = self._criar_user_must_change('obrigado5')
        self.client.force_login(user)
        resp = self.client.get(reverse('meu_perfil'))
        self.assertRedirects(resp, reverse('trocar_senha'))

    def test_bloqueia_dashboard_com_flag(self):
        user = self._criar_user_must_change('obrigado6')
        self.client.force_login(user)
        resp = self.client.get('/')
        self.assertRedirects(resp, reverse('trocar_senha'))

    def test_apos_trocar_senha_libera_acesso(self):
        user = self._criar_user_must_change('troca_ok')
        self.client.force_login(user)
        self.client.post(reverse('trocar_senha'), {
            'old_password': 'Temp@1234',
            'new_password1': 'NovaSenh@99',
            'new_password2': 'NovaSenh@99',
        })
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)