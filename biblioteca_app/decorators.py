from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if hasattr(request.user, "perfil") and request.user.perfil.funcao == "administrador":
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "Acesso restrito a administradores.")
        return redirect("home")  
    return wrapper
