from django.db import models
from django.contrib.auth.models import AbstractUser
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

class User(AbstractUser):
    """Usuário customizado para futuras expansões"""
    must_change_password = models.BooleanField(default=True, verbose_name='Deve trocar senha')

class Beneficio(models.Model):
    """Tipos de benefícios: Auxílio Transporte e Renda Solidária"""
    ICONE_CHOICES = [
        ('bi-bus-front', 'Ônibus'),
        ('bi-cash-coin', 'Moeda'),
        ('bi-calendar-event', 'Único'),
        ('bi-hourglass-split', 'Temporário'),
        ('bi-cart', 'Mercado'),
        ('bi-heart-pulse', 'Saúde'),
    ]
    
    nome = models.CharField(max_length=100, unique=True)
    conta_pagadora = models.CharField(max_length=200, blank=True)
    icone = models.CharField(max_length=30, choices=ICONE_CHOICES, default='bi-wallet2')
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Benefício'
        verbose_name_plural = 'Benefícios'
        ordering = ['nome']
    
    def __str__(self):
        return self.nome

class Pessoa(models.Model):
    """Cadastro de pessoas beneficiárias"""
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('O', 'Outro'),
    ]

    CIDADE_CHOICES = [
        ('Pocinhos/PB', 'Pocinhos/PB'),
    ]
    
    nome_completo = models.CharField(max_length=200)
    #cpf = models.CharField(max_length=14, unique=True)
    cpf=EncryptedCharField(max_length=14, unique=True, verbose_name='CPF')  # CRIPTOGRAFADO
    cpf_ultimos_4 = models.CharField(max_length=4, db_index=True, blank=True, default='')
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    data_nascimento = models.DateField(null=True, blank=True)
    celular = models.CharField(max_length=15, blank=True)
    endereco = models.TextField()
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=50, choices=CIDADE_CHOICES)
    valor_beneficio = models.DecimalField(max_digits=10, decimal_places=2)
    beneficio = models.ForeignKey(Beneficio, on_delete=models.PROTECT)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Pessoa'
        verbose_name_plural = 'Pessoas'
        ordering = ['nome_completo']
        
    def save(self, *args, **kwargs):
        # Extrai últimos 4 dígitos do CPF ao salvar
        if self.cpf:
            cpf_numeros = ''.join(filter(str.isdigit, self.cpf))
            if len(cpf_numeros) >= 4:
                self.cpf_ultimos_4 = cpf_numeros[-4:]
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nome_completo} - {self.cpf}"

class Documento(models.Model):
    """Documentos PDF das pessoas"""
    pessoa = models.OneToOneField(Pessoa, on_delete=models.CASCADE, related_name='documento')
    arquivo = models.FileField(upload_to='documentos/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
    
    def __str__(self):
        return f"Documento de {self.pessoa.nome_completo}"

class PermissoesGerais(models.Model):
    class Meta:
        # Isso evita criar uma tabela desnecessária no banco
        managed = False
        
        # Aqui criamos as permissões
        permissions = [
            ("pode_ver_configuracoes", "Pode acessar as configurações do sistema"),
            ("pode_fazer_backup", "Pode realizar e baixar backups"),
        ]

class Memorando(models.Model):
    """Registro de memorandos gerados"""
    numero = models.CharField(max_length=12, unique=True)  # 00001/2026
    ano = models.PositiveIntegerField()
    sequencia = models.PositiveIntegerField()
    beneficio = models.ForeignKey(Beneficio, on_delete=models.PROTECT)
    conta_pagadora = models.CharField(max_length=200, blank=True)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    quantidade_pessoas = models.PositiveIntegerField()
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    # Salva o secretário, cargo e demais informações das configurações do sistema para 2 via do memorando
    secretaria_nome = models.CharField(max_length=100, blank=True)
    secretaria_cargo = models.CharField(max_length=100, blank=True)
    financas_nome = models.CharField(max_length=100, blank=True)
    financas_cargo = models.CharField(max_length=100, blank=True)
    email_institucional = models.EmailField(blank=True)
    endereco = models.CharField(max_length=200, blank=True)
    cep = models.CharField(max_length=10, blank=True)
    
    class Meta:
        verbose_name = 'Memorando'
        verbose_name_plural = 'Memorandos'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['ano', 'sequencia'], name='unique_sequencia_ano')
        ]
    
    def __str__(self):
        return f"Memorando {self.numero} - {self.beneficio.nome}"


class MemorandoPessoa(models.Model):
    """Snapshot dos dados das pessoas no momento da geração do memorando"""
    memorando = models.ForeignKey(Memorando, on_delete=models.CASCADE, related_name='pessoas')
    pessoa = models.ForeignKey(Pessoa, on_delete=models.SET_NULL, null=True)
    # Snapshot dos dados (imutáveis)
    nome_completo = models.CharField(max_length=200)
    valor_beneficio = models.DecimalField(max_digits=10, decimal_places=2)
    ordem = models.PositiveIntegerField()
    
    class Meta:
        verbose_name = 'Pessoa do Memorando'
        verbose_name_plural = 'Pessoas do Memorando'
        ordering = ['ordem']
    
    def __str__(self):
        return f"{self.nome_completo} - {self.memorando.numero}"

class ConfiguracaoGeral(models.Model):
    """Configurações gerais do sistema (singleton)"""
    
    # Secretaria de Assistência Social (quem assina)
    secretaria_nome = models.CharField(
        max_length=100, 
        default='Zélia Maria Matias e Silva',
        verbose_name='Nome do(a) Secretário(a)'
    )
    secretaria_cargo = models.CharField(
        max_length=100, 
        default='Secretária Adjunta de Assistência Social',
        verbose_name='Cargo'
    )
    
    # Secretaria de Finanças (destinatário)
    financas_nome = models.CharField(
        max_length=100, 
        default='Carlos Roberto Alves Filho',
        verbose_name='Nome do Secretário de Finanças'
    )
    financas_cargo = models.CharField(
        max_length=100, 
        default='Secretário de Finanças',
        verbose_name='Cargo'
    )
    
    # Rodapé
    email_institucional = models.EmailField(
        default='assistenciasocialpocinhos@gmail.com',
        verbose_name='E-mail institucional'
    )
    endereco = models.CharField(
        max_length=200, 
        default='Rua Pç. Pres. Getúlio Vargas, 57, Centro',
        verbose_name='Endereço'
    )
    cep = models.CharField(
        max_length=10, 
        default='58150-000',
        verbose_name='CEP'
    )
    
    class Meta:
        verbose_name = 'Configuração Geral'
        verbose_name_plural = 'Configurações Gerais'
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config
    
    def __str__(self):
        return "Configurações Gerais"