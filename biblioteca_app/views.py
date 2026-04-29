from django.db.models import Q, Count, F, Sum, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db import IntegrityError
from django.contrib import messages
from .models import Livro, Exemplar, Leitor, Emprestimo, Devolucao, Configuracao, PerfilUsuario, Autor, Editora, Genero, Reserva
from django.utils import timezone
from datetime import datetime, date
import decimal, json, base64, logging
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST 
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, get_user_model
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from .decorators import admin_required
from . import services
from .forms import LeitorForm, LivroCadastroForm, LeitorEditForm, LivroEditForm

logger = logging.getLogger(__name__)

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
    config, created = Configuracao.objects.get_or_create(pk=1)
    
    if request.method == 'POST':
        action = request.POST.get('form-action')
        
        if action == 'salvar-multa':
            valor_multa_str = request.POST.get('multa-por-dia')
            if valor_multa_str:
                config.multa_por_dia = valor_multa_str
                config.save()
                messages.success(request, 'Valor da multa atualizado com sucesso!')
                
        elif action == 'salvar-renovacao':
            dias_renovacao = request.POST.get('dias-renovacao')
            if dias_renovacao:
                config.dias_renovacao = dias_renovacao
                config.save()
                messages.success(request, 'Regra de renovação atualizada com sucesso!')
                
        return redirect('configuracao_multa')

    context = {
        'multa_por_dia': config.multa_por_dia,
        'dias_renovacao': config.dias_renovacao
    }
    return render(request, 'valor_multa.html', context)

@admin_required
def configuracao_contas(request):
    if request.method == 'POST' and request.POST.get('form-action') == 'editar-usuario':
        usuario_id = request.POST.get('usuario_id')
        user = get_object_or_404(User, id=usuario_id)

        email = request.POST.get('email')
        endereco = request.POST.get('endereco')
        
        nome = request.POST.get('nome')
        data_nascimento = request.POST.get('data_nascimento')
        celular = request.POST.get('celular')
        cpf = request.POST.get('cpf')
        cep = request.POST.get('cep')
        complemento = request.POST.get('complemento')
        cidade = request.POST.get('cidade')
        funcao = request.POST.get('funcao')
        nova_senha = request.POST.get('password')

        perfil, created = PerfilUsuario.objects.get_or_create(user=user)

        if email and endereco and cpf:
            if PerfilUsuario.objects.filter(cpf=cpf).exclude(user=user).exists():
                messages.error(request, 'Erro: CPF já está em uso por outro funcionário.')
                return redirect('configuracao_contas')

            user.email = email
            if nova_senha:
                user.set_password(nova_senha)
            user.save()
            
            perfil.nome = nome
            perfil.data_nascimento = data_nascimento or None
            perfil.celular = celular
            perfil.cpf = cpf
            perfil.email = email
            perfil.cep = cep
            perfil.endereco = endereco
            perfil.complemento = complemento
            perfil.cidade = cidade
            perfil.funcao = funcao
            perfil.save()
            
            messages.success(request, 'Funcionário atualizado com sucesso!')
        else:
            messages.error(request, 'Erro: E-mail, CPF e Endereço são obrigatórios.')
            
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
        
        nome = request.POST.get('nome')
        data_nascimento = request.POST.get('data_nascimento')
        celular = request.POST.get('celular')
        cep = request.POST.get('cep')
        complemento = request.POST.get('complemento')
        cidade = request.POST.get('cidade')
        foto_base64 = request.POST.get('foto_base64')

        if username and password and email and cpf and endereco and funcao:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Nome de usuário já existe.')
            elif PerfilUsuario.objects.filter(cpf=cpf).exists():
                messages.error(request, 'CPF já cadastrado.')
            else:
                user = User.objects.create_user(username=username, password=password, email=email)
                perfil = PerfilUsuario.objects.create(
                    user=user,
                    nome=nome,
                    data_nascimento=data_nascimento or None,
                    celular=celular,
                    email=email,
                    cpf=cpf,
                    cep=cep,
                    endereco=endereco,
                    complemento=complemento,
                    cidade=cidade,
                    funcao=funcao  
                )
                
                if foto_base64:
                    try:
                        formato, imgstr = foto_base64.split(';base64,')
                        ext = formato.split('/')[-1]
                        cpf_limpo = ''.join(filter(str.isdigit, cpf))
                        perfil.foto.save(f"funcionario_{cpf_limpo}.{ext}", ContentFile(base64.b64decode(imgstr)), save=True)
                    except Exception as e:
                        messages.warning(request, f'Aviso: Não foi possível processar a foto da câmera ({str(e)}).')
                        
                messages.success(request, 'Funcionário cadastrado com sucesso!')
        return redirect('configuracao_cadastro')

    return render(request, 'cadastro.html')

def livro_detalhes(request, livro_id):
    livro = get_object_or_404(Livro.objects.select_related('autor', 'genero', 'editora').prefetch_related('exemplares', 'imagens_adicionais'), pk=livro_id)
    
    emprestimos_ativos = Emprestimo.objects.filter(exemplar__livro=livro, devolucao__isnull=True).count()
    disponivel = Exemplar.objects.filter(livro=livro, status=Exemplar.Status.DISPONIVEL).exists()
    
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
        form = LivroCadastroForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                imagens_adicionais = request.FILES.getlist('imagens_adicionais')
                form.save(imagens_adicionais=imagens_adicionais)
                messages.success(request, 'Livro cadastrado com sucesso!')
            except Exception as e:
                messages.error(request, f'Erro interno ao cadastrar livro: {str(e)}', extra_tags="erro")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error, extra_tags="erro")
    
    context = {
        'quantidades': range(1, 51),
        'generos': Genero.objects.all().order_by('nome')
    }
    return render(request, 'cadastro_livros.html', context)

@admin_required
def editar_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    
    if request.method == 'POST':
        form = LivroEditForm(request.POST, request.FILES, instance=livro)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f'O livro "{livro.titulo}" foi atualizado.')
            except Exception as e:
                messages.error(request, f'Erro ao atualizar livro: {str(e)}', extra_tags="erro")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    # Adiciona o nome do campo para melhor contexto, se disponível
                    field_name = form.fields[field].label if field in form.fields else field
                    messages.error(request, f'{field_name}: {error}', extra_tags="erro")
        return redirect('estoque') 
    
    # Para requisições de clique normal (GET), exibimos a tela de edição
    form = LivroEditForm(instance=livro)
    return render(request, 'editar_livro.html', {'form': form, 'livro': livro})

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
    
    livros_base = Livro.objects.select_related('autor', 'editora', 'genero').all()

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
        form = LeitorForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Leitor cadastrado com sucesso!', extra_tags="sucesso")
                
                # Caso tenha tido algum problema com a foto capturada
                if hasattr(form, 'foto_aviso') and form.foto_aviso:
                    messages.warning(request, form.foto_aviso)
            except IntegrityError:
                messages.error(request, 'Erro de integridade no banco de dados (Ex: CPF ou Email duplicado).', extra_tags="erro")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error, extra_tags="erro")
                    
        return redirect('cadastro_leitor')
    
    return render(request, 'cadastro_leitor.html')

@admin_required
def editar_leitor(request, leitor_id):
    leitor = get_object_or_404(Leitor, pk=leitor_id)
    
    if request.method == 'POST':
        form = LeitorEditForm(request.POST, instance=leitor)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f'Dados de "{leitor.nome}" atualizados.')
            except IntegrityError:
                messages.error(request, 'Erro de integridade no banco de dados (Ex: ID ou Email duplicado).', extra_tags="erro")
            except Exception as e:
                messages.error(request, f'Erro ao atualizar leitor: {str(e)}', extra_tags="erro")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = form.fields[field].label if field in form.fields else field
                    messages.error(request, f'{field_name}: {error}', extra_tags="erro")
        return redirect(request.META.get('HTTP_REFERER', 'leitores')) # Redireciona mesmo em caso de erro
    return redirect('leitores') # Se não for POST, apenas redireciona

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
    hoje = timezone.now().date()
    
    subquery_multa = Emprestimo.objects.filter(
        leitor=OuterRef('pk'),
        data_devolucao__lt=hoje,
        devolucao__isnull=True
    )
    
    subquery_divida = Devolucao.objects.filter(
        emprestimo__leitor=OuterRef('pk'),
        multa_paga=False,
        valor_multa__gt=0
    )
    
    leitores_base = Leitor.objects.annotate(
        tem_atraso=Exists(subquery_multa),
        tem_divida=Exists(subquery_divida)
    )
    
    if query:
        leitores = leitores_base.filter(
            Q(nome__icontains=query) |
            Q(email__icontains=query)
        ).distinct()
    else:
        leitores = leitores_base.all()

    context = {
        'leitores': leitores,
        'query': query, 
    }
    return render(request, 'leitores.html', context)

def emprestimo(request):
    if request.method == 'POST':
        id_leitor_post = request.POST.get('id_leitor') 
        tombos_post = request.POST.getlist('codigo_tombo')
        data_emprestimo_str = request.POST.get('data_emprestimo')
        data_devolucao_str = request.POST.get('data_devolucao')

        tombos_post = [t.strip() for t in tombos_post if t.strip()]

        if not all([id_leitor_post, tombos_post, data_emprestimo_str, data_devolucao_str]):
            messages.error(request, "Todos os campos são obrigatórios e ao menos um exemplar deve ser informado.", extra_tags="erro")
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

        sucessos = 0
        erros = []
        for tombo_post in tombos_post:
            try:
                exemplar = Exemplar.objects.get(codigo_tombo=tombo_post)
                services.realizar_emprestimo(
                    leitor=leitor, exemplar=exemplar, data_emprestimo=data_emprestimo_obj,
                    data_devolucao=data_devolucao_obj, usuario=request.user if request.user.is_authenticated else None
                )
                sucessos += 1
            except Exemplar.DoesNotExist:
                erros.append(f"Código de Tombo '{tombo_post}' não encontrado.")
            except ValueError as e:
                erros.append(f"Erro no exemplar '{tombo_post}': {str(e)}")
                
        if sucessos > 0:
            messages.success(request, f"{sucessos} empréstimo(s) registrado(s) com sucesso.", extra_tags="sucesso")
        for erro in erros:
            messages.error(request, erro, extra_tags="erro")
            
        return redirect('emprestimo')

    livros_cadastrados = Livro.objects.annotate(disp=Count('exemplares', filter=Q(exemplares__status='disponivel'))).filter(disp__gt=0)
    return render(request, 'emprestimo.html', {'livros': livros_cadastrados})

def emprestimo_com_livro(request, livro_id):
    livro = get_object_or_404(Livro, pk=livro_id)
    exemplares_disponiveis = Exemplar.objects.filter(livro=livro, status=Exemplar.Status.DISPONIVEL)
    
    if not exemplares_disponiveis.exists():
        messages.error(request, f'O livro "{livro.titulo}" não está disponível para empréstimo no momento.')
        return redirect('livro_detalhes', livro_id=livro.id) 

    context = {
        'livro_pre_selecionado': livro,
        'exemplares_disponiveis': exemplares_disponiveis
    }
    return render(request, 'emprestimo.html', context)

def reservas(request):
    if request.method == 'POST':
        acao = request.POST.get('acao_massa')
        ids_selecionados = request.POST.getlist('emprestimos_selecionados')
        
        if acao == 'renovar' and ids_selecionados:
            sucessos = 0
            for emp_id in ids_selecionados:
                emp = get_object_or_404(Emprestimo, pk=emp_id)
                services.renovar_emprestimo(emp)
                sucessos += 1
            messages.success(request, f'{sucessos} empréstimo(s) renovado(s) com sucesso.')
            return redirect('reservas')
        
        elif acao == 'devolver' and ids_selecionados:
            sucessos = 0
            hoje = timezone.now().date()
            pagou_multa = request.POST.get('pagou_multa') == 'true'
            for emp_id in ids_selecionados:
                emp = get_object_or_404(Emprestimo, pk=emp_id)
                multa_devida = services.calcular_valor_multa(emp, hoje)
                valor_pago = multa_devida if pagou_multa else decimal.Decimal('0.00')
                services.realizar_devolucao(
                    emprestimo=emp, data_entrega=hoje, 
                    valor_multa_paga=valor_pago, usuario=request.user if request.user.is_authenticated else None
                )
                sucessos += 1
            messages.success(request, f'{sucessos} empréstimo(s) devolvido(s) com sucesso.')
            return redirect('reservas')

    query = request.GET.get('q', '').strip()
    
    emprestimos_base = Emprestimo.objects.select_related('leitor', 'exemplar__livro').exclude(
        pk__in=Devolucao.objects.values('emprestimo_id')
    )
    
    if query:
        # Busca por Título, Autor, Nome do Leitor, Matrícula (ID Leitor) ou Tombo
        emprestimos_ativos = emprestimos_base.filter(
            Q(exemplar__livro__titulo__icontains=query) |
            Q(exemplar__livro__autor__nome__icontains=query) |
            Q(leitor__nome__icontains=query) |
            Q(leitor__id_leitor__icontains=query) |
            Q(exemplar__codigo_tombo__icontains=query)
        ).order_by('data_devolucao')
    else:
        emprestimos_ativos = emprestimos_base.order_by('data_devolucao')

    hoje = date.today()

    for emprestimo in emprestimos_ativos:
        valor_multa = services.calcular_valor_multa(emprestimo, hoje)
        emprestimo.atrasado = valor_multa > 0
        emprestimo.valor_multa = f"{valor_multa:.2f}"
        
    paginator = Paginator(emprestimos_ativos, 15) # 15 itens por página
    page_number = request.GET.get('page')
    emprestimos_page = paginator.get_page(page_number)

    context = {
        'emprestimos': emprestimos_page
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
        
        valor_multa = services.calcular_valor_multa(emprestimo, data_entrega)
        atraso = valor_multa > 0

        return JsonResponse({
            'valor_multa': f'{valor_multa:.2f}',
            'atraso': atraso
        })
    except Exception as e:
        logger.error(f"Erro na API calcular_multa: {e}", exc_info=True)
        return JsonResponse({'erro': 'Ocorreu um erro interno ao calcular a multa.'}, status=500)

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

        services.realizar_devolucao(
            emprestimo=emprestimo, data_entrega=data_entrega,
            valor_multa_paga=valor_multa_post_str, usuario=request.user if request.user.is_authenticated else None
        )

        messages.success(request, f"O livro '{emprestimo.livro.titulo}' foi devolvido com sucesso!")
        return redirect("reservas")

    messages.error(request, "Método inválido para devolução.")
    return redirect("reservas")

def multa(request):
    query = request.GET.get('q')
    hoje = date.today()
    
    leitores_dict = {}

    # 1. Multas consolidadas (Livro devolvido, mas não pago)
    devolucoes_pendentes = Devolucao.objects.filter(multa_paga=False, valor_multa__gt=0).select_related('emprestimo__leitor')
    for dev in devolucoes_pendentes:
        leitor = dev.emprestimo.leitor
        if leitor.id not in leitores_dict:
            leitores_dict[leitor.id] = {'leitor': leitor, 'total_multa': decimal.Decimal('0.00'), 'status': 'Multa Pendente'}
        leitores_dict[leitor.id]['total_multa'] += dev.valor_multa
    
    # 2. Multas correntes (Livros atrasados, que ainda não foram devolvidos)
    emprestimos_atrasados = Emprestimo.objects.select_related('leitor').filter(data_devolucao__lt=hoje, devolucao__isnull=True)
    for emp in emprestimos_atrasados:
        valor = services.calcular_valor_multa(emp, hoje)
        if valor > 0:
            leitor = emp.leitor
            if leitor.id not in leitores_dict:
                leitores_dict[leitor.id] = {'leitor': leitor, 'total_multa': decimal.Decimal('0.00'), 'status': 'Livro em Atraso'}
            leitores_dict[leitor.id]['total_multa'] += valor
            if leitores_dict[leitor.id]['status'] != 'Livro em Atraso':
                leitores_dict[leitor.id]['status'] = 'Atraso e Multa Pendente'

    leitores_inadimplentes = list(leitores_dict.values())
    
    # Filtragem e busca
    if query:
        q_lower = query.lower()
        leitores_inadimplentes = [
            item for item in leitores_inadimplentes
            if q_lower in item['leitor'].nome.lower() or (item['leitor'].id_leitor and q_lower in item['leitor'].id_leitor.lower())
        ]

    # Ordena os maiores devedores primeiro
    leitores_inadimplentes.sort(key=lambda x: x['total_multa'], reverse=True)

    total_multas_aberto = sum(item['total_multa'] for item in leitores_dict.values())

    multas_arrecadadas_valor = Devolucao.objects.filter(multa_paga=True).aggregate(total_arrecadado=Sum('valor_multa'))['total_arrecadado']
    
    multas_arrecadadas = multas_arrecadadas_valor if multas_arrecadadas_valor else decimal.Decimal('0.00')

    context = {
        'leitores_inadimplentes': leitores_inadimplentes,
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
        
        return JsonResponse({'nome': leitor.nome, 'tem_multa': leitor.possui_multa})
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
                'capa': livro.capa.url if livro.capa and livro.capa.name else None
            }
            return JsonResponse(response_data)
        else:
            return JsonResponse({'erro': 'Livro não encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Erro na API buscar_livro: {e}", exc_info=True)
        return JsonResponse({'erro': 'Ocorreu um erro interno ao buscar o livro.'}, status=500)

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
        logger.error(f"Erro na API buscar_leitor_por_id: {e}", exc_info=True)
        return JsonResponse({'erro': 'Ocorreu um erro interno ao buscar o leitor.'}, status=500)

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
            'capa_url': livro.capa.url if livro.capa and livro.capa.name else None
        }
        return JsonResponse(response_data)
    except Livro.DoesNotExist:
        return JsonResponse({'erro': 'Livro não encontrado'}, status=404)
    except Exception as e:
        logger.error(f"Erro na API buscar_livro_por_id: {e}", exc_info=True)
        return JsonResponse({'erro': 'Ocorreu um erro interno ao buscar os detalhes do livro.'}, status=500)

def buscar_livro_completo(request):
    titulo = request.GET.get('titulo')
    try:
        livro = Livro.objects.filter(titulo__icontains=titulo).first() 
        if not livro:
            return JsonResponse({'erro': 'Livro não encontrado'}, status=404)
        
        quantidade_disponivel = Exemplar.objects.filter(livro=livro, status=Exemplar.Status.DISPONIVEL).count()
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
            'capa': livro.capa.url if livro.capa and livro.capa.name else None
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(f"Erro na API buscar_livro_completo: {e}", exc_info=True)
        return JsonResponse({'erro': 'Ocorreu um erro interno ao buscar as informações do livro.'}, status=500)

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
            'capa': livro.capa.url if livro.capa and livro.capa.name else None,
            'status': exemplar.status,
            'status_display': exemplar.get_status_display()
        }
        return JsonResponse(response_data)
    except Exemplar.DoesNotExist:
        return JsonResponse({'erro': 'Exemplar físico não encontrado.'}, status=404)
    except Exception as e:
        logger.error(f"Erro na API buscar_exemplar: {e}", exc_info=True)
        return JsonResponse({'erro': 'Ocorreu um erro interno ao buscar o exemplar físico.'}, status=500)

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
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'cancelar':
            reserva_id = request.POST.get('reserva_id')
            if reserva_id:
                reserva = get_object_or_404(Reserva, pk=reserva_id)
                reserva.status = 'cancelada'
                reserva.save()
                messages.success(request, f'A reserva do livro "{reserva.livro.titulo}" para {reserva.leitor.nome} foi cancelada.')
            return redirect('fila_reservas')
            
        elif acao == 'nova_reserva':
            leitor_id = request.POST.get('leitor_id')
            livro_id = request.POST.get('livro_id')
            
            if leitor_id and livro_id:
                leitor = get_object_or_404(Leitor, pk=leitor_id)
                livro = get_object_or_404(Livro, pk=livro_id)
                
                if Reserva.objects.filter(leitor=leitor, livro=livro, status__in=[Reserva.Status.ATIVA, Reserva.Status.DISPONIVEL]).exists():
                    messages.warning(request, f'O leitor "{leitor.nome}" já possui uma reserva ativa para "{livro.titulo}".')
                else:
                    Reserva.objects.create(leitor=leitor, livro=livro)
                    messages.success(request, f'Reserva criada com sucesso para "{leitor.nome}".')
            return redirect('fila_reservas')
            
    query = request.GET.get('q', '').strip()
    
    # Trazemos as reservas, omitindo as canceladas/atendidas da visão principal por padrão, e otimizamos com select_related
    reservas_base = Reserva.objects.select_related('leitor', 'livro').exclude(status__in=[Reserva.Status.CANCELADA, Reserva.Status.ATENDIDA]).order_by('data_solicitacao')
    
    if query:
        reservas = reservas_base.filter(
            Q(livro__titulo__icontains=query) |
            Q(leitor__nome__icontains=query)
        )
    else:
        reservas = reservas_base.all()

    leitores_ativos = Leitor.objects.filter(ativo=True).order_by('nome')
    livros = Livro.objects.all().order_by('titulo')

    context = {
        'reservas': reservas, 
        'query': query,
        'leitores': leitores_ativos,
        'livros': livros
    }
    return render(request, 'fila_reservas.html', context)

@login_required(login_url='login_view')
def renovacao(request):
    return render(request, 'renovacao.html') # A ser criado na próxima etapa

@login_required(login_url='login_view')
def historico_leitor(request, leitor_id):
    leitor = get_object_or_404(Leitor, pk=leitor_id)
    
    # Processar pagamento da multa
    if request.method == 'POST' and request.POST.get('acao') == 'quitar_multa':
        devolucao_id = request.POST.get('devolucao_id')
        if devolucao_id:
            dev = get_object_or_404(Devolucao, pk=devolucao_id, emprestimo__leitor=leitor)
            dev.multa_paga = True
            dev.recebido_por = request.user
            dev.save()
            messages.success(request, f'O pagamento de R$ {dev.valor_multa} referente à multa do livro "{dev.emprestimo.exemplar.livro.titulo}" foi quitado!')
        return redirect('historico_leitor', leitor_id=leitor.id)
        
    emprestimos = Emprestimo.objects.filter(leitor=leitor).order_by('-data_emprestimo')
    hoje = date.today()
    tem_livro_atrasado = False
    
    for emp in emprestimos:
        if not hasattr(emp, 'devolucao'):
            valor_multa = services.calcular_valor_multa(emp, hoje)
            emp.valor_multa_pendente = valor_multa
            emp.is_atrasado = valor_multa > 0
            if emp.is_atrasado:
                emp.status_color = "danger"
                emp.status_display = "Em Atraso"
                tem_livro_atrasado = True
            else:
                emp.status_color = "info text-dark"
                emp.status_display = "Emprestado"
        else:
            emp.status_color = "success"
            emp.status_display = "Devolvido"

    multas_pendentes = Devolucao.objects.filter(emprestimo__leitor=leitor, multa_paga=False, valor_multa__gt=0).order_by('-data_devolucao_real')

    context = {
        'leitor': leitor,
        'emprestimos': emprestimos,
        'multas_pendentes': multas_pendentes,
        'tem_livro_atrasado': tem_livro_atrasado
    }
    return render(request, 'historico_leitor.html', context)

@admin_required
def historico_financeiro(request):
    query = request.GET.get('q', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    
    # 1. Base query: apenas multas pagas e com valor financeiro
    devolucoes = Devolucao.objects.filter(
        multa_paga=True, 
        valor_multa__gt=0
    ).select_related(
        'emprestimo__leitor', 
        'emprestimo__exemplar__livro', 
        'recebido_por'
    ).order_by('-data_devolucao_real', '-id')
    
    # 2. Aplicação de Filtros
    if query:
        devolucoes = devolucoes.filter(
            Q(emprestimo__leitor__nome__icontains=query) |
            Q(recebido_por__username__icontains=query) |
            Q(emprestimo__leitor__id_leitor__icontains=query)
        )
        
    if data_inicio:
        devolucoes = devolucoes.filter(data_devolucao_real__gte=data_inicio)
    if data_fim:
        devolucoes = devolucoes.filter(data_devolucao_real__lte=data_fim)
        
    # 3. Totais para os Cards do Dashboard
    hoje = timezone.now().date()
    
    total_hoje = Devolucao.objects.filter(multa_paga=True, valor_multa__gt=0, data_devolucao_real=hoje).aggregate(Sum('valor_multa'))['valor_multa__sum'] or decimal.Decimal('0.00')
    total_mes = Devolucao.objects.filter(multa_paga=True, valor_multa__gt=0, data_devolucao_real__year=hoje.year, data_devolucao_real__month=hoje.month).aggregate(Sum('valor_multa'))['valor_multa__sum'] or decimal.Decimal('0.00')
    total_filtrado = devolucoes.aggregate(Sum('valor_multa'))['valor_multa__sum'] or decimal.Decimal('0.00')
    
    context = {
        'devolucoes': devolucoes, 'total_hoje': total_hoje, 'total_mes': total_mes,
        'total_filtrado': total_filtrado, 'query': query, 'data_inicio': data_inicio, 'data_fim': data_fim
    }
    return render(request, 'historico_financeiro.html', context)