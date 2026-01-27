from django import forms
from .models import Pessoa, Documento, Beneficio

class PessoaForm(forms.ModelForm):
    arquivo = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'application/pdf'}),
        #label='Documento PDF',
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
    
    class Meta:
        model = Pessoa
        fields = ['nome_completo', 'cpf', 'sexo', 'data_nascimento', 'celular', 
                  'endereco', 'bairro', 'cidade', 'valor_beneficio', 'beneficio']
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
            'valor_beneficio': 'Valor do Benefício (R$)',
            'beneficio': 'Tipo de Benefício',
        }
    
    def clean_arquivo(self):
        arquivo = self.cleaned_data.get('arquivo')
        if arquivo:
            if not arquivo.name.lower().endswith('.pdf'):
                raise forms.ValidationError('Apenas arquivos PDF são permitidos.')
            if arquivo.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Arquivo muito grande. Tamanho máximo: 10MB.')
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
                raise forms.ValidationError('CPF já cadastrado no sistema!')
        
        return cpf_formatado
    
    def clean_nome_completo(self):
        nome = self.cleaned_data.get('nome_completo')
        return nome.title() if nome else nome
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
            if not arquivo.name.endswith('.pdf'):
                raise forms.ValidationError('Apenas arquivos PDF são permitidos')
            
            # Limite de 10MB
            if arquivo.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Arquivo muito grande. Tamanho máximo: 10MB')
        
        return arquivo
