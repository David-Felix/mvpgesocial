from django import forms
from .models import Pessoa, Documento, Beneficio, User
#from django.contrib.auth.password_validation import validate_password (caso decida verificar força de senha na criação do user)

def validar_pdf_real(arquivo):
    """Valida se o arquivo é realmente um PDF (magic bytes)"""
    if arquivo:
        # Lê os primeiros bytes
        arquivo.seek(0)
        header = arquivo.read(5)
        arquivo.seek(0)  # Volta ao início para não quebrar o upload
        
        # PDF sempre começa com %PDF-
        if header != b'%PDF-':
            return False
    return True

class PessoaForm(forms.ModelForm):
    arquivo = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'application/pdf'}),
        help_text='Tamanho máximo: 10MB (.pdf)'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.data_nascimento:
            self.initial['data_nascimento'] = self.instance.data_nascimento.strftime('%Y-%m-%d')
        
        self.fields['beneficio'].queryset = Beneficio.objects.filter(ativo=True)
        
        if self.instance.pk:
            self.fields['beneficio'].disabled = True
            self.fields['beneficio'].help_text = 'Não é possível alterar o benefício após o cadastro'
            # Edição: 3 opções de status
            self.fields['status'].choices = Pessoa.STATUS_CHOICES
        else:
            # Cadastro: apenas Ativo e Em Espera
            self.fields['status'].choices = [
                ('ativo', 'Ativo'),
                ('em_espera', 'Em Espera'),
            ]
    
    class Meta:
        model = Pessoa
        fields = ['nome_completo', 'cpf', 'sexo', 'data_nascimento', 'celular', 
                  'endereco', 'bairro', 'cidade', 'valor_beneficio', 'beneficio', 'status']
        widgets = {
            'nome_completo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000.000.000-00'}),
            'sexo': forms.Select(attrs={'class': 'form-control'}),
            'data_nascimento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'celular': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(83) 99999-9999', 'pattern': '[0-9]*', 'inputmode': 'numeric'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Rua, número, complemento'}),
            'bairro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do bairro'}),
            'cidade': forms.Select(attrs={'class': 'form-control'}),
            'valor_beneficio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'beneficio': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'nome_completo': 'Nome Completo',
            'cpf': 'CPF',
            'sexo': 'Sexo',
            'data_nascimento': 'Data de Nascimento',
            'celular': 'Celular',
            'endereco': 'Endereço',
            'bairro': 'Bairro',
            'cidade': 'Cidade',
            'valor_beneficio': 'Valor a Receber',
            'beneficio': 'Tipo de Benefício',
            'status': 'Status',
        }
    
    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if arquivo:
            if not arquivo.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Apenas arquivos PDF são permitidos.')
            if arquivo.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Arquivo muito grande. Tamanho máximo: 10MB.')
            if not validar_pdf_real(arquivo):
                raise forms.ValidationError('Arquivo inválido. Envie um PDF verdadeiro.')
        return arquivo
    
    def clean_celular(self):
        celular = self.cleaned_data.get('celular')
        if celular:
            celular = ''.join(filter(str.isdigit, celular))
        return celular
    
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        cpf = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf) != 11:
            raise forms.ValidationError('CPF deve conter 11 dígitos')
        
        if cpf == cpf[0] * 11:
            raise forms.ValidationError('CPF inválido')
        
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito1 = 11 - (soma % 11)
        if digito1 > 9:
            digito1 = 0
        
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito2 = 11 - (soma % 11)
        if digito2 > 9:
            digito2 = 0
        
        if not (int(cpf[9]) == digito1 and int(cpf[10]) == digito2):
            raise forms.ValidationError('CPF inválido')
        
        cpf_formatado = f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'
        
        from .models import Pessoa
        qs = Pessoa.objects.all()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        for pessoa in qs:
            if pessoa.cpf == cpf_formatado:
                if pessoa.status != 'desligado':
                    raise forms.ValidationError(
                        'CPF já cadastrado em um benefício ativo ou em espera! '
                        'Só é permitido cadastrar o mesmo CPF se todos os registros anteriores estiverem desligados.'
                    )
        
        return cpf_formatado
        
class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ['arquivo']
        widgets = {
            'arquivo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'application/pdf'}),
        }
        labels = {
            'arquivo': 'Documento PDF (todos os documentos unidos)',
        }
    
    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        
        if arquivo:
            if not arquivo.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Apenas arquivos PDF são permitidos')
            
            if arquivo.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Arquivo muito grande. Tamanho máximo: 10MB')
            
            if not validar_pdf_real(arquivo):
                raise forms.ValidationError('Arquivo inválido. Envie um PDF verdadeiro.')
        
        return arquivo


class UsuarioCreateForm(forms.ModelForm):
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite uma senha forte'}),
    )

    class Meta:
        model = User
        fields = ['username', 'nome_completo', 'email', 'cargo', 'is_staff']
        labels = {
            'username': 'Usuário',
            'is_staff': 'Tornar Administrador',
        }
        help_texts = {
            'username': 'Usado para fazer login no sistema (sem espaços)',
        }
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': r'[a-zA-Z0-9._-]+',
                'title': 'Apenas letras, números, ponto, hífen e underscore. Sem espaços!',
            }),
            'nome_completo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo do usuário'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Assistente Social'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if ' ' in username:
            raise forms.ValidationError('Nome de usuário não pode conter espaços!')
        return username

    # caso decida verificar força de senha na criação do user
    #def clean_password(self):
        #password = self.cleaned_data['password']
        #validate_password(password)
        #return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_superuser = False
        user.must_change_password = True
        if commit:
            user.save()
        return user

class UsuarioEditForm(forms.ModelForm):
    resetar_senha = forms.BooleanField(
        required=False,
        label='Resetar senha',
        help_text='O usuário precisará trocar a senha no primeiro acesso.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_resetar_senha'}),
    )
    password = forms.CharField(
        required=False,
        label='Nova Senha',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Digite a nova senha temporária'}),
    )

    class Meta:
        model = User
        fields = ['username', 'nome_completo', 'email', 'cargo', 'is_staff']
        labels = {
            'username': 'Usuário',
            'is_staff': 'Administrador',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'nome_completo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome completo do usuário'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Assistente Social'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_username(self):
        return self.instance.username

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('resetar_senha'):
            password = cleaned_data.get('password')
            if not password:
                self.add_error('password', 'Informe a nova senha ao resetar.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('resetar_senha'):
            user.set_password(self.cleaned_data['password'])
            user.must_change_password = True
        if commit:
            user.save()
        return user

class MeuPerfilForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'cargo']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Assistente Social'}),
        }