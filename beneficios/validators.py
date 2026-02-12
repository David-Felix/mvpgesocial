import re
from django.core.exceptions import ValidationError


class SenhaForteValidator:
    """Valida senha com maiúscula, minúscula, número e caractere especial"""
    
    def validate(self, password, user=None):
        errors = []
        
        if not re.search(r'[A-Z]', password):
            errors.append('A senha deve conter pelo menos uma letra maiúscula.')
        
        if not re.search(r'[a-z]', password):
            errors.append('A senha deve conter pelo menos uma letra minúscula.')
        
        if not re.search(r'[0-9]', password):
            errors.append('A senha deve conter pelo menos um número.')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append('A senha deve conter pelo menos um caractere especial (!@#$%^&*...).')
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        return 'A senha deve conter: maiúscula, minúscula, número e caractere especial.'
