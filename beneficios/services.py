from datetime import datetime
from django.db import transaction
from .models import Memorando, MemorandoPessoa


def gerar_numero_memorando():
    """Gera próximo número de memorando no formato 00001/2026"""
    ano_atual = datetime.now().year
    
    with transaction.atomic():
        ultimo = Memorando.objects.filter(ano=ano_atual).order_by('-sequencia').first()
        proxima_sequencia = (ultimo.sequencia + 1) if ultimo else 1
        numero = f"{proxima_sequencia:05d}/{ano_atual}"
        
    return numero, ano_atual, proxima_sequencia


def registrar_memorando(beneficio, pessoas_dados, usuario):
    """
    Registra memorando no histórico com snapshot dos dados.
    
    Args:
        beneficio: objeto Beneficio
        pessoas_dados: lista de dicts com {pessoa, nome_completo, cpf, valor_beneficio, ordem}
        usuario: objeto User que gerou
    
    Returns:
        objeto Memorando criado
    """
    from .models import ConfiguracaoGeral
    
    numero, ano, sequencia = gerar_numero_memorando()
    config = ConfiguracaoGeral.get_config()
    
    valor_total = sum(p['valor_beneficio'] for p in pessoas_dados)
    conta_pagadora = getattr(beneficio, 'conta_pagadora', '')
    
    with transaction.atomic():
        memorando = Memorando.objects.create(
            numero=numero,
            ano=ano,
            sequencia=sequencia,
            beneficio=beneficio,
            conta_pagadora=conta_pagadora,
            valor_total=valor_total,
            quantidade_pessoas=len(pessoas_dados),
            usuario=usuario,
            # Snapshot das configurações
            secretaria_nome=config.secretaria_nome,
            secretaria_cargo=config.secretaria_cargo,
            financas_nome=config.financas_nome,
            financas_cargo=config.financas_cargo,
            email_institucional=config.email_institucional,
            endereco=config.endereco,
            cep=config.cep,
        )
        
        # Criar snapshot de cada pessoa
        for dados in pessoas_dados:
            MemorandoPessoa.objects.create(
                memorando=memorando,
                pessoa=dados.get('pessoa'),
                nome_completo=dados['nome_completo'],
                valor_beneficio=dados['valor_beneficio'],
                ordem=dados['ordem']
            )
    
    return memorando