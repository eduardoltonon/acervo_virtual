from django.db import models
from django.utils import timezone 
from django.contrib.auth.models import User

class Genero(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome

class Editora(models.Model):
    nome = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.nome

class Autor(models.Model):
    nome = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.nome

class Livro(models.Model):
    titulo = models.CharField(max_length=200)
    autor = models.ForeignKey(Autor, on_delete=models.PROTECT, related_name="livros")
    edicao = models.CharField(max_length=100)
    editora = models.ForeignKey(Editora, on_delete=models.PROTECT, related_name="livros", null=True, blank=True)
    idioma = models.CharField(max_length=50, default="Português")
    data_publicacao = models.DateField(blank=True, null=True)
    numero_paginas = models.IntegerField()
    genero = models.ForeignKey(Genero, on_delete=models.PROTECT, related_name="livros")
    classificacao = models.IntegerField() 
    sinopse = models.TextField()
    capa = models.ImageField(upload_to='capas/', blank=True, null=True)
    localizacao = models.CharField(max_length=100, blank=True, null=True, help_text="Ex: Estante A, Prateleira 2")

    def __str__(self):
        return self.titulo

class ImagemLivro(models.Model):
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name='imagens_adicionais')
    imagem = models.ImageField(upload_to='livros_imagens/')

    def __str__(self):
        return f"Imagem adicional de {self.livro.titulo}"

class Exemplar(models.Model):
    STATUS_CHOICES = [
        ('disponivel', 'Disponível'),
        ('emprestado', 'Emprestado'),
        ('manutencao', 'Em Manutenção'),
        ('perdido', 'Perdido'),
    ]
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name='exemplares')
    codigo_tombo = models.CharField(max_length=50, unique=True, help_text="Código identificador único do exemplar físico")
    estado_conservacao = models.CharField(max_length=100, default='Bom')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disponivel')

    def __str__(self):
        return f"{self.livro.titulo} - Tombo: {self.codigo_tombo}"

class Leitor(models.Model):
    id_leitor = models.CharField(max_length=50, unique=True, null=True, blank=True, help_text="ID Único ou Matrícula")
    nome = models.CharField(max_length=200)
    data_nascimento = models.DateField()
    celular = models.CharField(max_length=15, unique=True)
    cpf = models.CharField(max_length=14, unique=True)
    email = models.EmailField(unique=True)
    cep = models.CharField(max_length=9)
    endereco = models.CharField(max_length=255)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    cidade = models.CharField(max_length=100)
    RECEBIMENTO_ALERTAS_CHOICES = [
        ('email', 'Email'),
        ('celular', 'Celular'),
    ]
    recebimento_alertas = models.CharField(max_length=10, choices=RECEBIMENTO_ALERTAS_CHOICES, default='email')
    ativo = models.BooleanField(default=True, help_text="Desmarque para bloquear temporariamente o leitor")
    foto = models.ImageField(upload_to='fotos_leitores/', null=True, blank=True)

    @property
    def possui_multa(self):
        if hasattr(self, 'tem_multa_anotada'):
            return self.tem_multa_anotada
        hoje = timezone.now().date()
        return Emprestimo.objects.filter(leitor=self, data_devolucao__lt=hoje, devolucao__isnull=True).exists()

    def __str__(self):
        return self.nome
        
class Reserva(models.Model):
    STATUS_CHOICES = [
        ('ativa', 'Ativa - Na Fila'),
        ('disponivel', 'Livro Disponível (Aguardando Retirada)'),
        ('atendida', 'Atendida (Empréstimo Realizado)'),
        ('cancelada', 'Cancelada'),
    ]
    leitor = models.ForeignKey(Leitor, on_delete=models.CASCADE, related_name='reservas')
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name='reservas')
    data_solicitacao = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativa')

    def __str__(self):
        return f"Reserva: {self.leitor.nome} -> {self.livro.titulo} ({self.get_status_display()})"

class Emprestimo(models.Model):
    leitor = models.ForeignKey(Leitor, on_delete=models.CASCADE)
    exemplar = models.ForeignKey(Exemplar, on_delete=models.CASCADE)
    data_emprestimo = models.DateField(default=timezone.now)
    data_devolucao = models.DateField()
    cadastrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='emprestimos_realizados')

    def __str__(self):
        return f"{self.leitor.nome} emprestou {self.exemplar.livro.titulo}"
    
class Devolucao(models.Model):
    emprestimo = models.OneToOneField(Emprestimo, on_delete=models.CASCADE)
    data_devolucao_real = models.DateField(default=timezone.now)
    valor_multa = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    multa_paga = models.BooleanField(default=False)
    recebido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='devolucoes_recebidas')

    def __str__(self):
        return f"Devolução de {self.emprestimo.exemplar.livro.titulo}"
    
class Configuracao(models.Model):
    multa_por_dia = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    limite_dias_emprestimo = models.PositiveIntegerField(default=14, help_text="Número máximo de dias para um empréstimo padrão.")

    def __str__(self):
        return "Configurações do Sistema"

class PerfilUsuario(models.Model):
    FUNCOES = [
        ("administrador", "Administrador"),
        ("bibliotecario", "Bibliotecário"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    email = models.EmailField()
    cpf = models.CharField(max_length=14, unique=True)
    endereco = models.CharField(max_length=255)
    funcao = models.CharField(max_length=20, choices=FUNCOES, default="bibliotecario" ) 

    def __str__(self):
        return f"{self.user.username} - {self.funcao}"
