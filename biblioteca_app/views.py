from django.db.models import Q, Count, F, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db import IntegrityError
from django.contrib import messages
from .models import Livro, Exemplar, Leitor, Emprestimo, Devolucao, Configuracao, PerfilUsuario, Autor, Editora, Genero
from django.utils import timezone
from datetime import datetime, date
import decimal, json, base64
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST 
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from .decorators import admin_required
from . import services

# --- Funções Auxiliares (Regras de Negócio Extraídas) ---
def _validar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, str(cpf)))
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for i in range(9, 11):
        value = sum((int(cpf[num]) * ((i+1) - num) for num in range(0, i)))
        digit = ((value * 10) % 11) % 10
        if digit != int(cpf[i]):
            return False
    return True

def _calcular_valor_multa(emprestimo, data_base=None):
    if not data_base:
        data_base = date.today()
    config = Configuracao.objects.first()
    valor_por_dia = decimal.Decimal(str(config.multa_por_dia)) if config else decimal.Decimal('2.50')
    if data_base > emprestimo.data_devolucao:
        dias_atraso = (data_base - emprestimo.data_devolucao).days
        return valor_por_dia * dias_atraso
    return decimal.Decimal('0.00')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            try:
                perfil = user.perfil  
            except PerfilUsuario.DoesNotExist:
                if user.is_superuser:
                    # Resolve a falta de perfil para superusuários criados no terminal
                    fake_cpf = f"00000000{user.id:03d}"
                    perfil = PerfilUsuario.objects.create(
                        user=user,
                        email=user.email or f"{user.username}@sistema.local",
                        cpf=fake_cpf,
                        endereco="Acesso via Terminal",
                        funcao="administrador"
                    )
                else:
                    perfil = None

            if perfil:
                request.session['funcao'] = perfil.funcao
            else:
                request.session['funcao'] = None
                
            return redirect('home')
        else:
            messages.error(request, 'Usuário ou senha inválidos. Tente novamente.')
            return render(request, 'login.html')

    return render(request, 'login.html')

@login_required(login_url='login_view')
def home(request):
    hoje = timezone.now().date()
    
    query = request.GET.get('q')
    
    if query:
        
        livros = Livro.objects.filter(
            Q(titulo__icontains=query) |
            Q(autor__nome__icontains=query) | 
            Q(genero__nome__icontains=query)  
        ).distinct() 
    else:
        livros = Livro.objects.all()
        
    total_livros = Livro.objects.count()
    leitores_ativos = Leitor.objects.filter(ativo=True).count()
    emprestimos_ativos = Emprestimo.objects.filter(devolucao__isnull=True).count()
    devolucoes_atrasadas = Emprestimo.objects.filter(devolucao__isnull=True, data_devolucao__lt=hoje).count()
    
    context = {
        'livros': livros,
        'total_livros': total_livros,
        'leitores_ativos': leitores_ativos,
        'emprestimos_ativos': emprestimos_ativos,
        'devolucoes_atrasadas': devolucoes_atrasadas
    }
    return render(request, 'home.html', context)

def excluir_usuario(request, user_id):
    if request.method == 'POST':
        try:
            usuario_a_excluir = get_object_or_404(User, id=user_id)

            if usuario_a_excluir == request.user:
                messages.error(request, 'Você não pode excluir a sua própria conta.')
            else:
                usuario_a_excluir.delete()
                messages.success(request, f'Usuário {usuario_a_excluir.username} excluído com sucesso!')
        except Exception as e:
            messages.error(request, f'Erro ao excluir o usuário: {e}')
    
    return redirect('configuracao_contas')

@admin_required
def configuracao_multa(request):
    if request.method == 'POST' and request.POST.get('form-action') == 'salvar-multa':
        valor_multa_str = request.POST.get('multa-por-dia')
        if valor_multa_str:
            config, created = Configuracao.objects.get_or_create(pk=1)
            config.multa_por_dia = valor_multa_str
            config.save()
            messages.success(request, 'Valor da multa atualizado com sucesso!')
        return redirect('configuracao_multa')

    multa_por_dia = Configuracao.objects.first().multa_por_dia if Configuracao.objects.exists() else 2.50
    return render(request, 'valor_multa.html', {'multa_por_dia': multa_por_dia})

@admin_required
def configuracao_contas(request):
    if request.method == 'POST' and request.POST.get('form-action') == 'editar-usuario':
        usuario_id = request.POST.get('usuario_id')
        user = get_object_or_404(User, id=usuario_id)

        email = request.POST.get('email')
        endereco = request.POST.get('endereco')
        perfil, created = PerfilUsuario.objects.get_or_create(user=user)

        if email and endereco:
            user.email = email
            user.save()
            perfil.email = email
            perfil.endereco = endereco
            perfil.save()
            
            messages.success(request, 'Usuário atualizado com sucesso!')
        else:
            messages.error(request, 'Erro: E-mail e Endereço são obrigatórios.')
            
        return redirect('configuracao_contas')

    usuarios_cadastrados = User.objects.all().select_related('perfil')
    return render(request, 'contas.html', {'usuarios_cadastrados': usuarios_cadastrados})

@admin_required
def configuracao_cadastro(request):
    if request.method == 'POST' and request.POST.get('form-action') == 'cadastro-usuario':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        cpf = request.POST.get('cpf')
        endereco = request.POST.get('endereco')
        funcao = request.POST.get('funcao')  

        if username and password and email and cpf and endereco and funcao:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Nome de usuário já existe.')
            elif PerfilUsuario.objects.filter(cpf=cpf).exists():
                messages.error(request, 'CPF já cadastrado.')
            else:
                user = User.objects.create_user(username=username, password=password, email=email)
                PerfilUsuario.objects.create(
                    user=user,
                    email=email,
                    cpf=cpf,
                    endereco=endereco,
                    funcao=funcao  
                )
                messages.success(request, 'Usuário cadastrado com sucesso!')
        return redirect('configuracao_cadastro')

    return render(request, 'cadastro.html')

def livro_detalhes(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    
    emprestimos_ativos = Emprestimo.objects.filter(exemplar__livro=livro, devolucao__isnull=True).count()
    disponivel = Exemplar.objects.filter(livro=livro, status='disponivel').exists()
    
    data_devolucao_proxima = None
    if not disponivel:
        emprestimos_pendentes = Emprestimo.objects.filter(exemplar__livro=livro, devolucao__isnull=True).order_by('data_devolucao')
        if emprestimos_pendentes.exists():
            data_devolucao_proxima = emprestimos_pendentes.first().data_devolucao
    
    context = {
        'livro': livro,
        'disponivel': disponivel,
        'data_devolucao_proxima': data_devolucao_proxima,
        'exemplares': livro.exemplares.all()
    }
    return render(request, 'livro_detalhes.html', context)

def cadastro_livros(request):
    if request.method == 'POST':
        services.criar_livro_com_exemplares(
            titulo=request.POST.get('titulo'),
            autor_nome=request.POST.get('autor'),
            edicao=request.POST.get('edicao'),
            numero_paginas=request.POST.get('numero_paginas'),
            genero_nome=request.POST.get('genero'),
            classificacao=request.POST.get('classificacao'),
            sinopse=request.POST.get('sinopse'),
            capa=request.FILES.get('capa'),
            imagens_adicionais=request.FILES.getlist('imagens_adicionais'),
            quantidade=int(request.POST.get('quantidade', 1)),
            editora_nome=request.POST.get('editora'),
            idioma=request.POST.get('idioma'),
            data_publicacao=request.POST.get('data_publicacao') or None,
            localizacao=request.POST.get('localizacao')
        )
        messages.success(request, 'Livro cadastrado com sucesso!')
    
    context = {
        'quantidades': range(1, 51),
        'generos': Genero.objects.all().order_by('nome')
    }
    return render(request, 'cadastro_livros.html', context)

@admin_required
def editar_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    if request.method == 'POST':
        livro.titulo = request.POST.get('titulo-edicao', livro.titulo)
        livro.edicao = request.POST.get('edicao-edicao', livro.edicao)
        livro.numero_paginas = request.POST.get('numero_paginas-edicao', livro.numero_paginas)
        
        idioma = request.POST.get('idioma-edicao')
        if idioma:
            livro.idioma = idioma
            
        data_pub = request.POST.get('data_publicacao-edicao')
        livro.data_publicacao = data_pub if data_pub else None
            
        classificacao = request.POST.get('classificacao-edicao')
        if classificacao:
            livro.classificacao = classificacao
            
        sinopse = request.POST.get('sinopse-edicao')
        if sinopse:
            livro.sinopse = sinopse
        
        autor_nome = request.POST.get('autor-edicao', '').strip()
        if autor_nome:
            livro.autor, _ = Autor.objects.get_or_create(nome=autor_nome)

        genero_nome = request.POST.get('genero-edicao', '').strip()
        if genero_nome:
            livro.genero, _ = Genero.objects.get_or_create(nome=genero_nome)

        editora_nome = request.POST.get('editora-edicao', '').strip()
        if editora_nome:
            livro.editora, _ = Editora.objects.get_or_create(nome=editora_nome)
        else:
            livro.editora = None

        if 'capa-nova-edicao' in request.FILES:
            livro.capa = request.FILES['capa-nova-edicao']
            
        livro.save()
        messages.success(request, f'O livro "{livro.titulo}" foi atualizado.')
        return redirect('estoque')
    
    return redirect('estoque')

@admin_required
@require_POST
def excluir_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    try:
        titulo_livro = livro.titulo
        livro.delete()
        messages.success(request, f'O livro "{titulo_livro}" foi excluído com sucesso.')
    except IntegrityError:
        messages.error(request, f'Não é possível excluir o livro "{livro.titulo}" pois ele está associado a um empréstimo.')
    
    return redirect('estoque')

def estoque(request):
    query = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', 'livre')
    
    livros_base = Livro.objects.all()

    if query:
        if filtro == 'titulo':
            livros_base = livros_base.filter(titulo__icontains=query)
        elif filtro == 'autor':
            livros_base = livros_base.filter(autor__nome__icontains=query)
        elif filtro == 'editora':
            livros_base = livros_base.filter(editora__nome__icontains=query)
        elif filtro == 'genero':
            livros_base = livros_base.filter(genero__nome__icontains=query)
        else:
            livros_base = livros_base.filter(
                Q(titulo__icontains=query) |
                Q(autor__nome__icontains=query) | 
                Q(editora__nome__icontains=query) | 
                Q(genero__nome__icontains=query)  
            ).distinct()

    livros_cadastrados = livros_base.annotate(
        total_exemplares=Count('exemplares', distinct=True),
        emprestados=Count('exemplares__emprestimo', filter=Q(exemplares__emprestimo__devolucao__isnull=True), distinct=True)
    ).annotate(
        disponiveis=F('total_exemplares') - F('emprestados') 
    )
    
    context = {
        'livros': livros_cadastrados,
        'query': query, 
        'filtro': filtro,
    }
    return render(request, 'estoque.html', context)

def cadastro_leitor(request):
    if request.method == 'POST':
        id_leitor_post = request.POST.get('id_leitor')
        email_post = request.POST.get('email')
        cpf_post = request.POST.get('cpf') 
        
        cpf_limpo = ''.join(filter(str.isdigit, str(cpf_post))) 

        if not _validar_cpf(cpf_limpo):
            messages.error(request, 'CPF inválido. Verifique os números digitados.', extra_tags="erro")
            return redirect('cadastro_leitor')
            
        if Leitor.objects.filter(id_leitor=id_leitor_post).exists():
            messages.error(request, 'Este ID de Leitor já está cadastrado no sistema.', extra_tags="erro")
            return redirect('cadastro_leitor')
 
        if Leitor.objects.filter(email=email_post).exists():
            messages.error(request, 'Este endereço de e-mail já está cadastrado para outro leitor.', extra_tags="erro")
            return redirect('cadastro_leitor')
        
        if Leitor.objects.filter(cpf=cpf_limpo).exists():
            messages.error(request, 'Este CPF já está cadastrado para outro leitor.', extra_tags="erro")
            return redirect('cadastro_leitor')


        novo_leitor = Leitor()
        novo_leitor.id_leitor = id_leitor_post
        novo_leitor.nome = request.POST.get('nome')
        novo_leitor.data_nascimento = request.POST.get('data_nascimento')
        novo_leitor.celular = request.POST.get('celular')
        novo_leitor.cpf = cpf_limpo
        novo_leitor.email = email_post
        novo_leitor.cep = request.POST.get('cep')
        novo_leitor.endereco = request.POST.get('endereco')
        novo_leitor.complemento = request.POST.get('complemento')
        novo_leitor.cidade = request.POST.get('cidade')
        novo_leitor.recebimento_alertas = 'recebimento_alertas' in request.POST
        
        # Verifica se uma foto foi tirada via câmera (Base64)
        foto_base64 = request.POST.get('foto_base64')
        if foto_base64:
            try:
                format, imgstr = foto_base64.split(';base64,')
                ext = format.split('/')[-1]
                novo_leitor.foto.save(f"leitor_{cpf_limpo}.{ext}", ContentFile(base64.b64decode(imgstr)), save=False)
            except Exception as e:
                messages.warning(request, f'Aviso: Não foi possível processar a foto da câmera ({str(e)}).')

        try:
            novo_leitor.save()
            messages.success(request, 'Leitor cadastrado com sucesso!', extra_tags="sucesso")
        except IntegrityError:
            messages.error(request, 'Erro de integridade no banco de dados (Ex: CPF ou Email duplicado).', extra_tags="erro")
        
        return redirect('cadastro_leitor')
    
    return render(request, 'cadastro_leitor.html')

@admin_required
def editar_leitor(request, leitor_id):
    leitor = get_object_or_404(Leitor, pk=leitor_id)
    if request.method == 'POST':
        novo_id = request.POST.get('id_leitor-edicao')
        if novo_id and novo_id != leitor.id_leitor:
            if Leitor.objects.filter(id_leitor=novo_id).exists():
                messages.error(request, 'Este ID de Leitor já está em uso.')
                return redirect(request.META.get('HTTP_REFERER', 'leitores'))
            leitor.id_leitor = novo_id

        leitor.nome = request.POST.get('nome-edicao')
        leitor.celular = request.POST.get('celular-edicao')
        leitor.email = request.POST.get('email-edicao')
        leitor.cep = request.POST.get('cep-edicao')
        leitor.endereco = request.POST.get('endereco-edicao')
        leitor.complemento = request.POST.get('complemento-edicao')
        leitor.cidade = request.POST.get('cidade-edicao')
        leitor.save()
        messages.success(request, f'Dados de "{leitor.nome}" atualizados.')
        return redirect(request.META.get('HTTP_REFERER', 'leitores'))
    
    return redirect('leitores')

@admin_required
@require_POST 
def excluir_leitor(request, leitor_id):
    leitor = get_object_or_404(Leitor, pk=leitor_id)
    try:
        nome_leitor = leitor.nome
        leitor.delete()
        messages.success(request, f'O leitor "{nome_leitor}" foi excluído com sucesso.')
    except IntegrityError:
        messages.error(request, f'Não é possível excluir o leitor "{leitor.nome}" pois ele possui empréstimos ativos.')
    return redirect('leitores')

def usuarios(request):
    query = request.GET.get('q')
    
    if query:
        leitores = Leitor.objects.filter(
            Q(nome__icontains=query) |
            Q(email__icontains=query)
        ).distinct()
    else:
        leitores = Leitor.objects.all()

    context = {
        'leitores': leitores,
        'query': query, 
    }
    return render(request, 'leitores.html', context)

def emprestimo(request):
    if request.method == 'POST':
        id_leitor_post = request.POST.get('id_leitor') 
        tombo_post = request.POST.get('codigo_tombo')
        data_emprestimo_str = request.POST.get('data_emprestimo')
        data_devolucao_str = request.POST.get('data_devolucao')

        if not all([id_leitor_post, tombo_post, data_emprestimo_str, data_devolucao_str]):
            messages.error(request, "Todos os campos são obrigatórios.", extra_tags="erro")
            return redirect('emprestimo')

        try:
            data_emprestimo_obj = datetime.strptime(data_emprestimo_str, '%Y-%m-%d').date()
            data_devolucao_obj = datetime.strptime(data_devolucao_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Formato de data inválido.", extra_tags="erro")
            return redirect('emprestimo')
            
        if data_devolucao_obj < data_emprestimo_obj:
            messages.error(
                request, 
                "A data de devolução não pode ser anterior à data de empréstimo.", 
                extra_tags="erro"
            )
            return redirect('emprestimo')

        try:
            leitor = Leitor.objects.get(id_leitor=id_leitor_post) 
        except Leitor.DoesNotExist:
            messages.error(request, "ID do Leitor não encontrado.", extra_tags="erro")
            return redirect('emprestimo')

        try:
            exemplar = Exemplar.objects.get(codigo_tombo=tombo_post)
        except Exemplar.DoesNotExist:
            messages.error(request, "Código de Tombo não encontrado.", extra_tags="erro")
            return redirect('emprestimo')

        try:
            services.realizar_emprestimo(
                leitor=leitor, exemplar=exemplar, data_emprestimo=data_emprestimo_obj,
                data_devolucao=data_devolucao_obj, usuario=request.user if request.user.is_authenticated else None
            )
            messages.success(request, "Empréstimo registrado com sucesso.", extra_tags="sucesso")
        except ValueError as e:
            messages.error(request, str(e), extra_tags="erro")
            
        return redirect('emprestimo')

    livros_cadastrados = Livro.objects.annotate(disp=Count('exemplares', filter=Q(exemplares__status='disponivel'))).filter(disp__gt=0)
    return render(request, 'emprestimo.html', {'livros': livros_cadastrados})

def emprestimo_com_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    exemplares_disponiveis = Exemplar.objects.filter(livro=livro, status='disponivel')
    
    if not exemplares_disponiveis.exists():
        messages.error(request, f'O livro "{livro.titulo}" não está disponível para empréstimo no momento.')
        return redirect('livro_detalhes', livro_id=livro.id) 

    context = {
        'livro_pre_selecionado': livro,
        'exemplares_disponiveis': exemplares_disponiveis
    }
    return render(request, 'emprestimo.html', context)

def reservas(request):
    query = request.GET.get('q') 
    
    emprestimos_base = Emprestimo.objects.exclude(
        pk__in=Devolucao.objects.values('emprestimo_id')
    )
    
    if query:
        emprestimos_ativos = emprestimos_base.filter(
            Q(exemplar__livro__titulo__icontains=query) |
            Q(exemplar__livro__autor__nome__icontains=query) |
            Q(leitor__nome__icontains=query)
        ).order_by('data_devolucao')
    else:
        emprestimos_ativos = emprestimos_base.order_by('data_devolucao')

    hoje = date.today()

    for emprestimo in emprestimos_ativos:
        valor_multa = _calcular_valor_multa(emprestimo, hoje)
        emprestimo.atrasado = valor_multa > 0
        emprestimo.valor_multa = f"{valor_multa:.2f}"

    context = {
        'emprestimos': emprestimos_ativos
    }
    return render(request, 'reservas.html', context)

def calcular_multa(request):
    emprestimo_id = request.GET.get('emprestimo_id')
    data_entrega_str = request.GET.get('data_entrega') 
    emprestimos_ativos = Emprestimo.objects.exclude(
        pk__in=Devolucao.objects.values('emprestimo_id')
    ).order_by('data_devolucao')

    try:
        emprestimo = get_object_or_404(Emprestimo, pk=emprestimo_id)
        if data_entrega_str:
            data_entrega = datetime.datetime.strptime(data_entrega_str, '%Y-%m-%d').date()
        else:
            data_entrega = datetime.date.today() 
        
        valor_multa = _calcular_valor_multa(emprestimo, data_entrega)
        atraso = valor_multa > 0

        return JsonResponse({
            'valor_multa': f'{valor_multa:.2f}',
            'atraso': atraso
        })
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)

def devolver_livro(request, emprestimo_id):
    if request.method == "POST":
        emprestimo = get_object_or_404(Emprestimo, pk=emprestimo_id)
        data_entrega_str = request.POST.get("data_entrega")
        valor_multa_post_str = request.POST.get("valor_multa", "0.00") 

        try:
            data_entrega = datetime.strptime(data_entrega_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Data de entrega inválida.")
            return redirect("reservas")

        multa_devida = _calcular_valor_multa(emprestimo, data_entrega)

        multa_foi_paga = False
        valor_a_registrar = multa_devida 
        
        if multa_devida > 0:
            if valor_multa_post_str == "0.00":
                multa_foi_paga = True 
                
            else:
                multa_foi_paga = False 
                valor_a_registrar = decimal.Decimal(valor_multa_post_str)

        else:
            multa_foi_paga = True
            valor_a_registrar = decimal.Decimal('0.00')


        devolucao = Devolucao.objects.create(
            emprestimo=emprestimo,
            data_devolucao_real=data_entrega,
            valor_multa=valor_a_registrar, 
            multa_paga=multa_foi_paga 
        )

        emprestimo.devolvido = True 
        emprestimo.devolucao = devolucao
        emprestimo.save()

        messages.success(request, f"O livro '{emprestimo.livro.titulo}' foi devolvido com sucesso!")
        return redirect("reservas")

    messages.error(request, "Método inválido para devolução.")
    return redirect("reservas")

def multa(request):
    query = request.GET.get('q')
    
    if query:
        livros_base = Livro.objects.filter(
            Q(titulo__icontains=query) |
            Q(autor__nome__icontains=query) | 
            Q(genero__nome__icontains=query)  
        ).distinct()
    else:
        livros_base = Livro.objects.all()

    devolucoes_com_multa = []
    hoje = date.today()
    
    emprestimos_atrasados = Emprestimo.objects.filter(
        data_devolucao__lt=hoje, 
        devolucao__isnull=True
    )
    
    total_multas_aberto = decimal.Decimal('0.00')

    for emprestimo in emprestimos_atrasados:
        valor_multa_temp = _calcular_valor_multa(emprestimo, hoje)
        total_multas_aberto += valor_multa_temp 
        emprestimo.valor_multa_temp = valor_multa_temp
        devolucoes_com_multa.append(emprestimo)

    multas_arrecadadas_valor = Devolucao.objects.aggregate(
        total_arrecadado=Sum('valor_multa') 
    )['total_arrecadado']
    
    multas_arrecadadas = multas_arrecadadas_valor if multas_arrecadadas_valor else decimal.Decimal('0.00')

    context = {
        'devolucoes': devolucoes_com_multa,
        'total_multas_aberto': total_multas_aberto,
        'multas_arrecadadas': multas_arrecadadas,
    }

    return render(request, 'relatorio_multa.html', context)

def buscar_leitor(request):
    id_leitor = request.GET.get('id_leitor', '').strip()
    if not id_leitor:
        return JsonResponse({'erro': 'ID do Leitor não fornecido'}, status=400)
    
    try:
        leitor = Leitor.objects.get(id_leitor=id_leitor)
        tem_multa = Emprestimo.objects.filter(
            leitor=leitor, devolucao__isnull=True, data_devolucao__lt=date.today()
        ).exists()
        
        return JsonResponse({'nome': leitor.nome, 'tem_multa': tem_multa})
    except Leitor.DoesNotExist:
        return JsonResponse({'erro': 'Leitor não encontrado'}, status=404)

def buscar_livro(request):
    titulo = request.GET.get('titulo')
    if not titulo:
        return JsonResponse({'erro': 'O título do livro não foi fornecido.'}, status=400)

    try:
        
        livro = Livro.objects.filter(titulo__icontains=titulo).first() 
        
        if livro:
            response_data = {
                'titulo': livro.titulo,
                'autor': livro.autor.nome,
                'edicao': livro.edicao,
                'editora': livro.editora.nome if livro.editora else '',
                'idioma': livro.idioma,
                'data_publicacao': livro.data_publicacao,
                'numero_paginas': livro.numero_paginas,
                'genero' : livro.genero.nome,
                'classificacao' : livro.classificacao,
                'capa': livro.capa.url if livro.capa else None
            }
            return JsonResponse(response_data)
        else:
            return JsonResponse({'erro': 'Livro não encontrado'}, status=404)
    except Exception as e:
        
        return JsonResponse({'erro': str(e)}, status=500)

def buscar_leitor_por_id(request):
    leitor_id = request.GET.get('id')
    
    try:
        leitor = Leitor.objects.get(pk=leitor_id)
        
        response_data = {
            'nome': leitor.nome,
            'celular': leitor.celular,
            'email': leitor.email,
            'cep': leitor.cep,
            'endereco': leitor.endereco,
            'complemento': leitor.complemento or '', 
            'cidade': leitor.cidade,
        }
        return JsonResponse(response_data)
    except Leitor.DoesNotExist:
        return JsonResponse({'erro': 'Leitor não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)

def buscar_livro_por_id(request):
    livro_id = request.GET.get('id')
    
    try:
        livro = Livro.objects.get(pk=livro_id)
        
        response_data = {
            'titulo': livro.titulo,
            'autor': livro.autor.nome,
            'genero': livro.genero.nome,
            'classificacao': livro.classificacao,
                'quantidade': livro.exemplares.count(),
            'edicao': livro.edicao,
            'editora': livro.editora.nome if livro.editora else '',
            'idioma': livro.idioma,
            'data_publicacao': livro.data_publicacao,
            'numero_paginas': livro.numero_paginas,
            'sinopse': livro.sinopse,
            'capa_url': livro.capa.url if livro.capa else None
        }
        return JsonResponse(response_data)
    except Livro.DoesNotExist:
        return JsonResponse({'erro': 'Livro não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)

def buscar_livro_completo(request):
    titulo = request.GET.get('titulo')
    try:
        livro = Livro.objects.filter(titulo__icontains=titulo).first() 
        if not livro:
            return JsonResponse({'erro': 'Livro não encontrado'}, status=404)
        
        quantidade_disponivel = Exemplar.objects.filter(livro=livro, status='disponivel').count()
        disponivel = quantidade_disponivel > 0

        data_devolucao_proxima = None
        if not disponivel:
            emprestimo_mais_proximo = Emprestimo.objects.filter(exemplar__livro=livro, devolucao__isnull=True).order_by('data_devolucao').first()
            if emprestimo_mais_proximo and emprestimo_mais_proximo.data_devolucao:
                data_devolucao_proxima = emprestimo_mais_proximo.data_devolucao.strftime("%d/%m/%Y")

        response_data = {
            'disponivel': disponivel,
            'quantidade_disponivel': quantidade_disponivel,
            'data_devolucao_proxima': data_devolucao_proxima,
            'titulo': livro.titulo,
            'autor': livro.autor.nome,
            'edicao': livro.edicao,
            'numero_paginas': livro.numero_paginas,
            'genero': livro.genero.nome,
            'classificacao': livro.classificacao,
            'capa': livro.capa.url if livro.capa else None
        }
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)

def buscar_exemplar(request):
    tombo = request.GET.get('tombo', '').strip()
    try:
        exemplar = Exemplar.objects.get(codigo_tombo=tombo)
        livro = exemplar.livro
        
        response_data = {
            'titulo': livro.titulo,
            'autor': livro.autor.nome,
            'edicao': livro.edicao,
            'numero_paginas': livro.numero_paginas,
            'genero': livro.genero.nome,
            'classificacao': livro.classificacao,
            'capa': livro.capa.url if livro.capa else None,
            'status': exemplar.status,
            'status_display': exemplar.get_status_display()
        }
        return JsonResponse(response_data)
    except Exemplar.DoesNotExist:
        return JsonResponse({'erro': 'Exemplar físico não encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)

def relatorio(request):
    query = request.GET.get('q')
    
    if query:
        livros_base = Livro.objects.filter(
            Q(titulo__icontains=query) |
            Q(autor__nome__icontains=query) | 
            Q(genero__nome__icontains=query)  
        ).distinct()
    else:
        livros_base = Livro.objects.all()

    livros_emprestados = livros_base.annotate(
            total_emprestimos=Count('exemplares__emprestimo') 
    ).order_by('-total_emprestimos', 'titulo')

    livros_emprestados = livros_emprestados.filter(total_emprestimos__gt=0) 
    total_emprestimos_feitos = Emprestimo.objects.count()
    total_devolvidos = Devolucao.objects.count()

    percentual_devolvidos = 0
    if total_emprestimos_feitos > 0:
        percentual_devolvidos = (total_devolvidos / total_emprestimos_feitos) * 100
    
    usuario_ativo = request.user 

    context = {
        'livros_emprestados': livros_emprestados, 
        'total_emprestimos_feitos': total_emprestimos_feitos,
        'total_devolvidos': total_devolvidos,
        'percentual_devolvidos': f'{percentual_devolvidos:.2f}', 
        'query': query, 
    }
    return render(request, 'relatorio.html', context)

# --- PLACEHOLDERS PARA AS NOVAS TELAS DO SISTEMA ---

@login_required(login_url='login_view')
def fila_reservas(request):
    return render(request, 'fila_reservas.html') # A ser criado na próxima etapa

@login_required(login_url='login_view')
def renovacao(request):
    return render(request, 'renovacao.html') # A ser criado na próxima etapa

@login_required(login_url='login_view')
def historico_leitor(request, leitor_id):
    leitor = get_object_or_404(Leitor, pk=leitor_id)
    emprestimos = Emprestimo.objects.filter(leitor=leitor).order_by('-data_emprestimo')
    context = {
        'leitor': leitor,
        'emprestimos': emprestimos
    }
    return render(request, 'historico_leitor.html', context)

@admin_required
def historico_financeiro(request):
    return render(request, 'historico_financeiro.html') # A ser criado na próxima etapa