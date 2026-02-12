from django.shortcuts import redirect
from django.urls import reverse


class ForcarTrocaSenhaMiddleware:
    """Redireciona usuário para trocar senha se must_change_password=True"""
    
    URLS_PERMITIDAS = [
        '/trocar-senha/',
        '/logout/',
        '/static/',
        '/admin/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            if getattr(request.user, 'must_change_password', False):
                path = request.path
                if not any(path.startswith(url) for url in self.URLS_PERMITIDAS):
                    return redirect('trocar_senha')
        
        return self.get_response(request)
