"""
Testes para todos os Forms do GeSocial.
"""
from decimal import Decimal
from io import BytesIO

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from beneficios.forms import (
    PessoaForm, DocumentoForm,
    UsuarioCreateForm, UsuarioEditForm, MeuPerfilForm,
    validar_pdf_real,
)
from beneficios.models import Beneficio, Pessoa
from .base import GeSocialTestBase

User = get_user_model()


# ═══════════════════════════════════════════
# VALIDAR PDF REAL
# ═══════════════════════════════════════════
class ValidarPdfRealTest(TestCase):

    def test_arquivo_pdf_valido(self):
        arquivo = BytesIO(b'%PDF-1.4 test content')
        self.assertTrue(validar_pdf_real(arquivo))

    def test_arquivo_nao_pdf(self):
        arquivo = BytesIO(b'PK\x03\x04 zip content')
        self.assertFalse(validar_pdf_real(arquivo))

    def test_arquivo_none(self):
        self.assertTrue(validar_pdf_real(None))

    def test_arquivo_vazio(self):
        arquivo = BytesIO(b'')
        self.assertFalse(validar_pdf_real(arquivo))

    def test_arquivo_texto_disfarçado(self):
        arquivo = BytesIO(b'Hello World this is not a PDF')
        self.assertFalse(validar_pdf_real(arquivo))


# ═══════════════════════════════════════════
# PESSOA FORM
# ═══════════════════════════════════════════
class PessoaFormTest(GeSocialTestBase):

    def setUp(self):
        super().setUp()
        self.beneficio = self.criar_beneficio()

    def _form_data(self, **overrides):
        data = {
            'nome_completo': 'João da Silva',
            'cpf': '529.982.247-25',
            'sexo': 'M',
            'data_nascimento': '1990-01-15',
            'celular': '83999887766',
            'endereco': 'Rua Teste, 100',
            'bairro': 'Centro',
            'cidade': 'Pocinhos/PB',
            'valor_beneficio': '150.00',
            'beneficio': self.beneficio.pk,
            'status': 'ativo',
        }
        data.update(overrides)
        return data

    def test_form_valido(self):
        form = PessoaForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_cpf_invalido_digitos(self):
        form = PessoaForm(data=self._form_data(cpf='111.111.111-11'))
        self.assertFalse(form.is_valid())
        self.assertIn('cpf', form.errors)

    def test_cpf_invalido_curto(self):
        form = PessoaForm(data=self._form_data(cpf='123'))
        self.assertFalse(form.is_valid())
        self.assertIn('cpf', form.errors)

    def test_cpf_invalido_verificador(self):
        form = PessoaForm(data=self._form_data(cpf='529.982.247-99'))
        self.assertFalse(form.is_valid())
        self.assertIn('cpf', form.errors)

    def test_cpf_formatado_automaticamente(self):
        form = PessoaForm(data=self._form_data(cpf='52998224725'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['cpf'], '529.982.247-25')

    def test_cpf_duplicado_bloqueado_se_ativo(self):
        self.criar_pessoa(self.beneficio, cpf='529.982.247-25', status='ativo')
        form = PessoaForm(data=self._form_data(cpf='529.982.247-25'))
        self.assertFalse(form.is_valid())
        self.assertIn('cpf', form.errors)

    def test_cpf_duplicado_permitido_se_desligado(self):
        self.criar_pessoa(self.beneficio, cpf='529.982.247-25', status='desligado')
        form = PessoaForm(data=self._form_data(cpf='529.982.247-25'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_cpf_duplicado_bloqueado_se_em_espera(self):
        self.criar_pessoa(self.beneficio, cpf='529.982.247-25', status='em_espera')
        form = PessoaForm(data=self._form_data(cpf='529.982.247-25'))
        self.assertFalse(form.is_valid())

    def test_status_cadastro_sem_desligado(self):
        form = PessoaForm()
        choices = [c[0] for c in form.fields['status'].choices]
        self.assertIn('ativo', choices)
        self.assertIn('em_espera', choices)
        self.assertNotIn('desligado', choices)

    def test_status_edicao_com_desligado(self):
        p = self.criar_pessoa(self.beneficio)
        form = PessoaForm(instance=p)
        choices = [c[0] for c in form.fields['status'].choices]
        self.assertIn('desligado', choices)

    def test_beneficio_disabled_na_edicao(self):
        p = self.criar_pessoa(self.beneficio)
        form = PessoaForm(instance=p)
        self.assertTrue(form.fields['beneficio'].disabled)

    def test_beneficio_habilitado_no_cadastro(self):
        form = PessoaForm()
        self.assertFalse(form.fields['beneficio'].disabled)

    def test_queryset_apenas_beneficios_ativos(self):
        self.criar_beneficio(nome='Inativo', ativo=False)
        form = PessoaForm()
        qs = form.fields['beneficio'].queryset
        self.assertFalse(qs.filter(ativo=False).exists())

    def test_celular_limpa_formatacao(self):
        form = PessoaForm(data=self._form_data(celular='(83) 99988-7766'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['celular'], '83999887766')

    def test_valor_beneficio_zero_aceito(self):
        form = PessoaForm(data=self._form_data(valor_beneficio='0'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_arquivo_pdf_valido(self):
        pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        form = PessoaForm(data=self._form_data(), files={'arquivo': pdf})
        self.assertTrue(form.is_valid(), form.errors)

    def test_arquivo_nao_pdf_rejeitado(self):
        fake = SimpleUploadedFile('doc.pdf', b'PK\x03\x04 not pdf', content_type='application/pdf')
        form = PessoaForm(data=self._form_data(), files={'arquivo': fake})
        self.assertFalse(form.is_valid())
        self.assertIn('arquivo', form.errors)

    def test_arquivo_extensao_errada(self):
        txt = SimpleUploadedFile('doc.txt', b'%PDF-1.4 fake', content_type='text/plain')
        form = PessoaForm(data=self._form_data(), files={'arquivo': txt})
        self.assertFalse(form.is_valid())
        self.assertIn('arquivo', form.errors)

    def test_arquivo_muito_grande(self):
        big = SimpleUploadedFile('big.pdf', b'%PDF-' + b'x' * (11 * 1024 * 1024), content_type='application/pdf')
        form = PessoaForm(data=self._form_data(), files={'arquivo': big})
        self.assertFalse(form.is_valid())
        self.assertIn('arquivo', form.errors)


# ═══════════════════════════════════════════
# DOCUMENTO FORM
# ═══════════════════════════════════════════
class DocumentoFormTest(GeSocialTestBase):

    def test_form_valido(self):
        pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 content', content_type='application/pdf')
        form = DocumentoForm(files={'arquivo': pdf})
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejeita_arquivo_nao_pdf(self):
        fake = SimpleUploadedFile('evil.pdf', b'MZ\x90\x00', content_type='application/pdf')
        form = DocumentoForm(files={'arquivo': fake})
        self.assertFalse(form.is_valid())

    def test_rejeita_extensao_errada(self):
        img = SimpleUploadedFile('foto.jpg', b'%PDF-1.4', content_type='image/jpeg')
        form = DocumentoForm(files={'arquivo': img})
        self.assertFalse(form.is_valid())

    def test_rejeita_maior_10mb(self):
        big = SimpleUploadedFile('big.pdf', b'%PDF-' + b'0' * (11 * 1024 * 1024))
        form = DocumentoForm(files={'arquivo': big})
        self.assertFalse(form.is_valid())


# ═══════════════════════════════════════════
# USUARIO CREATE FORM
# ═══════════════════════════════════════════
class UsuarioCreateFormTest(GeSocialTestBase):

    def _form_data(self, **overrides):
        data = {
            'username': 'novo_user',
            'password': 'Teste@123',
            'nome_completo': 'Novo Usuário',
            'email': 'novo@test.com',
            'cargo': 'Assistente',
            'is_staff': False,
        }
        data.update(overrides)
        return data

    def test_form_valido(self):
        form = UsuarioCreateForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_save_set_password(self):
        form = UsuarioCreateForm(data=self._form_data())
        form.is_valid()
        user = form.save()
        self.assertTrue(user.check_password('Teste@123'))
        self.assertTrue(user.must_change_password)
        self.assertFalse(user.is_superuser)

    def test_username_com_espaco_rejeitado(self):
        form = UsuarioCreateForm(data=self._form_data(username='user name'))
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_username_duplicado_rejeitado(self):
        form1 = UsuarioCreateForm(data=self._form_data())
        form1.is_valid()
        form1.save()
        form2 = UsuarioCreateForm(data=self._form_data())
        self.assertFalse(form2.is_valid())

    def test_is_staff_admin(self):
        form = UsuarioCreateForm(data=self._form_data(is_staff=True))
        form.is_valid()
        user = form.save()
        self.assertTrue(user.is_staff)

    def test_superuser_sempre_false(self):
        form = UsuarioCreateForm(data=self._form_data(is_staff=True))
        form.is_valid()
        user = form.save()
        self.assertFalse(user.is_superuser)


# ═══════════════════════════════════════════
# USUARIO EDIT FORM
# ═══════════════════════════════════════════
class UsuarioEditFormTest(GeSocialTestBase):

    def test_username_readonly(self):
        form = UsuarioEditForm(
            data={'username': 'hackeado', 'nome_completo': 'X', 'email': '', 'cargo': '', 'is_staff': False},
            instance=self.normal_user,
        )
        form.is_valid()
        self.assertEqual(form.cleaned_data['username'], 'usuario_test')

    def test_resetar_senha_sem_senha_erro(self):
        form = UsuarioEditForm(
            data={
                'username': 'usuario_test', 'nome_completo': '', 'email': '',
                'cargo': '', 'is_staff': False, 'resetar_senha': True, 'password': '',
            },
            instance=self.normal_user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_resetar_senha_com_senha(self):
        form = UsuarioEditForm(
            data={
                'username': 'usuario_test', 'nome_completo': '', 'email': '',
                'cargo': '', 'is_staff': False,
                'resetar_senha': True, 'password': 'Nova@1234',
            },
            instance=self.normal_user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.check_password('Nova@1234'))
        self.assertTrue(user.must_change_password)

    def test_sem_resetar_senha_mantem_atual(self):
        form = UsuarioEditForm(
            data={
                'username': 'usuario_test', 'nome_completo': 'Editado',
                'email': 'e@e.com', 'cargo': 'Cargo', 'is_staff': False,
            },
            instance=self.normal_user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.check_password('User@1234'))


# ═══════════════════════════════════════════
# MEU PERFIL FORM
# ═══════════════════════════════════════════
class MeuPerfilFormTest(GeSocialTestBase):

    def test_campos_limitados(self):
        form = MeuPerfilForm(instance=self.normal_user)
        self.assertEqual(set(form.fields.keys()), {'email', 'cargo'})

    def test_form_valido(self):
        form = MeuPerfilForm(
            data={'email': 'teste@teste.com', 'cargo': 'Assistente Social'},
            instance=self.normal_user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_email_vazio_aceito(self):
        form = MeuPerfilForm(
            data={'email': '', 'cargo': ''},
            instance=self.normal_user,
        )
        self.assertTrue(form.is_valid(), form.errors)
