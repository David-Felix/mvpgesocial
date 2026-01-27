from .models import Beneficio

def beneficios_ativos(request):
    """Disponibiliza benefícios ativos em todos os templates"""
    if request.user.is_authenticated:
        return {
            'beneficios_menu': Beneficio.objects.filter(ativo=True).only('id', 'nome', 'icone').order_by('nome')
        }
    return {}