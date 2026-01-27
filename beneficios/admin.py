from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Beneficio, Pessoa, Documento

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Permissões Customizadas', {'fields': ()}),
    )

@admin.register(Beneficio)
class BeneficioAdmin(admin.ModelAdmin):
    list_display = ['nome', 'conta_pagadora', 'ativo', 'created_at']
    list_filter = ['ativo']
    search_fields = ['nome', 'conta_pagadora']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informações do Benefício', {
            'fields': ('nome', 'conta_pagadora', 'ativo')
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ['ordem_alfabetica', 'nome_completo', 'cpf', 'status_display', 'valor_beneficio', 'acoes']
    list_filter = ['ativo', 'beneficio', 'sexo']
    search_fields = ['nome_completo', 'cpf']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Dados Pessoais', {
            'fields': ('nome_completo', 'cpf', 'sexo', 'data_nascimento', 'celular')
        }),
        ('Endereço', {
            'fields': ('endereco', 'bairro', 'cidade')
        }),
        ('Benefício', {
            'fields': ('beneficio', 'valor_beneficio', 'ativo')
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def ordem_alfabetica(self, obj):
        pessoas = Pessoa.objects.order_by('nome_completo')
        return list(pessoas).index(obj) + 1
    ordem_alfabetica.short_description = 'ID'
    
    def status_display(self, obj):
        return 'Ativo' if obj.ativo else 'Desativado'
    status_display.short_description = 'Status'
    
    def acoes(self, obj):
        from django.utils.html import format_html
        if obj.ativo:
            return format_html(
                '<a class="button" href="{}">Desativar</a>',
                f'/admin/beneficios/pessoa/{obj.id}/desativar/'
            )
        else:
            return format_html(
                '<a class="button" href="{}">Ativar</a>',
                f'/admin/beneficios/pessoa/{obj.id}/ativar/'
            )
    acoes.short_description = 'Ações'

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ['pessoa', 'uploaded_at']
    search_fields = ['pessoa__nome_completo']
    readonly_fields = ['uploaded_at']
