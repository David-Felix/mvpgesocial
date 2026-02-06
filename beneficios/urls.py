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
    path('pessoa/<int:pk>/toggle/', views.pessoa_toggle, name='pessoa_toggle'),
    path('pessoa/<int:pk>/documento/', views.pessoa_documento, name='pessoa_documento'),
    path('documento/<int:pk>/visualizar/', views.documento_protegido, name='documento_protegido'),
 
    # Documentos das pessoas
    path('pessoa/<int:pk>/recibo/', views.gerar_recibo, name='gerar_recibo'),
    path('pessoa/<int:pk>/documentos/', views.gerar_documentos, name='gerar_documentos'),
    path('pessoa/<int:pk>/memorando/', views.gerar_memorando, name='gerar_memorando'),

    # Gerenciamento de Usuários
    path('usuarios/', views.usuarios_list, name='usuarios_list'),
    path('usuarios/novo/', views.usuario_create, name='usuario_create'),
    path('usuarios/<int:pk>/toggle-staff/', views.usuario_toggle_staff, name='usuario_toggle_staff'),
    path('usuarios/<int:pk>/toggle-active/', views.usuario_toggle_active, name='usuario_toggle_active'),
    
    # Listagem por beneficio
    path('beneficio/<int:beneficio_id>/pessoas/', views.pessoas_por_beneficio, name='pessoas_por_beneficio'),
    
    # Gerenciamento de Benefícios
    path('beneficios/', views.beneficios_list, name='beneficios_list'),
    path('beneficios/novo/', views.beneficio_create, name='beneficio_create'),
    path('beneficios/<int:pk>/editar/', views.beneficio_edit_form, name='beneficio_edit_form'),
    path('beneficios/<int:pk>/toggle/', views.beneficio_toggle, name='beneficio_toggle'),
    
    # Beneficios
    path('beneficio/<int:pk>/editar/', views.beneficio_edit, name='beneficio_edit'),

    # Ações em Massa
    path('beneficio/<int:beneficio_id>/memorando-massa/', views.gerar_memorando_massa, name='gerar_memorando_massa'),
    path('beneficio/<int:beneficio_id>/recibos-massa/', views.gerar_recibos_massa, name='gerar_recibos_massa'),
    path('beneficio/<int:beneficio_id>/documentos-massa/', views.gerar_documentos_massa, name='gerar_documentos_massa'),

    # Sobre
    path('sobre/', views.sobre, name='sobre'),

    # Histórico de Memorandos
    path('memorandos/', views.memorandos_lista, name='memorandos_lista'),
    path('memorandos/<int:pk>/segunda-via/', views.memorando_segunda_via, name='memorando_segunda_via'),

]
