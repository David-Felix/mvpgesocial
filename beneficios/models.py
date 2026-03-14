from django.db import models
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField
from django.contrib.auth.models import AbstractUser
from encrypted_model_fields.fields import EncryptedCharField, EncryptedTextField

class User(AbstractUser):
    """Usuário customizado para futuras expansões"""
    must_change_password = models.BooleanField(default=True, verbose_name='Deve trocar senha')
    history = AuditlogHistoryField()

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
    descricao = models.CharField(max_length=200, blank=True, default='', verbose_name='Descrição')
    conta_pagadora = models.CharField(max_length=200, blank=True)
    icone = models.CharField(max_length=30, choices=ICONE_CHOICES, default='bi-wallet2')
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()
    
    class Meta:
        verbose_name = 'Benefício'
        verbose_name_plural = 'Benefícios'
        ordering = ['nome']
    
    @property
    def nome_exibicao(self):
        return self.descricao if self.descricao else self.nome

    def __str__(self):
        return self.nome_exibicao

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

    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('em_espera', 'Em Espera'),
        ('desligado', 'Desligado'),
    ]
    
    nome_completo = models.CharField(max_length=200)
    cpf = EncryptedCharField(max_length=14, verbose_name='CPF')
    cpf_ultimos_4 = models.CharField(max_length=4, db_index=True, blank=True, default='')
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    data_nascimento = models.DateField(null=True, blank=True)
    celular = models.CharField(max_length=15, blank=True)
    endereco = models.TextField()
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=50, choices=CIDADE_CHOICES)
    valor_beneficio = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
    beneficio = models.ForeignKey(Beneficio, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = AuditlogHistoryField()
    
    class Meta:
        verbose_name = 'Pessoa'
        verbose_name_plural = 'Pessoas'
        ordering = ['nome_completo']
        
    def save(self, *args, **kwargs):
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
    history = AuditlogHistoryField()
    
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
    history = AuditlogHistoryField()
    
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
    history = AuditlogHistoryField()

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
    history = AuditlogHistoryField()
    
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

class HistoricoStatus(models.Model):
    """Histórico de mudanças de status das pessoas"""
    STATUS_CHOICES = Pessoa.STATUS_CHOICES + [('cadastrado', 'Cadastrado')]
    
    pessoa = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='historico_status')
    status_anterior = models.CharField(max_length=20, choices=STATUS_CHOICES, null=True, blank=True)
    status_novo = models.CharField(max_length=20, choices=Pessoa.STATUS_CHOICES)
    data = models.DateTimeField()
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Histórico de Status'
        verbose_name_plural = 'Históricos de Status'
        ordering = ['-data']
    
    def __str__(self):
        return f"{self.pessoa.nome_completo}: {self.status_anterior} → {self.status_novo} em {self.data}"

class LogAcao(models.Model):
    """Log de ações de geração de documentos e operações em massa"""
    TIPO_CHOICES = [
        ('memorando_individual', 'Memorando Individual'),
        ('memorando_massa', 'Memorando em Massa'),
        ('recibo_individual', 'Recibo Individual'),
        ('recibos_massa', 'Recibos em Massa'),
        ('documentos_massa', 'Documentos em Massa'),
        ('remessa_banco', 'Arquivo Remessa'),
        ('relatorio_beneficiarios_pdf', 'Relatório Beneficiários PDF'),
        ('relatorio_beneficiarios_xlsx', 'Relatório Beneficiários Excel'),
        ('relatorio_financeiro_pdf', 'Relatório Financeiro PDF'),
        ('relatorio_financeiro_xlsx', 'Relatório Financeiro Excel'),
        ('status_ativar', 'Ativou Pessoa'),
        ('status_espera', 'Moveu para Espera'),
        ('status_desligar', 'Desligou Pessoa'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    descricao = models.TextField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Log de Ação'
        verbose_name_plural = 'Logs de Ações'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.usuario} - {self.get_tipo_display()} - {self.created_at}"


class BackupConfig(models.Model):
    """Configurações de backup do sistema (singleton)"""
    FREQUENCIA_CHOICES = [
        ('diario', 'Diário'),
        ('semanal', 'Semanal'),
    ]
    
    # Google Drive
    rclone_nome_remote = models.CharField(max_length=100, default='DRIVE', verbose_name='Nome do remote')
    rclone_pasta = models.CharField(max_length=200, default='BackupGESOCIAL', verbose_name='Pasta de destino')
    
    # Backup Banco de Dados
    agendamento_db_ativo = models.BooleanField(default=False, verbose_name='Agendar backup do banco')
    horario_db = models.TimeField(default='03:00', verbose_name='Horário (Banco)')
    frequencia_db = models.CharField(max_length=10, choices=FREQUENCIA_CHOICES, default='diario', verbose_name='Frequência (Banco)')
    versoes_nuvem_db = models.PositiveIntegerField(default=5, verbose_name='Versões nuvem (Banco)')
    versoes_local_db = models.PositiveIntegerField(default=5, verbose_name='Versões locais (Banco)')
    
    # Backup Documentos
    agendamento_doc_ativo = models.BooleanField(default=False, verbose_name='Agendar backup de documentos')
    horario_doc = models.TimeField(default='04:00', verbose_name='Horário (Documentos)')
    frequencia_doc = models.CharField(max_length=10, choices=FREQUENCIA_CHOICES, default='semanal', verbose_name='Frequência (Documentos)')
    versoes_nuvem_doc = models.PositiveIntegerField(default=3, verbose_name='Versões nuvem (Documentos)')
    versoes_local_doc = models.PositiveIntegerField(default=3, verbose_name='Versões locais (Documentos)')
    
    class Meta:
        verbose_name = 'Configuração de Backup'
        verbose_name_plural = 'Configurações de Backup'
    
    @property
    def rclone_destino(self):
        nome = self.rclone_nome_remote.strip().rstrip(':')
        pasta = self.rclone_pasta.strip().strip('/')
        return f'{nome}:{pasta}'
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config
    
    def __str__(self):
        return 'Configuração de Backup'


class BackupHistorico(models.Model):
    """Registro de cada execução de backup"""
    TIPO_CHOICES = [
        ('manual', 'Manual'),
        ('automatico', 'Automático'),
    ]
    STATUS_CHOICES = [
        ('executando', 'Executando'),
        ('sucesso', 'Sucesso'),
        ('erro', 'Erro'),
    ]
    TIPO_BACKUP_CHOICES = [
        ('banco', 'Banco de Dados'),
        ('documentos', 'Documentos'),
    ]
    
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
    tipo_backup = models.CharField(max_length=15, choices=TIPO_BACKUP_CHOICES, default='banco')
    tamanho_bytes = models.BigIntegerField(null=True, blank=True)
    itens = models.CharField(max_length=100, verbose_name='Itens incluídos')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='executando')
    arquivo_nome = models.CharField(max_length=200, blank=True, default='')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Histórico de Backup'
        verbose_name_plural = 'Históricos de Backup'
        ordering = ['-data_inicio']
    
    def __str__(self):
        return f'{self.arquivo_nome} - {self.get_status_display()}'
    
    @property
    def tamanho_formatado(self):
        if not self.tamanho_bytes:
            return '-'
        if self.tamanho_bytes < 1024:
            return f'{self.tamanho_bytes} B'
        elif self.tamanho_bytes < 1024 * 1024:
            return f'{self.tamanho_bytes / 1024:.1f} KB'
        elif self.tamanho_bytes < 1024 * 1024 * 1024:
            return f'{self.tamanho_bytes / (1024 * 1024):.1f} MB'
        else:
            return f'{self.tamanho_bytes / (1024 * 1024 * 1024):.2f} GB'

class BackupLog(models.Model):
    """Log detalhado de cada etapa do backup"""
    ETAPA_CHOICES = [
        ('inicio', 'Início'),
        ('dump_banco', 'Dump do Banco'),
        ('compactar_docs', 'Compactar Documentos'),
        ('compactar_configs', 'Compactar Configurações'),
        ('comprimir', 'Comprimir (zstd)'),
        ('criptografar', 'Criptografar (GPG)'),
        ('copiar_local', 'Copiar Local'),
        ('enviar', 'Enviar Google Drive'),
        ('retencao_nuvem', 'Retenção Nuvem'),
        ('retencao_local', 'Retenção Local'),
        ('limpar', 'Limpeza Temporários'),
        ('fim', 'Finalização'),
    ]
    STATUS_CHOICES = [
        ('executando', 'Executando'),
        ('sucesso', 'Sucesso'),
        ('erro', 'Erro'),
    ]
    
    backup = models.ForeignKey(BackupHistorico, on_delete=models.CASCADE, related_name='logs')
    etapa = models.CharField(max_length=30, choices=ETAPA_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    mensagem = models.TextField(blank=True, default='')
    data = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Log de Backup'
        verbose_name_plural = 'Logs de Backup'
        ordering = ['data']
    
    def __str__(self):
        return f'{self.get_etapa_display()} - {self.get_status_display()}'
        
# Registrar models no auditlog
auditlog.register(User)
auditlog.register(Beneficio)
auditlog.register(Pessoa)
auditlog.register(Documento)
auditlog.register(ConfiguracaoGeral)
auditlog.register(Memorando)
auditlog.register(ConfiguracaoGeral)