from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage
from .models import Pessoa, Beneficio, Documento, Memorando, MemorandoPessoa
from .services import registrar_memorando
from .utils import registrar_log_acao
from .forms import PessoaForm, DocumentoForm
from django.db.models import Q, F, Sum, Func, Value, CharField, Count
from django.contrib.staticfiles import finders
from django.views.decorators.clickjacking import xframe_options_sameorigin
from decimal import Decimal
import subprocess
import sys
import os

@login_required
def dashboard(request):
    """Dashboard com overview financeiro e benefícios ativos"""
    
    beneficios = Beneficio.objects.filter(ativo=True).order_by('id')
    
    stats_list = []
    total_mensal_geral = 0
    
    classes = ['benefit-card-azul', 'benefit-card-verde', 'benefit-card-turquesa', 'benefit-card-roxo']
    icones_padrao = ['bi-bus-front', 'bi-cash-coin', 'bi-wallet2', 'bi-piggy-bank']
    
    for idx, beneficio in enumerate(beneficios):
        stats = Pessoa.objects.filter(beneficio=beneficio).aggregate(
            total_pessoas=Count('id'),
            ativos=Count('id', filter=Q(status='ativo')),
            desativados=Count('id', filter=Q(status='desligado')),
            valor_mensal=Sum('valor_beneficio', filter=Q(status='ativo'))
        )
        
        valor_mensal = stats['valor_mensal'] or 0
        valor_mensal_formatado = f"{valor_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        icone = beneficio.icone if hasattr(beneficio, 'icone') and beneficio.icone else icones_padrao[idx % 4]
        
        stats_list.append({
            'id': beneficio.id,
            'nome': beneficio.nome_exibicao,
            'icone': icone,  
            'cor_classe': classes[idx % len(classes)],
            'total': stats['total_pessoas'],
            'ativos': stats['ativos'],
            'desativados': stats['desativados'],
            'valor_mensal': float(valor_mensal),
            'valor_mensal_formatado': valor_mensal_formatado,
        })
        
        total_mensal_geral += valor_mensal

    total_mensal_geral_formatado = f"{total_mensal_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Distribuição por faixa de valor
    pessoas_ativas = Pessoa.objects.filter(
        status='ativo',
        beneficio__ativo=True
    )
    
    distribuicao_valor = pessoas_ativas.aggregate(
        ate_100=Count('id', filter=Q(valor_beneficio__lte=100)),
        de_101_150=Count('id', filter=Q(valor_beneficio__gt=100, valor_beneficio__lte=150)),
        de_151_200=Count('id', filter=Q(valor_beneficio__gt=150, valor_beneficio__lte=200)),
        de_201_250=Count('id', filter=Q(valor_beneficio__gt=200, valor_beneficio__lte=250)),
        de_251_300=Count('id', filter=Q(valor_beneficio__gt=250, valor_beneficio__lte=300)),
        acima_300=Count('id', filter=Q(valor_beneficio__gt=300))
    )
    
    todas_beneficios_ativos = Pessoa.objects.filter(beneficio__ativo=True)
    
    context = {
        'beneficios': stats_list,
        'total_mensal_geral': total_mensal_geral,
        'total_mensal_geral_formatado': total_mensal_geral_formatado,
        'total_geral': todas_beneficios_ativos.count(),
        'total_ativos_geral': todas_beneficios_ativos.filter(status='ativo').count(),
        'total_em_espera_geral': todas_beneficios_ativos.filter(status='em_espera').count(),
        'total_desativados_geral': todas_beneficios_ativos.filter(status='desligado').count(),
        'distribuicao_valor': distribuicao_valor,
    }
    
    return render(request, 'beneficios/dashboard.html', context)

@login_required
def pessoa_create(request):
    """Criar nova pessoa"""
    if request.method == 'POST':
        form = PessoaForm(request.POST, request.FILES)
        if form.is_valid():
            pessoa = form.save()
            
            # Registrar histórico de status inicial
            from .models import HistoricoStatus
            from django.utils import timezone
            HistoricoStatus.objects.create(
                pessoa=pessoa,
                status_anterior=None,
                status_novo=pessoa.status,
                data=timezone.now(),
                usuario=request.user
            )
            
            # Salvar documento se enviado
            arquivo = form.cleaned_data.get('arquivo')
            if arquivo:
                Documento.objects.create(pessoa=pessoa, arquivo=arquivo)
            
            messages.success(request, f'Pessoa {pessoa.nome_completo} cadastrada com sucesso!')
            return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    else:
        beneficio_id = request.GET.get('beneficio')
        initial = {}
        if beneficio_id:
            initial['beneficio'] = beneficio_id
        form = PessoaForm(initial=initial)
    
    context = {
        'form': form,
        'titulo': 'Nova Pessoa',
        'voltar_url': '/'
    }
    return render(request, 'beneficios/pessoa_form.html', context)


@login_required
def pessoa_edit(request, pk):
    """Editar pessoa existente"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    status_anterior = pessoa.status  # Guardar antes do save
    
    try:
        documento_atual = pessoa.documento
    except Documento.DoesNotExist:
        documento_atual = None
    
    if request.method == 'POST':
        form = PessoaForm(request.POST, request.FILES, instance=pessoa)
        if form.is_valid():
            pessoa = form.save()
            
            # Registrar mudança de status se houve alteração
            if pessoa.status != status_anterior:
                from .models import HistoricoStatus
                from django.utils import timezone
                HistoricoStatus.objects.create(
                    pessoa=pessoa,
                    status_anterior=status_anterior,
                    status_novo=pessoa.status,
                    data=timezone.now(),
                    usuario=request.user
                )
            
            # Atualizar documento se enviado novo arquivo
            arquivo = form.cleaned_data.get('arquivo')
            if arquivo:
                if documento_atual:
                    documento_atual.arquivo.delete(save=False)
                    documento_atual.arquivo = arquivo
                    documento_atual.save()
                else:
                    Documento.objects.create(pessoa=pessoa, arquivo=arquivo)
            
            messages.success(request, f'Pessoa {pessoa.nome_completo} atualizada com sucesso!')
            return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    else:
        form = PessoaForm(instance=pessoa)
    
    # Buscar histórico de status
    from .models import HistoricoStatus
    historico = HistoricoStatus.objects.filter(pessoa=pessoa).select_related('usuario')
    
    context = {
        'form': form,
        'titulo': 'Editar Pessoa',
        'pessoa': pessoa,
        'documento_atual': documento_atual,
        'historico_status': historico,
        'voltar_url': f'/beneficio/{pessoa.beneficio.id}/pessoas/'
    }
    return render(request, 'beneficios/pessoa_form.html', context)

@login_required
def pessoa_ativar(request, pk):
    """Mudar status da pessoa para Ativo"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    status_anterior = pessoa.status
    
    if status_anterior == 'ativo':
        messages.info(request, f'{pessoa.nome_completo} já está ativa.')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    
    pessoa.status = 'ativo'
    pessoa.save()
    
    from .models import HistoricoStatus
    from django.utils import timezone
    HistoricoStatus.objects.create(
        pessoa=pessoa,
        status_anterior=status_anterior,
        status_novo='ativo',
        data=timezone.now(),
        usuario=request.user
    )
    registrar_log_acao(request, 'status_ativar', f'{pessoa.nome_completo} - {status_anterior} → ativo')
    messages.success(request, f'{pessoa.nome_completo} ativada com sucesso!')
    return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)


@login_required
def pessoa_espera(request, pk):
    """Mudar status da pessoa para Em Espera"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    status_anterior = pessoa.status
    
    if status_anterior == 'em_espera':
        messages.info(request, f'{pessoa.nome_completo} já está em espera.')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    
    pessoa.status = 'em_espera'
    pessoa.save()
    
    from .models import HistoricoStatus
    from django.utils import timezone
    HistoricoStatus.objects.create(
        pessoa=pessoa,
        status_anterior=status_anterior,
        status_novo='em_espera',
        data=timezone.now(),
        usuario=request.user
    )
    registrar_log_acao(request, 'status_espera', f'{pessoa.nome_completo} - {status_anterior} → em_espera')
    messages.success(request, f'{pessoa.nome_completo} movida para lista de espera!')
    return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)


@login_required
def pessoa_desligar(request, pk):
    """Mudar status da pessoa para Desligado"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    status_anterior = pessoa.status
    
    if status_anterior == 'desligado':
        messages.info(request, f'{pessoa.nome_completo} já está desligada.')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    
    pessoa.status = 'desligado'
    pessoa.save()
    
    from .models import HistoricoStatus
    from django.utils import timezone
    HistoricoStatus.objects.create(
        pessoa=pessoa,
        status_anterior=status_anterior,
        status_novo='desligado',
        data=timezone.now(),
        usuario=request.user
    )
    registrar_log_acao(request, 'status_desligar', f'{pessoa.nome_completo} - {status_anterior} → desligado')
    messages.success(request, f'{pessoa.nome_completo} desligada com sucesso!')
    return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)

@login_required
def pessoa_documento(request, pk):
    """Upload de documento da pessoa"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.pessoa = pessoa
            documento.save()
            messages.success(request, 'Documento cadastrado com sucesso!')
            return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    else:
        form = DocumentoForm()
    
    context = {
        'form': form,
        'pessoa': pessoa,
        'voltar_url': f'/beneficio/{pessoa.beneficio.id}/pessoas/'
    }
    return render(request, 'beneficios/documento_form.html', context)

@login_required
def pessoas_por_beneficio(request, beneficio_id):
    """Lista pessoas de um benefício com filtros otimizados."""
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id)
    
    # Query Base
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio).order_by('nome_completo')
        
    # Contagens dos Cards
    stats = pessoas_query.aggregate(
        ativos=Count('id', filter=Q(status='ativo')),
        em_espera=Count('id', filter=Q(status='em_espera')),
        desligados=Count('id', filter=Q(status='desligado')),
        total=Count('id'),
        total_mensal=Sum('valor_beneficio', filter=Q(status='ativo'))
    )
    # Formatar total mensal
    total_mensal = stats['total_mensal'] or 0
    total_mensal_formatado = f"{total_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    # Distribuição por faixa de valor (apenas deste benefício)
    distribuicao_valor = pessoas_query.filter(status='ativo').aggregate(
        ate_100=Count('id', filter=Q(valor_beneficio__lte=100)),
        de_101_150=Count('id', filter=Q(valor_beneficio__gt=100, valor_beneficio__lte=150)),
        de_151_200=Count('id', filter=Q(valor_beneficio__gt=150, valor_beneficio__lte=200)),
        de_201_250=Count('id', filter=Q(valor_beneficio__gt=200, valor_beneficio__lte=250)),
        de_251_300=Count('id', filter=Q(valor_beneficio__gt=250, valor_beneficio__lte=300)),
        acima_300=Count('id', filter=Q(valor_beneficio__gt=300))
    )
    
    # Captura de Filtros
    f_nome = request.GET.get('nome', '').strip()
    f_cpf = request.GET.get('cpf', '').strip()
    f_status = request.GET.get('status', 'ativo')
    f_valor = request.GET.get('valor', '').replace(',', '.')
    f_pos_de = request.GET.get('id_de', '').strip()
    f_pos_ate = request.GET.get('id_ate', '').strip()
    
    # Filtros no Banco
    pessoas_filtradas = pessoas_query
    
    if f_nome:
        pessoas_filtradas = pessoas_filtradas.filter(nome_completo__icontains=f_nome)
    
    if f_status == 'ativo':
        pessoas_filtradas = pessoas_filtradas.filter(status='ativo')
    elif f_status == 'desligado':
        pessoas_filtradas = pessoas_filtradas.filter(status='desligado')
    elif f_status == 'em_espera':
        pessoas_filtradas = pessoas_filtradas.filter(status='em_espera')
    
    try:
        if f_valor and float(f_valor) > 0:
            pessoas_filtradas = pessoas_filtradas.filter(valor_beneficio=float(f_valor))
    except ValueError:
        pass
    
    # FILTRO CPF OTIMIZADO
    if f_cpf:
        cpf_limpo = ''.join(filter(str.isdigit, f_cpf))
        
        if len(cpf_limpo) >= 4:
            ultimos_4 = cpf_limpo[-4:]
            candidatos = pessoas_filtradas.filter(cpf_ultimos_4=ultimos_4).only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_filtradas = pessoas_filtradas.filter(pk__in=ids_validos)
        else:
            candidatos = pessoas_filtradas.only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_filtradas = pessoas_filtradas.filter(pk__in=ids_validos)
    
    # Filtro de Posição
    slice_aplicado = False
    try:
        if f_pos_de and f_pos_ate:
            pos_de = int(f_pos_de)
            pos_ate = int(f_pos_ate)
            if pos_de < 1:
                messages.warning(request, 'A posição inicial deve ser maior que 0!')
            elif pos_ate < pos_de:
                messages.warning(request, 'A posição final não pode ser menor que a inicial!')
            else:
                pessoas_filtradas = pessoas_filtradas[pos_de-1:pos_ate]
                slice_aplicado = True
        elif f_pos_de:
            pos_de = int(f_pos_de)
            if pos_de >= 1:
                pessoas_filtradas = pessoas_filtradas[pos_de-1:]
                slice_aplicado = True
        elif f_pos_ate:
            pos_ate = int(f_pos_ate)
            pessoas_filtradas = pessoas_filtradas[:pos_ate]
            slice_aplicado = True
    except ValueError:
        messages.error(request, 'Posições devem ser números válidos!')
    
    if slice_aplicado:
        pessoas_list = list(pessoas_filtradas)
        start = int(f_pos_de) if f_pos_de else 1
        for idx, pessoa in enumerate(pessoas_list, start):
            pessoa.ordem = idx
        
        context = {
            'beneficio': beneficio,
            'pessoas': pessoas_list,
            'total_ativos': stats['ativos'],
            'total_em_espera': stats['em_espera'],
            'total_desativados': stats['desligados'],
            'total_geral': stats['total'],
            'total_mensal': total_mensal_formatado,
            'distribuicao_valor': distribuicao_valor,
            'por_pagina': len(pessoas_list),
            'filtros': {
                'nome': f_nome,
                'cpf': f_cpf,
                'status': f_status,
                'valor': f_valor,
                'id_de': f_pos_de,
                'id_ate': f_pos_ate,
            }
        }
        return render(request, 'beneficios/pessoas_lista.html', context)
    
    # Paginação normal
    por_pagina = int(request.GET.get('por_pagina', 15))
    if por_pagina not in [15, 25, 50]:
        por_pagina = 15
    
    paginator = Paginator(pessoas_filtradas, por_pagina)
    page_number = request.GET.get('page', 1)
    pessoas_page = paginator.get_page(page_number)
    
    start_index = (pessoas_page.number - 1) * por_pagina
    for idx, pessoa in enumerate(pessoas_page, start_index + 1):
        pessoa.ordem = idx
    
    context = {
        'beneficio': beneficio,
        'pessoas': pessoas_page,
        'total_ativos': stats['ativos'],
        'total_em_espera': stats['em_espera'],
        'total_desativados': stats['desligados'],
        'total_geral': stats['total'],
        'total_mensal': total_mensal_formatado,
        'distribuicao_valor': distribuicao_valor,
        'por_pagina': por_pagina,
        'filtros': {
            'nome': f_nome,
            'cpf': f_cpf,
            'status': f_status,
            'valor': f_valor,
            'id_de': f_pos_de,
            'id_ate': f_pos_ate,
        }
    }
    
    return render(request, 'beneficios/pessoas_lista.html', context)

@login_required
def beneficios_list(request):
    """Lista e gerencia benefícios"""
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores!')
        return redirect('dashboard')
    beneficios = Beneficio.objects.annotate(
        total_pessoas=Count('pessoa'),
        pessoas_ativas=Count('pessoa', filter=Q(pessoa__status='ativo')),
        pessoas_desligadas=Count('pessoa', filter=Q(pessoa__status='desligado'))
    ).order_by('nome')
    
    context = {
        'beneficios': beneficios,
    }
    return render(request, 'beneficios/beneficios_list.html', context)

@login_required
def beneficio_create(request):
    """Criar novo benefício"""
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores!')
        return redirect('dashboard')
    if request.method == 'POST':
        nome = request.POST.get('nome')
        conta_pagadora = request.POST.get('conta_pagadora', '')
        icone = request.POST.get('icone', 'bi-wallet2')
        descricao = request.POST.get('descricao', '')
        
        if nome:
            Beneficio.objects.create(nome=nome, descricao=descricao, conta_pagadora=conta_pagadora, icone=icone)
            messages.success(request, f'Benefício {nome} criado com sucesso!')
            return redirect('beneficios_list')
        else:
            messages.error(request, 'Nome do benefício é obrigatório!')
    
    return render(request, 'beneficios/beneficio_form.html', {'titulo': 'Novo Benefício'})

@login_required
def beneficio_edit_form(request, pk):
    """Editar benefício"""
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores!')
        return redirect('dashboard')
    beneficio = get_object_or_404(Beneficio, pk=pk)
    
    if request.method == 'POST':
        beneficio.nome = request.POST.get('nome', beneficio.nome)
        beneficio.descricao = request.POST.get('descricao', '')
        beneficio.conta_pagadora = request.POST.get('conta_pagadora', '')
        beneficio.icone = request.POST.get('icone', beneficio.icone)
        beneficio.save()
        messages.success(request, f'Benefício {beneficio.nome} atualizado!')
        return redirect('beneficios_list')
    
    context = {
        'beneficio': beneficio,
        'titulo': 'Editar Benefício'
    }
    return render(request, 'beneficios/beneficio_form.html', context)

@login_required
def beneficio_toggle(request, pk):
    """Ativar/Desativar benefício"""
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores!')
        return redirect('dashboard')
    beneficio = get_object_or_404(Beneficio, pk=pk)
    beneficio.ativo = not beneficio.ativo
    beneficio.save()
    
    status = 'ativado' if beneficio.ativo else 'desativado'
    messages.success(request, f'Benefício {beneficio.nome} {status} com sucesso!')
    return redirect('beneficios_list')

@login_required
def usuarios_list(request):
    """Lista usuários do sistema (apenas para admins)"""
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta área!')
        return redirect('dashboard')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Super Admin vê todos, Administrador não vê superusers
    if request.user.is_superuser:
        usuarios = User.objects.all().order_by('username')
    else:
        usuarios = User.objects.filter(is_superuser=False).order_by('username')
    
    context = {
        'usuarios': usuarios,
    }
    return render(request, 'beneficios/usuarios_list.html', context)

@login_required
def usuario_create(request):
    """Criar novo usuário (apenas para admins)"""
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta área!')
        return redirect('dashboard')
    
    if request.method == 'POST':
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        is_staff = request.POST.get('is_staff') == 'on'
        
        # Validações
        if not username or not password:
            messages.error(request, 'Usuário e senha são obrigatórios!')
        elif ' ' in username:
            messages.error(request, 'Nome de usuário não pode conter espaços!')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'Usuário {username} já existe!')
        else:
            user = User.objects.create_user(username=username, password=password)
            user.is_staff = is_staff
            user.is_superuser = False
            user.save()
            
            tipo = 'Administrador' if is_staff else 'Usuário'
            messages.success(request, f'{tipo} {username} criado com sucesso!')
            return redirect('usuarios_list')
    
    return render(request, 'beneficios/usuario_form.html', {'titulo': 'Novo Usuário'})

@login_required
def usuario_toggle_staff(request, pk):
    """Alternar status de admin do usuário"""
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta área!')
        return redirect('dashboard')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    
    if usuario.is_superuser:
        messages.error(request, 'Não é possível alterar um Super Admin!')
        return redirect('usuarios_list')
    
    if usuario == request.user:
        messages.error(request, 'Você não pode alterar suas próprias permissões!')
        return redirect('usuarios_list')
    
    usuario.is_staff = not usuario.is_staff
    usuario.save()
    
    tipo = 'Administrador' if usuario.is_staff else 'Usuário'
    messages.success(request, f'{usuario.username} agora é {tipo}!')
    return redirect('usuarios_list')

@login_required
def usuario_toggle_active(request, pk):
    """Ativar/Desativar usuário"""
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta área!')
        return redirect('dashboard')
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    usuario = get_object_or_404(User, pk=pk)
    
    if usuario.is_superuser:
        messages.error(request, 'Não é possível desativar um Super Admin!')
        return redirect('usuarios_list')
    
    if usuario == request.user:
        messages.error(request, 'Você não pode desativar sua própria conta!')
        return redirect('usuarios_list')
    
    usuario.is_active = not usuario.is_active
    usuario.save()
    
    status = 'ativado' if usuario.is_active else 'desativado'
    messages.success(request, f'Usuário {usuario.username} {status}!')
    return redirect('usuarios_list')


@login_required
def gerar_recibo(request, pk):
    """Gera apenas 2 vias do recibo (sem documentos)"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    
    if pessoa.status != 'ativo':
        messages.error(request, 'Só é possível gerar recibo de pessoa ativa!')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    
    try:
        from .utils import gerar_recibo_paginas_separadas
        pdf_buffer = gerar_recibo_paginas_separadas(pessoa)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="recibo_{pessoa.cpf}.pdf"'
        #registrar_log_acao(request, 'recibo_individual', f'Recibo - {pessoa.nome_completo}')
        return response
    except Exception as e:
        messages.error(request, f'Erro ao gerar recibo: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)

@login_required
def gerar_documentos(request, pk):
    """Retorna apenas os documentos anexados"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    
    try:
        if not hasattr(pessoa, 'documento') or not pessoa.documento:
            messages.error(request, 'Esta pessoa não possui documentos anexados!')
            return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
        
        response = HttpResponse(pessoa.documento.arquivo, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="documentos_{pessoa.cpf}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f'Erro ao acessar documentos: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)

@login_required
def gerar_memorando(request, pk):
    """Gera memorando individual com registro no histórico"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    
    if pessoa.status != 'ativo':
        messages.error(request, 'Só é possível gerar memorando de pessoa ativa!')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    
    try:
        # Registrar no histórico
        pessoas_dados = [{
            'pessoa': pessoa,
            'nome_completo': pessoa.nome_completo,
            'cpf': pessoa.cpf,
            'valor_beneficio': pessoa.valor_beneficio,
            'ordem': 1
        }]
        
        memorando = registrar_memorando(pessoa.beneficio, pessoas_dados, request.user)
        
        # Gerar PDF usando dados do snapshot
        from .utils import gerar_memorando_segunda_via_pdf
        pdf_buffer = gerar_memorando_segunda_via_pdf(memorando)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="memorando_{memorando.numero.replace("/", "-")}.pdf"'
        #registrar_log_acao(request, 'memorando_individual', f'Memorando {memorando.numero} - {pessoa.nome_completo}')
        return response
        
    except Exception as e:
        messages.error(request, f'Erro ao gerar memorando: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)


@login_required
def gerar_memorando_massa(request, beneficio_id):
    """Gera memorando em massa com registro no histórico"""
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id)
    
    # Aplica os mesmos filtros da listagem
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio, status='ativo').order_by('nome_completo')
    
    # Captura filtros da URL
    f_nome = request.GET.get('nome', '').strip()
    f_cpf = request.GET.get('cpf', '').strip()
    f_status = request.GET.get('status', '')
    f_valor = request.GET.get('valor', '').replace(',', '.')
    f_pos_de = request.GET.get('id_de', '').strip()
    f_pos_ate = request.GET.get('id_ate', '').strip()
    
    # Aplica filtros
    if f_nome:
        pessoas_query = pessoas_query.filter(nome_completo__icontains=f_nome)

    if f_status != 'ativo':
        messages.error(request, 'Geração em massa é permitida apenas com filtro de status "Ativo"!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    try:
        if f_valor and float(f_valor) > 0:
            pessoas_query = pessoas_query.filter(valor_beneficio=float(f_valor))
    except ValueError:
        pass
    
    # Filtro CPF
    if f_cpf:
        cpf_limpo = ''.join(filter(str.isdigit, f_cpf))
        if len(cpf_limpo) >= 4:
            ultimos_4 = cpf_limpo[-4:]
            candidatos = pessoas_query.filter(cpf_ultimos_4=ultimos_4).only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_query = pessoas_query.filter(pk__in=ids_validos)
        else:
            candidatos = pessoas_query.only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_query = pessoas_query.filter(pk__in=ids_validos)
    
    # Filtro de posição
    try:
        if f_pos_de and f_pos_ate:
            pos_de = int(f_pos_de)
            pos_ate = int(f_pos_ate)
            if pos_de >= 1 and pos_ate >= pos_de:
                pessoas_query = pessoas_query[pos_de-1:pos_ate]
        elif f_pos_de:
            pos_de = int(f_pos_de)
            if pos_de >= 1:
                pessoas_query = pessoas_query[pos_de-1:]
        elif f_pos_ate:
            pos_ate = int(f_pos_ate)
            pessoas_query = pessoas_query[:pos_ate]
    except ValueError:
        pass
    
    pessoas = list(pessoas_query)
    
    if not pessoas:
        messages.error(request, 'Nenhuma pessoa encontrada com os filtros aplicados!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    try:
        # Preparar dados para snapshot
        pessoas_dados = []
        for idx, pessoa in enumerate(pessoas, 1):
            pessoas_dados.append({
                'pessoa': pessoa,
                'nome_completo': pessoa.nome_completo,
                'cpf': pessoa.cpf,
                'valor_beneficio': pessoa.valor_beneficio,
                'ordem': idx
            })
        
        # Registrar no histórico
        memorando = registrar_memorando(beneficio, pessoas_dados, request.user)
        
        # Gerar PDF usando dados do snapshot
        from .utils import gerar_memorando_segunda_via_pdf
        pdf_buffer = gerar_memorando_segunda_via_pdf(memorando)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="memorando_{memorando.numero.replace("/", "-")}.pdf"'
        #registrar_log_acao(request, 'memorando_massa', f'Memorando {memorando.numero} - {beneficio.nome} - {len(pessoas)} pessoas')
        return response
    except Exception as e:
        messages.error(request, f'Erro ao gerar memorando em massa: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)

@login_required
def gerar_recibos_massa(request, beneficio_id):
    """Gera recibos em massa (2 vias para cada pessoa) respeitando os filtros aplicados"""
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id)
    
    # Aplica os mesmos filtros da listagem
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio, status='ativo').order_by('nome_completo')
    
    # Captura filtros da URL
    f_nome = request.GET.get('nome', '').strip()
    f_cpf = request.GET.get('cpf', '').strip()
    f_status = request.GET.get('status', '')
    f_valor = request.GET.get('valor', '').replace(',', '.')
    f_pos_de = request.GET.get('id_de', '').strip()
    f_pos_ate = request.GET.get('id_ate', '').strip()
    
    # Aplica filtros
    if f_nome:
        pessoas_query = pessoas_query.filter(nome_completo__icontains=f_nome)

    if f_status != 'ativo':
        messages.error(request, 'Geração em massa é permitida apenas com filtro de status "Ativo"!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    try:
        if f_valor and float(f_valor) > 0:
            pessoas_query = pessoas_query.filter(valor_beneficio=float(f_valor))
    except ValueError:
        pass
    
    # Filtro CPF
    if f_cpf:
        cpf_limpo = ''.join(filter(str.isdigit, f_cpf))
        if len(cpf_limpo) >= 4:
            ultimos_4 = cpf_limpo[-4:]
            candidatos = pessoas_query.filter(cpf_ultimos_4=ultimos_4).only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_query = pessoas_query.filter(pk__in=ids_validos)
        else:
            candidatos = pessoas_query.only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_query = pessoas_query.filter(pk__in=ids_validos)
    
    # Filtro de posição
    try:
        if f_pos_de and f_pos_ate:
            pos_de = int(f_pos_de)
            pos_ate = int(f_pos_ate)
            if pos_de >= 1 and pos_ate >= pos_de:
                pessoas_query = pessoas_query[pos_de-1:pos_ate]
        elif f_pos_de:
            pos_de = int(f_pos_de)
            if pos_de >= 1:
                pessoas_query = pessoas_query[pos_de-1:]
        elif f_pos_ate:
            pos_ate = int(f_pos_ate)
            pessoas_query = pessoas_query[:pos_ate]
    except ValueError:
        pass
    
    pessoas = list(pessoas_query)
    
    if not pessoas:
        messages.error(request, 'Nenhuma pessoa encontrada com os filtros aplicados!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    try:
        from .utils import gerar_recibos_massa_pdf
        pdf_buffer = gerar_recibos_massa_pdf(pessoas)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="recibos_massa_{beneficio.nome}.pdf"'
        #registrar_log_acao(request, 'recibos_massa', f'Recibos em massa - {beneficio.nome} - {len(pessoas)} pessoas')
        return response
    except Exception as e:
        messages.error(request, f'Erro ao gerar recibos em massa: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)

@login_required
def documento_protegido(request, pk):
    """Serve documento via X-Accel-Redirect (nginx) - requer autenticação"""
    import os
    from django.http import Http404
    from django.conf import settings
    from urllib.parse import quote
    
    pessoa = get_object_or_404(Pessoa, pk=pk)
    documento = get_object_or_404(Documento, pessoa=pessoa)
    
    file_path = documento.arquivo.name
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    if not os.path.exists(full_path):
        raise Http404("Documento não encontrado")
    
    # Codificar caminho para UTF-8
    file_path_encoded = quote(file_path, safe='/')
    
    response = HttpResponse()
    response['Content-Type'] = 'application/pdf'
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
    response['X-Accel-Redirect'] = f'/protected-media/{file_path_encoded}'
    
    return response

@login_required
def gerar_documentos_massa(request, beneficio_id):
    """
    Gera documentos em massa
    """
    import os
    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    from .models import Beneficio, Pessoa

    # 1.Verifica se o benefício existe
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id )
    
    # 2. Captura de Filtros da URL 
    f_status = request.GET.get('status', '').strip().lower()
    f_nome = request.GET.get('nome', '').strip()
    f_cpf = request.GET.get('cpf', '').strip()
    f_valor = request.GET.get('valor', '').replace(',', '.')
    f_pos_de = request.GET.get('id_de', '').strip()
    f_pos_ate = request.GET.get('id_ate', '').strip()

   
    # Se o status for 'desativado' OU se estiver vazio (Todos), o sistema BARRA.
    if f_status != 'ativo':
        messages.error(request, 'Não existem pessoas ativas para gerar o PDF com os filtros aplicados!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)

    # 4. BLOQUEIO DE MANIPULAÇÃO DE TEXTO 
    if (f_pos_de and not f_pos_de.isdigit()) or (f_pos_ate and not f_pos_ate.isdigit()):
        messages.error(request, 'Parâmetros de posição inválidos detectados!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)

    # 5. Query de Ativos (Usando o campo Boolean 'ativo' do seu Model)
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio, status='ativo').order_by('nome_completo')
    
    # Filtros Adicionais
    if f_nome:
        pessoas_query = pessoas_query.filter(nome_completo__icontains=f_nome)
    
    if f_valor:
        try:
            pessoas_query = pessoas_query.filter(valor_beneficio=float(f_valor))
        except ValueError:
            pass
    
    if f_cpf:
        cpf_limpo = ''.join(filter(str.isdigit, f_cpf))
        if cpf_limpo:
            if len(cpf_limpo) >= 4:
                ultimos_4 = cpf_limpo[-4:]
                candidatos = pessoas_query.filter(cpf_ultimos_4=ultimos_4).only('id', 'cpf')
            else:
                candidatos = pessoas_query.only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_query = pessoas_query.filter(pk__in=ids_validos)
    
    # 6. Validação de Intervalo e Posição
    total_ativos = pessoas_query.count()
    if total_ativos == 0:
        messages.error(request, 'Nenhuma pessoa ativa encontrada com os filtros aplicados!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)

    try:
        pos_de = int(f_pos_de) if f_pos_de else 1
        pos_ate = int(f_pos_ate) if f_pos_ate else total_ativos
        
        if pos_de < 1 or pos_de > total_ativos or pos_de > pos_ate:
            messages.error(request, 'Intervalo de posições inválido!')
            return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
            
        pessoas_query = pessoas_query[pos_de-1:min(pos_ate, total_ativos)]
    except (ValueError, TypeError):
        pass

    # 7. Verificação Final e Documentos
    pessoas = list(pessoas_query.select_related('documento'))
    if not pessoas:
        messages.error(request, 'Nenhuma pessoa ativa encontrada!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    # Validação de arquivos físicos no disco
    pessoas_sem_doc = []
    for p in pessoas:
        if not hasattr(p, 'documento') or not p.documento or not p.documento.arquivo:
            pessoas_sem_doc.append(p.nome_completo)
        elif not os.path.exists(p.documento.arquivo.path):
            pessoas_sem_doc.append(f"{p.nome_completo} (arquivo não encontrado)")
    
    if pessoas_sem_doc:
        nomes = ', '.join(pessoas_sem_doc[:10])
        messages.error(request, f'Existem pessoas sem documento anexado: {nomes}')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    # 8. Geração do PDF (Chama seu utils.py original)
    try:
        from .utils import gerar_documentos_massa_pdf
        pdf_buffer = gerar_documentos_massa_pdf(pessoas)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="documentos_massa_{beneficio.id}.pdf"'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        registrar_log_acao(request, 'documentos_massa', f'Documentos em massa - {beneficio.nome} - {len(pessoas)} pessoas')
        return response
    except Exception as e:
        messages.error(request, f'Erro ao gerar documentos: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)

@login_required
def sobre(request):
    """Retorna dados para o modal Sobre"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    context = {
        'versao': '1.4.2',
        'data_compilacao': '10/03/2026',
        'total_usuarios': '10',
        'total_programas': '2',
    }
    return render(request, 'beneficios/sobre.html', context)

@login_required
def memorandos_lista(request):
    """Lista histórico de memorandos com filtros"""
    memorandos_query = Memorando.objects.select_related('beneficio', 'usuario').order_by('-created_at')
    
    # Filtros
    f_data_inicio = request.GET.get('data_inicio', '').strip()
    f_data_fim = request.GET.get('data_fim', '').strip()
    f_beneficio = request.GET.get('beneficio', '').strip()
    
    if f_data_inicio:
        try:
            from datetime import datetime
            data_inicio = datetime.strptime(f_data_inicio, '%Y-%m-%d')
            memorandos_query = memorandos_query.filter(created_at__date__gte=data_inicio)
        except ValueError:
            pass
    
    if f_data_fim:
        try:
            from datetime import datetime
            data_fim = datetime.strptime(f_data_fim, '%Y-%m-%d')
            memorandos_query = memorandos_query.filter(created_at__date__lte=data_fim)
        except ValueError:
            pass
    
    if f_beneficio and f_beneficio.isdigit():
        memorandos_query = memorandos_query.filter(beneficio_id=int(f_beneficio))
    
    # Paginação
    paginator = Paginator(memorandos_query, 20)
    page_number = request.GET.get('page', 1)
    memorandos = paginator.get_page(page_number)
    
    # Benefícios para o filtro
    beneficios = Beneficio.objects.order_by('nome')
    
    context = {
        'memorandos': memorandos,
        'beneficios': beneficios,
        'filtros': {
            'data_inicio': f_data_inicio,
            'data_fim': f_data_fim,
            'beneficio': f_beneficio,
        }
    }
    
    return render(request, 'beneficios/memorandos_lista.html', context)


@login_required
def memorando_segunda_via(request, pk):
    """Gera segunda via do memorando (PDF idêntico ao original)"""
    memorando = get_object_or_404(Memorando, pk=pk)
    
    try:
        from .utils import gerar_memorando_segunda_via_pdf
        pdf_buffer = gerar_memorando_segunda_via_pdf(memorando)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="memorando_{memorando.numero.replace("/", "-")}_2via.pdf"'
        return response
    except Exception as e:
        messages.error(request, f'Erro ao gerar segunda via: {str(e)}')
        return redirect('memorandos_lista')

@login_required
def configuracoes_gerais(request):
    """Editar configurações gerais do sistema"""
    if not request.user.is_staff:
        messages.error(request, 'Você não tem permissão para acessar esta área!')
        return redirect('dashboard')
    
    from .models import ConfiguracaoGeral
    config = ConfiguracaoGeral.get_config()
    
    if request.method == 'POST':
        config.secretaria_nome = request.POST.get('secretaria_nome', '').strip()
        config.secretaria_cargo = request.POST.get('secretaria_cargo', '').strip()
        config.financas_nome = request.POST.get('financas_nome', '').strip()
        config.financas_cargo = request.POST.get('financas_cargo', '').strip()
        config.email_institucional = request.POST.get('email_institucional', '').strip()
        config.endereco = request.POST.get('endereco', '').strip()
        config.cep = request.POST.get('cep', '').strip()
        config.save()
        
        messages.success(request, 'Configurações salvas com sucesso!')
        return redirect('configuracoes_gerais')
    
    return render(request, 'beneficios/configuracoes_gerais.html', {'config': config})

@login_required
def trocar_senha(request):
    """Troca de senha obrigatória ou voluntária"""
    obrigatorio = request.user.must_change_password
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Senha alterada com sucesso!')
            return redirect('dashboard')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'obrigatorio': obrigatorio,
    }
    return render(request, 'beneficios/trocar_senha.html', context)

@login_required
def gerar_remessa_banco(request, beneficio_id):
    """Gera arquivo CSV de remessa bancária respeitando filtros aplicados"""
    import csv
    from io import StringIO
    
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id)
    
    # Captura filtros da URL
    f_nome = request.GET.get('nome', '').strip()
    f_cpf = request.GET.get('cpf', '').strip()
    f_status = request.GET.get('status', '').strip()
    f_valor = request.GET.get('valor', '').replace(',', '.')
    f_pos_de = request.GET.get('id_de', '').strip()
    f_pos_ate = request.GET.get('id_ate', '').strip()
    
    # Bloqueio: apenas status ativo
    if f_status != 'ativo':
        messages.error(request, 'Geração de remessa é permitida apenas com filtro de status "Ativo"!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    # Bloqueio de posições inválidas
    if (f_pos_de and not f_pos_de.isdigit()) or (f_pos_ate and not f_pos_ate.isdigit()):
        messages.error(request, 'Parâmetros de posição inválidos!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    # Query base: apenas ativos
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio, status='ativo').order_by('nome_completo')
    
    # Filtros
    if f_nome:
        pessoas_query = pessoas_query.filter(nome_completo__icontains=f_nome)
    
    if f_valor:
        try:
            pessoas_query = pessoas_query.filter(valor_beneficio=float(f_valor))
        except ValueError:
            pass
    
    if f_cpf:
        cpf_limpo = ''.join(filter(str.isdigit, f_cpf))
        if cpf_limpo:
            if len(cpf_limpo) >= 4:
                ultimos_4 = cpf_limpo[-4:]
                candidatos = pessoas_query.filter(cpf_ultimos_4=ultimos_4).only('id', 'cpf')
            else:
                candidatos = pessoas_query.only('id', 'cpf')
            ids_validos = [p.pk for p in candidatos if cpf_limpo in ''.join(filter(str.isdigit, p.cpf))]
            pessoas_query = pessoas_query.filter(pk__in=ids_validos)
    
    # Filtro de posição
    try:
        if f_pos_de and f_pos_ate:
            pos_de = int(f_pos_de)
            pos_ate = int(f_pos_ate)
            if pos_de >= 1 and pos_ate >= pos_de:
                pessoas_query = pessoas_query[pos_de-1:pos_ate]
        elif f_pos_de:
            pos_de = int(f_pos_de)
            if pos_de >= 1:
                pessoas_query = pessoas_query[pos_de-1:]
        elif f_pos_ate:
            pos_ate = int(f_pos_ate)
            pessoas_query = pessoas_query[:pos_ate]
    except ValueError:
        pass
    
    pessoas = list(pessoas_query)
    
    if not pessoas:
        messages.error(request, 'Nenhuma pessoa ativa encontrada com os filtros aplicados!')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)
    
    # Montar nome do arquivo
    nome_beneficio = beneficio.nome.upper()
    if f_valor:
        try:
            valor_formatado = f"{float(f_valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            nome_arquivo = f"Poupanca Social POCINHOS - {nome_beneficio} - {valor_formatado}.csv"
        except ValueError:
            nome_arquivo = f"Poupanca Social POCINHOS - {nome_beneficio}.csv"
    else:
        nome_arquivo = f"Poupanca Social POCINHOS - {nome_beneficio}.csv"
    
    # Gerar CSV
    output = StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_NONE, escapechar='\\')
    writer.writerow(['CPF', 'NOME', 'VALOR', 'OBSERVACAO'])
    
    for pessoa in pessoas:
        cpf_numeros = ''.join(filter(str.isdigit, pessoa.cpf))
        nome = pessoa.nome_completo.upper()
        valor = f"{pessoa.valor_beneficio:.2f}"
        writer.writerow([cpf_numeros, nome, valor, 'CEP 58150000'])
    
    # Response com BOM para Excel
    response = HttpResponse(
        '\ufeff' + output.getvalue(),
        content_type='text/csv; charset=utf-8'
    )
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    registrar_log_acao(request, 'remessa_banco', f'Remessa - {beneficio.nome} - {len(pessoas)} pessoas - R$ {sum(p.valor_beneficio for p in pessoas):.2f}')
    return response

@login_required
def relatorio_beneficiarios(request):
    """Página de filtros do relatório de beneficiários"""
    beneficios = Beneficio.objects.filter(ativo=True).order_by('nome')
    
    # Buscar bairros distintos
    bairros = (Pessoa.objects.values_list('bairro', flat=True)
               .distinct().order_by('bairro'))
    
    context = {
        'beneficios_lista': beneficios,
        'bairros': bairros,
        'titulo': 'Relatório de Beneficiários',
    }
    return render(request, 'beneficios/relatorio_beneficiarios.html', context)

@xframe_options_sameorigin
@login_required
def gerar_relatorio_beneficiarios(request):
    """Gera relatório de beneficiários em PDF ou Excel"""
    from datetime import datetime
    
    # Captura filtros
    f_beneficio = request.GET.get('beneficio', '').strip()
    f_status = request.GET.get('status', '').strip()
    f_valor = request.GET.get('valor', '').replace(',', '.').strip()
    f_bairro = request.GET.get('bairro', '').strip()
    f_sexo = request.GET.get('sexo', '').strip()
    f_data_de = request.GET.get('data_de', '').strip()
    f_data_ate = request.GET.get('data_ate', '').strip()
    f_formato = request.GET.get('formato', 'pdf').strip()
    
    # Query base
    pessoas_query = Pessoa.objects.select_related('beneficio').order_by('beneficio__nome', 'nome_completo')
    
    # Filtro benefício
    if f_beneficio and f_beneficio.isdigit():
        pessoas_query = pessoas_query.filter(beneficio_id=int(f_beneficio))
        beneficio_nome = Beneficio.objects.filter(id=int(f_beneficio)).values_list('nome', flat=True).first() or 'Todos'
    else:
        pessoas_query = pessoas_query.filter(beneficio__ativo=True)
        beneficio_nome = 'Todos os Benefícios'
    
    # Filtro status
    if f_status and f_status != 'todos':
        pessoas_query = pessoas_query.filter(status=f_status)
        status_label = dict(Pessoa.STATUS_CHOICES).get(f_status, f_status)
    else:
        status_label = 'Todos'
    
    # Filtro valor
    if f_valor:
        try:
            pessoas_query = pessoas_query.filter(valor_beneficio=float(f_valor))
        except ValueError:
            pass
    
    # Filtro bairro
    if f_bairro:
        pessoas_query = pessoas_query.filter(bairro=f_bairro)
    
    # Filtro sexo
    if f_sexo and f_sexo != 'todos':
        pessoas_query = pessoas_query.filter(sexo=f_sexo)
    
    # Filtro período de cadastro
    if f_data_de:
        try:
            data_de = datetime.strptime(f_data_de, '%Y-%m-%d')
            pessoas_query = pessoas_query.filter(created_at__date__gte=data_de)
        except ValueError:
            pass
    
    if f_data_ate:
        try:
            data_ate = datetime.strptime(f_data_ate, '%Y-%m-%d')
            pessoas_query = pessoas_query.filter(created_at__date__lte=data_ate)
        except ValueError:
            pass
    
    pessoas = list(pessoas_query)

    if not pessoas:
        messages.error(request, 'Nenhuma pessoa encontrada com os filtros aplicados!')
        return redirect('relatorio_beneficiarios')
    
    # Totalizadores
    total_pessoas = len(pessoas)
    total_valor = sum(p.valor_beneficio for p in pessoas)
    total_ativos = sum(1 for p in pessoas if p.status == 'ativo')
    total_espera = sum(1 for p in pessoas if p.status == 'em_espera')
    total_desligados = sum(1 for p in pessoas if p.status == 'desligado')
    
    if f_formato == 'xlsx':
        from .utils import gerar_excel_beneficiarios
        #registrar_log_acao(request, 'relatorio_beneficiarios_xlsx', f'Relatório Beneficiários Excel - {beneficio_nome} - {total_pessoas} pessoas')
        return gerar_excel_beneficiarios(
            pessoas, beneficio_nome, status_label,
            total_pessoas, total_valor, total_ativos, total_espera, total_desligados
        )
    else:
        from .utils import gerar_pdf_beneficiarios
        #registrar_log_acao(request, 'relatorio_beneficiarios_pdf', f'Relatório Beneficiários PDF - {beneficio_nome} - {total_pessoas} pessoas')
        return gerar_pdf_beneficiarios(
            pessoas, beneficio_nome, status_label,
            total_pessoas, total_valor, total_ativos, total_espera, total_desligados
        )

@login_required
def relatorio_financeiro(request):
    """Página de filtros do relatório financeiro"""
    beneficios = Beneficio.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'beneficios_lista': beneficios,
        'titulo': 'Relatório Financeiro',
    }
    return render(request, 'beneficios/relatorio_financeiro.html', context)


@xframe_options_sameorigin
@login_required
def gerar_relatorio_financeiro(request):
    """Gera relatório financeiro em PDF ou Excel"""
    f_beneficio = request.GET.get('beneficio', '').strip()
    f_status = request.GET.get('status', '').strip()
    f_formato = request.GET.get('formato', 'pdf').strip()
    
    # Query base
    pessoas_query = Pessoa.objects.select_related('beneficio')
    
    # Filtro benefício
    if f_beneficio and f_beneficio.isdigit():
        pessoas_query = pessoas_query.filter(beneficio_id=int(f_beneficio))
        beneficios_filtro = Beneficio.objects.filter(id=int(f_beneficio))
    else:
        pessoas_query = pessoas_query.filter(beneficio__ativo=True)
        beneficios_filtro = Beneficio.objects.filter(ativo=True)
    
    # Filtro status
    if f_status and f_status != 'todos':
        pessoas_query = pessoas_query.filter(status=f_status)
        status_label = dict(Pessoa.STATUS_CHOICES).get(f_status, f_status)
    else:
        status_label = 'Todos'
    
    beneficio_label = 'Todos os Benefícios'
    if f_beneficio and f_beneficio.isdigit():
        beneficio_label = beneficios_filtro.values_list('nome', flat=True).first() or 'Todos'
    
    pessoas = list(pessoas_query)
    
    if not pessoas:
        messages.error(request, 'Nenhuma pessoa encontrada com os filtros aplicados!')
        return redirect('relatorio_financeiro')
    
    # Resumo geral
    total_beneficios = beneficios_filtro.count()
    total_ativos_geral = sum(1 for p in pessoas if p.status == 'ativo')
    total_espera_geral = sum(1 for p in pessoas if p.status == 'em_espera')
    total_desligados_geral = sum(1 for p in pessoas if p.status == 'desligado')
    total_pessoas = len(pessoas)
    total_valor = sum(p.valor_beneficio for p in pessoas)
    
    resumo_geral = {
        'total_beneficios': total_beneficios,
        'total_pessoas': total_pessoas,
        'total_ativos': total_ativos_geral,
        'total_valor': total_valor,
    }
    
    # Detalhamento por benefício
    det_beneficios = []
    for b in beneficios_filtro.order_by('nome'):
        pessoas_b = [p for p in pessoas if p.beneficio_id == b.id]
        ativos = sum(1 for p in pessoas_b if p.status == 'ativo')
        espera = sum(1 for p in pessoas_b if p.status == 'em_espera')
        desligados = sum(1 for p in pessoas_b if p.status == 'desligado')
        valor = sum(p.valor_beneficio for p in pessoas_b)
        percentual = (float(valor) / float(total_valor) * 100) if total_valor > 0 else 0
        
        det_beneficios.append({
            'descricao': b.nome_exibicao,
            'nome_oficial': b.nome,
            'ativos': ativos,
            'espera': espera,
            'desligados': desligados,
            'valor': valor,
            'percentual': percentual,
        })
    
    # Detalhamento por faixa de valor (apenas ativos)
    pessoas_ativas = pessoas
    faixas_config = [
        ('Até R$ 100', 0, 100),
        ('R$ 101 - 150', 100, 150),
        ('R$ 151 - 200', 150, 200),
        ('R$ 201 - 250', 200, 250),
        ('R$ 251 - 300', 250, 300),
        ('Acima de R$ 300', 300, None),
    ]
    
    det_faixas = []
    for nome_faixa, vmin, vmax in faixas_config:
        if vmax is None:
            pessoas_faixa = [p for p in pessoas_ativas if p.valor_beneficio > vmin]
        elif vmin == 0:
            pessoas_faixa = [p for p in pessoas_ativas if p.valor_beneficio <= vmax]
        else:
            pessoas_faixa = [p for p in pessoas_ativas if vmin < p.valor_beneficio <= vmax]
        
        qtd = len(pessoas_faixa)
        valor = sum(p.valor_beneficio for p in pessoas_faixa)
        percentual = (float(valor) / float(total_valor) * 100) if total_valor > 0 else 0
        
        det_faixas.append({
            'faixa': nome_faixa,
            'pessoas': qtd,
            'valor': valor,
            'percentual': percentual,
        })
    
    dados = {
        'beneficio_label': beneficio_label,
        'status_label': status_label,
        'resumo_geral': resumo_geral,
        'det_beneficios': det_beneficios,
        'det_faixas': det_faixas,
        'total_valor': total_valor,
        'total_ativos': total_ativos_geral,
        'total_espera': total_espera_geral,
        'total_desligados': total_desligados_geral,
        'total_pessoas': total_pessoas,
    }
    
    if f_formato == 'xlsx':
        from .utils import gerar_excel_financeiro
        #registrar_log_acao(request, 'relatorio_financeiro_xlsx', f'Relatório Financeiro Excel - {beneficio_label} - {total_pessoas} pessoas')
        return gerar_excel_financeiro(dados)
    else:
        from .utils import gerar_pdf_financeiro
        #registrar_log_acao(request, 'relatorio_financeiro_pdf', f'Relatório Financeiro PDF - {beneficio_label} - {total_pessoas} pessoas')
        return gerar_pdf_financeiro(dados)

@login_required
def auditoria(request):
    """Tela de auditoria geral do sistema"""
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores!')
        return redirect('dashboard')
    
    from auditlog.models import LogEntry
    from django.contrib.auth import get_user_model
    from datetime import datetime
    User = get_user_model()
    
    # Filtros
    f_data_de = request.GET.get('data_de', '').strip()
    f_data_ate = request.GET.get('data_ate', '').strip()
    f_usuario = request.GET.get('usuario', '').strip()
    f_tipo = request.GET.get('tipo', '').strip()
    f_entidade = request.GET.get('entidade', '').strip()
    
    # ═══ AUDITLOG (alterações em models) ═══
    audit_query = LogEntry.objects.select_related('actor', 'content_type').order_by('-timestamp')
    
    if f_data_de:
        try:
            audit_query = audit_query.filter(timestamp__date__gte=datetime.strptime(f_data_de, '%Y-%m-%d'))
        except ValueError:
            pass
    
    if f_data_ate:
        try:
            audit_query = audit_query.filter(timestamp__date__lte=datetime.strptime(f_data_ate, '%Y-%m-%d'))
        except ValueError:
            pass
    
    if f_usuario and f_usuario.isdigit():
        audit_query = audit_query.filter(actor_id=int(f_usuario))
    
    if f_entidade and f_entidade == 'models':
        pass  # mostra tudo do auditlog
    elif f_entidade and f_entidade == 'acoes':
        audit_query = LogEntry.objects.none()
    elif f_entidade and f_entidade != '':
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.filter(model=f_entidade.lower()).first()
        if ct:
            audit_query = audit_query.filter(content_type=ct)
    
    if f_tipo:
        action_map = {'criacao': 0, 'edicao': 1, 'exclusao': 2}
        if f_tipo in action_map:
            audit_query = audit_query.filter(action=action_map[f_tipo])
    
    # ═══ LOG AÇÕES (geração de documentos) ═══
    from .models import LogAcao
    acoes_query = LogAcao.objects.select_related('usuario').order_by('-created_at')
    
    if f_data_de:
        try:
            acoes_query = acoes_query.filter(created_at__date__gte=datetime.strptime(f_data_de, '%Y-%m-%d'))
        except ValueError:
            pass
    
    if f_data_ate:
        try:
            acoes_query = acoes_query.filter(created_at__date__lte=datetime.strptime(f_data_ate, '%Y-%m-%d'))
        except ValueError:
            pass
    
    if f_usuario and f_usuario.isdigit():
        acoes_query = acoes_query.filter(usuario_id=int(f_usuario))
    
    if f_entidade and f_entidade == 'acoes':
        pass  # mostra tudo das ações
    elif f_entidade and f_entidade == 'models':
        acoes_query = LogAcao.objects.none()
    elif f_entidade and f_entidade not in ('', 'models', 'acoes'):
        acoes_query = LogAcao.objects.none()
    
    if f_tipo == 'geracao':
        audit_query = LogEntry.objects.none()
    elif f_tipo in ('criacao', 'edicao', 'exclusao'):
        acoes_query = LogAcao.objects.none()
    
    # Combinar e ordenar
    registros = []
    
    action_labels = {0: 'Criação', 1: 'Edição', 2: 'Exclusão'}
    model_labels = {
        'pessoa': 'Pessoa',
        'beneficio': 'Benefício',
        'user': 'Usuário',
        'documento': 'Documento',
        'configuracaogeral': 'Configuração Geral',
    }
    
    for log in audit_query[:200]:
        changes = log.changes_dict if hasattr(log, 'changes_dict') else {}
        detalhes = []
        for campo, valores in changes.items():
            detalhes.append(f'{campo}: {valores[0]} → {valores[1]}')
        
        registros.append({
            'data': log.timestamp,
            'usuario': log.actor.username if log.actor else 'Sistema',
            'tipo': action_labels.get(log.action, 'Outro'),
            'tipo_classe': 'success' if log.action == 0 else 'warning' if log.action == 1 else 'danger',
            'entidade': model_labels.get(log.content_type.model, log.content_type.model) if log.content_type else '-',
            'objeto': str(log.object_repr),
            'detalhes': ' | '.join(detalhes) if detalhes else '-',
            'ip': log.remote_addr or '-',
        })
    
    for acao in acoes_query[:200]:
        registros.append({
            'data': acao.created_at,
            'usuario': acao.usuario.username if acao.usuario else 'Sistema',
            'tipo': acao.get_tipo_display(),
            'tipo_classe': 'info',
            'entidade': 'Ação',
            'objeto': '-',
            'detalhes': acao.descricao,
            'ip': acao.ip or '-',
        })
    
    # Ordenar por data decrescente
    registros.sort(key=lambda x: x['data'], reverse=True)
    registros = registros[:300]
    
    # Paginação
    paginator = Paginator(registros, 30)
    page_number = request.GET.get('page', 1)
    registros_page = paginator.get_page(page_number)
    
    # Dados para filtros
    usuarios = User.objects.order_by('username')
    
    context = {
        'registros': registros_page,
        'usuarios': usuarios,
        'filtros': {
            'data_de': f_data_de,
            'data_ate': f_data_ate,
            'usuario': f_usuario,
            'tipo': f_tipo,
            'entidade': f_entidade,
        }
    }
    return render(request, 'beneficios/auditoria.html', context)

def _atualizar_cron(config):
    """Atualiza a crontab do www-data com os agendamentos"""
    from crontab import CronTab
    
    cron = CronTab(user=True)
    cron.remove_all(comment='gesocial_backup_db')
    cron.remove_all(comment='gesocial_backup_doc')
    
    if config.agendamento_db_ativo:
        comando = (
            'cd /var/www/sistema_beneficios && '
            '/var/www/sistema_beneficios/venv/bin/python manage.py executar_backup '
            '--tipo-backup banco --tipo automatico '
            '>> /var/log/gesocial_backup.log 2>&1'
        )
        job = cron.new(command=comando, comment='gesocial_backup_db')
        job.hour.on(config.horario_db.hour)
        job.minute.on(config.horario_db.minute)
        if config.frequencia_db == 'semanal':
            job.dow.on(0)
    
    if config.agendamento_doc_ativo:
        comando = (
            'cd /var/www/sistema_beneficios && '
            '/var/www/sistema_beneficios/venv/bin/python manage.py executar_backup '
            '--tipo-backup documentos --tipo automatico '
            '>> /var/log/gesocial_backup.log 2>&1'
        )
        job = cron.new(command=comando, comment='gesocial_backup_doc')
        job.hour.on(config.horario_doc.hour)
        job.minute.on(config.horario_doc.minute)
        if config.frequencia_doc == 'semanal':
            job.dow.on(0)
    
    cron.write()


@login_required
def backup_config(request):
    """Configuração e execução de backup (Super Admin apenas)"""
    if not request.user.is_superuser:
        messages.error(request, 'Acesso restrito ao Super Admin!')
        return redirect('dashboard')
    
    from .models import BackupConfig, BackupHistorico
    config = BackupConfig.get_config()
    
    if request.method == 'POST':
        acao = request.POST.get('acao', '')
        
        if acao == 'salvar_config':
            config.rclone_nome_remote = request.POST.get('rclone_nome_remote', '').strip() or 'DRIVE'
            config.rclone_pasta = request.POST.get('rclone_pasta', '').strip() or 'BackupGESOCIAL'
            
            config.agendamento_db_ativo = request.POST.get('agendamento_db_ativo') == 'on'
            config.horario_db = request.POST.get('horario_db', '03:00')
            config.frequencia_db = request.POST.get('frequencia_db', 'diario')
            config.versoes_nuvem_db = int(request.POST.get('versoes_nuvem_db', 5))
            config.versoes_local_db = int(request.POST.get('versoes_local_db', 5))
            
            config.agendamento_doc_ativo = request.POST.get('agendamento_doc_ativo') == 'on'
            config.horario_doc = request.POST.get('horario_doc', '04:00')
            config.frequencia_doc = request.POST.get('frequencia_doc', 'semanal')
            config.versoes_nuvem_doc = int(request.POST.get('versoes_nuvem_doc', 3))
            config.versoes_local_doc = int(request.POST.get('versoes_local_doc', 3))
            
            config.save()
            config.refresh_from_db()
            
            if not _validar_horarios_backup(config):
                messages.error(request, 'Os horários de backup devem ter pelo menos 30 minutos de diferença!')
                return redirect('backup_config')
            
            try:
                _atualizar_cron(config)
                messages.success(request, 'Configurações de backup salvas!')
            except Exception as e:
                messages.warning(request, f'Configurações salvas, mas erro ao atualizar agendamento: {str(e)}')
            
            return redirect('backup_config')
        
        elif acao == 'executar':
            if BackupHistorico.objects.filter(status='executando').exists():
                messages.warning(request, 'Já existe um backup em execução!')
                return redirect('backup_config')
            
            tipo_backup = request.POST.get('tipo_backup', '')
            if tipo_backup not in ('banco', 'documentos'):
                messages.error(request, 'Selecione o tipo de backup!')
                return redirect('backup_config')
            
            label = 'Banco de Dados' if tipo_backup == 'banco' else 'Documentos'
            
            backup = BackupHistorico.objects.create(
                tipo='manual',
                tipo_backup=tipo_backup,
                itens=tipo_backup,
                status='executando',
                arquivo_nome='',
                usuario=request.user,
            )
            
            subprocess.Popen(
                [
                    sys.executable, 'manage.py', 'executar_backup',
                    '--backup-id', str(backup.id),
                    '--tipo-backup', tipo_backup,
                    '--tipo', 'manual',
                ],
                cwd='/var/www/sistema_beneficios',
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            
            messages.success(request, f'Backup de {label} iniciado! Acompanhe nos logs.')
            return redirect('backup_logs')
        
        elif acao == 'testar_rclone':
            try:
                result = subprocess.run(
                    ['rclone', 'about', config.rclone_destino],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    messages.success(request, f'Conexão com {config.rclone_destino} OK!')
                else:
                    messages.error(request, f'Erro rclone: {result.stderr}')
            except subprocess.TimeoutExpired:
                messages.error(request, 'Timeout ao testar conexão.')
            except Exception as e:
                messages.error(request, f'Erro ao testar: {str(e)}')
            return redirect('backup_config')
    
    rclone_ok = None
    
    executando = BackupHistorico.objects.filter(status='executando').exists()
    
    context = {
        'config': config,
        'rclone_ok': rclone_ok,
        'executando': executando,
    }
    return render(request, 'beneficios/backup_config.html', context)


@login_required
def backup_logs(request):
    """Logs de backup (Super Admin e Admin)"""
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores!')
        return redirect('dashboard')
    
    from .models import BackupHistorico
    
    backups = BackupHistorico.objects.prefetch_related('logs').order_by('-data_inicio')
    
    f_status = request.GET.get('status', '').strip()
    f_tipo = request.GET.get('tipo', '').strip()
    f_tipo_backup = request.GET.get('tipo_backup', '').strip()
    
    if f_status:
        backups = backups.filter(status=f_status)
    if f_tipo:
        backups = backups.filter(tipo=f_tipo)
    if f_tipo_backup:
        backups = backups.filter(tipo_backup=f_tipo_backup)
    
    paginator = Paginator(backups, 15)
    page_number = request.GET.get('page', 1)
    backups_page = paginator.get_page(page_number)
    
    executando = BackupHistorico.objects.filter(status='executando').exists()
    
    context = {
        'backups': backups_page,
        'executando': executando,
        'filtros': {
            'status': f_status,
            'tipo': f_tipo,
            'tipo_backup': f_tipo_backup,
        }
    }
    return render(request, 'beneficios/backup_logs.html', context)

def _validar_horarios_backup(config):
    """Valida diferença mínima de 30 minutos entre agendamentos"""
    if not config.agendamento_db_ativo or not config.agendamento_doc_ativo:
        return True
    
    min_db = config.horario_db.hour * 60 + config.horario_db.minute
    min_doc = config.horario_doc.hour * 60 + config.horario_doc.minute
    diferenca = abs(min_db - min_doc)
    diferenca = min(diferenca, 1440 - diferenca)
    
    return diferenca >= 30