from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Autenticação
    path('login/', auth_views.LoginView.as_view(template_name='beneficios/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Pessoas
    path('pessoa/nova/', views.pessoa_create, name='pessoa_create'),
    path('pessoa/<int:pk>/editar/', views.pessoa_edit, name='pessoa_edit'),
    path('pessoa/<int:pk>/ativar/', views.pessoa_ativar, name='pessoa_ativar'),
    path('pessoa/<int:pk>/espera/', views.pessoa_espera, name='pessoa_espera'),
    path('pessoa/<int:pk>/desligar/', views.pessoa_desligar, name='pessoa_desligar'),
    path('pessoa/<int:pk>/documento/', views.pessoa_documento, name='pessoa_documento'),
    path('documento/<int:pk>/visualizar/', views.documento_protegido, name='documento_protegido'),
 
    # Documentos das pessoas
    path('pessoa/<int:pk>/recibo/', views.gerar_recibo, name='gerar_recibo'),
    path('pessoa/<int:pk>/documentos/', views.gerar_documentos, name='gerar_documentos'),
    path('pessoa/<int:pk>/memorando/', views.gerar_memorando, name='gerar_memorando'),

    # Gerenciamento de Usuários
    path('usuarios/', views.usuarios_list, name='usuarios_list'),
    path('usuarios/novo/', views.usuario_create, name='usuario_create'),
    path('usuarios/<int:pk>/toggle-active/', views.usuario_toggle_active, name='usuario_toggle_active'),
    path('usuarios/<int:pk>/editar/', views.usuario_edit, name='usuario_edit'),

    # Perfil
    path('perfil/', views.meu_perfil, name='meu_perfil'),
    
    # Listagem por beneficio
    path('beneficio/<int:beneficio_id>/pessoas/', views.pessoas_por_beneficio, name='pessoas_por_beneficio'),
    
    # Gerenciamento de Benefícios
    path('beneficios/', views.beneficios_list, name='beneficios_list'),
    path('beneficios/novo/', views.beneficio_create, name='beneficio_create'),
    path('beneficios/<int:pk>/editar/', views.beneficio_edit_form, name='beneficio_edit_form'),
    path('beneficios/<int:pk>/toggle/', views.beneficio_toggle, name='beneficio_toggle'),

    # Ações em Massa
    path('beneficio/<int:beneficio_id>/memorando-massa/', views.gerar_memorando_massa, name='gerar_memorando_massa'),
    path('beneficio/<int:beneficio_id>/recibos-massa/', views.gerar_recibos_massa, name='gerar_recibos_massa'),
    path('beneficio/<int:beneficio_id>/documentos-massa/', views.gerar_documentos_massa, name='gerar_documentos_massa'),
    path('beneficio/<int:beneficio_id>/remessa-banco/', views.gerar_remessa_banco, name='gerar_remessa_banco'),

    # Sobre
    path('sobre/', views.sobre, name='sobre'),

    # Histórico de Memorandos
    path('memorandos/', views.memorandos_lista, name='memorandos_lista'),
    path('memorandos/<int:pk>/segunda-via/', views.memorando_segunda_via, name='memorando_segunda_via'),

    # Relatórios
    path('relatorios/beneficiarios/', views.relatorio_beneficiarios, name='relatorio_beneficiarios'),
    path('relatorios/beneficiarios/gerar/', views.gerar_relatorio_beneficiarios, name='gerar_relatorio_beneficiarios'),
    path('relatorios/financeiro/', views.relatorio_financeiro, name='relatorio_financeiro'),
    path('relatorios/financeiro/gerar/', views.gerar_relatorio_financeiro, name='gerar_relatorio_financeiro'),

    # Configurações Gerais
    path('configuracoes/', views.configuracoes_gerais, name='configuracoes_gerais'),

    # Auditoria
    path('auditoria/', views.auditoria, name='auditoria'),

    # Senha
    path('trocar-senha/', views.trocar_senha, name='trocar_senha'),

    # Backup
    path('backup/config/', views.backup_config, name='backup_config'),
    path('backup/logs/', views.backup_logs, name='backup_logs'),


]
