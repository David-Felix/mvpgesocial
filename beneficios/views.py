from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage
from .models import Pessoa, Beneficio, Documento
from .forms import PessoaForm, DocumentoForm
from django.db.models import Q, F, Sum, Func, Value, CharField, Count
from django.contrib.staticfiles import finders
from decimal import Decimal


@login_required
def dashboard(request):
    """Dashboard com overview financeiro e benefícios ativos"""
    
    # Benefícios ativos
    beneficios = Beneficio.objects.filter(ativo=True).order_by('id')
    
    # Estatísticas por benefício
    stats_list = []
    total_mensal_geral = 0
    
    # CORES E ÍCONES PADRÃO
    classes = ['benefit-card-azul', 'benefit-card-verde', 'benefit-card-turquesa', 'benefit-card-roxo']
    icones_padrao = ['bi-bus-front', 'bi-cash-coin', 'bi-wallet2', 'bi-piggy-bank']
    
    for idx, beneficio in enumerate(beneficios):
        stats = Pessoa.objects.filter(beneficio=beneficio).aggregate(
            total_pessoas=Count('id'),
            ativos=Count('id', filter=Q(ativo=True)),
            desativados=Count('id', filter=Q(ativo=False)),
            valor_mensal=Sum('valor_beneficio', filter=Q(ativo=True))
        )
        
        valor_mensal = stats['valor_mensal'] or 0
        valor_mensal_formatado = f"{valor_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # USAR ÍCONE DO BANCO OU PADRÃO
        icone = beneficio.icone if hasattr(beneficio, 'icone') and beneficio.icone else icones_padrao[idx % 4]
        
        stats_list.append({
            'id': beneficio.id,
            'nome': beneficio.nome,
            'icone': icone,  
            'cor_classe': classes[idx % len(classes)],  # Ciclo de 4 cores (0,1,2,3)
            'total': stats['total_pessoas'],
            'ativos': stats['ativos'],
            'desativados': stats['desativados'],
            'valor_mensal': float(valor_mensal),
            'valor_mensal_formatado': valor_mensal_formatado,
        })
        
        total_mensal_geral += valor_mensal

    # FORMATAR TOTAL MENSAL GERAL
    total_mensal_geral_formatado = f"{total_mensal_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    # Distribuição por faixa de valor
    pessoas_ativas = Pessoa.objects.filter(
        ativo=True,
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
    
    # Totais gerais
    todas_beneficios_ativos = Pessoa.objects.filter(beneficio__ativo=True)
    
    context = {
        'beneficios': stats_list,
        'total_mensal_geral': total_mensal_geral,
        'total_mensal_geral_formatado': total_mensal_geral_formatado,  # NOVO
        'total_geral': todas_beneficios_ativos.count(),
        'total_ativos_geral': todas_beneficios_ativos.filter(ativo=True).count(),
        'total_desativados_geral': todas_beneficios_ativos.filter(ativo=False).count(),
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
            
            # Salvar documento se enviado
            arquivo = form.cleaned_data.get('arquivo')
            if arquivo:
                Documento.objects.create(pessoa=pessoa, arquivo=arquivo)
            
            messages.success(request, f'Pessoa {pessoa.nome_completo} cadastrada com sucesso!')
            return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    else:
        form = PessoaForm()
    
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
    
    # Buscar documento de forma segura
    try:
        documento_atual = pessoa.documento
    except Documento.DoesNotExist:
        documento_atual = None
    
    if request.method == 'POST':
        form = PessoaForm(request.POST, request.FILES, instance=pessoa)
        if form.is_valid():
            form.save()
            
            # Atualizar documento se enviado novo arquivo
            arquivo = form.cleaned_data.get('arquivo')
            if arquivo:
                if documento_atual:
                    # Remove arquivo antigo do storage
                    documento_atual.arquivo.delete(save=False)
                    documento_atual.arquivo = arquivo
                    documento_atual.save()
                else:
                    Documento.objects.create(pessoa=pessoa, arquivo=arquivo)
            
            messages.success(request, f'Pessoa {pessoa.nome_completo} atualizada com sucesso!')
            return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    else:
        form = PessoaForm(instance=pessoa)
    
    context = {
        'form': form,
        'titulo': 'Editar Pessoa',
        'pessoa': pessoa,
        'documento_atual': documento_atual,
        'voltar_url': f'/beneficio/{pessoa.beneficio.id}/pessoas/'
    }
    return render(request, 'beneficios/pessoa_form.html', context)
    
    context = {
        'form': form,
        'titulo': 'Editar Pessoa',
        'pessoa': pessoa,
        'documento_atual': documento_atual,
        'voltar_url': f'/beneficio/{pessoa.beneficio.id}/pessoas/'
    }
    return render(request, 'beneficios/pessoa_form.html', context)

@login_required
def pessoa_toggle(request, pk):
    """Ativar/Desativar pessoa"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    pessoa.ativo = not pessoa.ativo
    pessoa.save()
    
    status = 'ativada' if pessoa.ativo else 'desativada'
    messages.success(request, f'Pessoa {pessoa.nome_completo} {status} com sucesso!')
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
def beneficio_edit(request, pk):
    """Editar benefício (modal/popup)"""
    beneficio = get_object_or_404(Beneficio, pk=pk)
    
    if request.method == 'POST':
        beneficio.conta_pagadora = request.POST.get('conta_pagadora', '')
        beneficio.save()
        messages.success(request, f'Benefício {beneficio.nome} atualizado!')
        return redirect('dashboard')
    
    return render(request, 'beneficios/beneficio_modal.html', {'beneficio': beneficio})


@login_required
def pessoas_por_beneficio(request, beneficio_id):
    """Lista pessoas de um benefício com filtros otimizados."""
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id)
    
    # Query Base
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio).select_related('documento').order_by('nome_completo')
        
    # Contagens dos Cards
    stats = pessoas_query.aggregate(
        ativos=Count('id', filter=Q(ativo=True)),
        desativados=Count('id', filter=Q(ativo=False)),
        total=Count('id'),
        total_mensal=Sum('valor_beneficio', filter=Q(ativo=True))
    )
    # Formatar total mensal
    total_mensal = stats['total_mensal'] or 0
    total_mensal_formatado = f"{total_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Distribuição por faixa de valor (apenas deste benefício)
    distribuicao_valor = pessoas_query.filter(ativo=True).aggregate(
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
    f_status = request.GET.get('status', '')
    f_valor = request.GET.get('valor', '').replace(',', '.')
    f_pos_de = request.GET.get('id_de', '').strip()
    f_pos_ate = request.GET.get('id_ate', '').strip()
    
    # Filtros no Banco
    pessoas_filtradas = pessoas_query
    
    if f_nome:
        pessoas_filtradas = pessoas_filtradas.filter(nome_completo__icontains=f_nome)
    
    if f_status == 'ativo':
        pessoas_filtradas = pessoas_filtradas.filter(ativo=True)
    elif f_status == 'desativado':
        pessoas_filtradas = pessoas_filtradas.filter(ativo=False)
    
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
            'total_desativados': stats['desativados'],
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
        'total_desativados': stats['desativados'],
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
    beneficios = Beneficio.objects.annotate(
        total_pessoas=Count('pessoa'),
        pessoas_ativas=Count('pessoa', filter=Q(pessoa__ativo=True)),
        pessoas_desligadas=Count('pessoa', filter=Q(pessoa__ativo=False))
    ).order_by('nome')
    
    context = {
        'beneficios': beneficios,
    }
    return render(request, 'beneficios/beneficios_list.html', context)

@login_required
def beneficio_create(request):
    """Criar novo benefício"""
    if request.method == 'POST':
        nome = request.POST.get('nome')
        conta_pagadora = request.POST.get('conta_pagadora', '')
        icone = request.POST.get('icone', 'bi-wallet2')
        
        if nome:
            Beneficio.objects.create(nome=nome, conta_pagadora=conta_pagadora, icone=icone)
            messages.success(request, f'Benefício {nome} criado com sucesso!')
            return redirect('beneficios_list')
        else:
            messages.error(request, 'Nome do benefício é obrigatório!')
    
    return render(request, 'beneficios/beneficio_form.html', {'titulo': 'Novo Benefício'})

@login_required
def beneficio_edit_form(request, pk):
    """Editar benefício"""
    beneficio = get_object_or_404(Beneficio, pk=pk)
    
    if request.method == 'POST':
        beneficio.nome = request.POST.get('nome', beneficio.nome)
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
    usuarios = User.objects.all().order_by('username')
    
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
    
    if usuario == request.user:
        messages.error(request, 'Você não pode desativar sua própria conta!')
        return redirect('usuarios_list')
    
    usuario.is_active = not usuario.is_active
    usuario.save()
    
    status = 'ativado' if usuario.is_active else 'desativado'
    messages.success(request, f'Usuário {usuario.username} {status}!')
    return redirect('usuarios_list')
# views.py - adicionar novas views

@login_required
def gerar_recibo(request, pk):
    """Gera apenas 2 vias do recibo (sem documentos)"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    
    if not pessoa.ativo:
        messages.error(request, 'Não é possível gerar recibo de pessoa desativada!')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    
    try:
        from .utils import gerar_recibo_paginas_separadas
        pdf_buffer = gerar_recibo_paginas_separadas(pessoa)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="recibo_{pessoa.cpf}.pdf"'
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
    """Gera memorando com nome e CPF"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    
    if not pessoa.ativo:
        messages.error(request, 'Não é possível gerar memorando de pessoa desativada!')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)
    
    try:
        from .utils import gerar_memorando_pdf
        pdf_buffer = gerar_memorando_pdf(pessoa)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="memorando_{pessoa.cpf}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f'Erro ao gerar memorando: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=pessoa.beneficio.id)


@login_required
def gerar_memorando_massa(request, beneficio_id):
    """Gera memorando em massa respeitando os filtros aplicados"""
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id)
    
    # Aplica os mesmos filtros da listagem
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio, ativo=True).order_by('nome_completo')
    
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
    
    if f_status == 'desativado':
        pessoas_query = pessoas_query.filter(ativo=False)
    elif not f_status:
        pessoas_query = pessoas_query.filter(ativo=True)
    
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
        from .utils import gerar_memorando_massa_pdf
        pdf_buffer = gerar_memorando_massa_pdf(beneficio, pessoas)
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="memorando_massa_{beneficio.nome}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f'Erro ao gerar memorando em massa: {str(e)}')
        return redirect('pessoas_por_beneficio', beneficio_id=beneficio_id)

@login_required
def gerar_recibos_massa(request, beneficio_id):
    """Gera recibos em massa (2 vias para cada pessoa) respeitando os filtros aplicados"""
    beneficio = get_object_or_404(Beneficio, pk=beneficio_id)
    
    # Aplica os mesmos filtros da listagem
    pessoas_query = Pessoa.objects.filter(beneficio=beneficio, ativo=True).order_by('nome_completo')
    
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
    
    if f_status == 'desativado':
        pessoas_query = pessoas_query.filter(ativo=False)
    elif not f_status:
        pessoas_query = pessoas_query.filter(ativo=True)
    
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