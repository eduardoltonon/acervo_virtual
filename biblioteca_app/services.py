from django.db import transaction
from django.utils import timezone
from .models import Livro, Exemplar, Emprestimo, Devolucao, Configuracao, Leitor, Autor, Editora, Genero, ImagemLivro
import decimal
import uuid
from datetime import date

def criar_livro_com_exemplares(titulo, autor_nome, edicao, numero_paginas, genero_nome, classificacao, sinopse, capa, quantidade, imagens_adicionais=None, editora_nome=None, idioma=None, data_publicacao=None, localizacao=None):
    with transaction.atomic():
        autor, _ = Autor.objects.get_or_create(nome=autor_nome.strip())
        genero, _ = Genero.objects.get_or_create(nome=genero_nome.strip())
        
        editora = None
        if editora_nome:
            editora, _ = Editora.objects.get_or_create(nome=editora_nome.strip())

        livro = Livro.objects.create(
            titulo=titulo, autor=autor, edicao=edicao, 
            numero_paginas=numero_paginas, genero=genero, 
            classificacao=classificacao, sinopse=sinopse, 
            capa=capa, editora=editora, idioma=idioma, 
            data_publicacao=data_publicacao,
            localizacao=localizacao
        )
        
        if imagens_adicionais:
            for img in imagens_adicionais:
                ImagemLivro.objects.create(livro=livro, imagem=img)
                
        exemplares = []
        for i in range(quantidade):
            # Gera um código de barras/tombo único simples para nossa simulação
            codigo_tombo = f"TB-{uuid.uuid4().hex[:8].upper()}"
            exemplares.append(Exemplar(livro=livro, codigo_tombo=codigo_tombo))
        Exemplar.objects.bulk_create(exemplares)
    return livro

def calcular_valor_multa(emprestimo, data_base=None):
    if not data_base:
        data_base = date.today()
    config = Configuracao.objects.first()
    valor_por_dia = decimal.Decimal(str(config.multa_por_dia)) if config else decimal.Decimal('2.50')
    if data_base > emprestimo.data_devolucao:
        dias_atraso = (data_base - emprestimo.data_devolucao).days
        return valor_por_dia * dias_atraso
    return decimal.Decimal('0.00')

def realizar_emprestimo(leitor, exemplar, data_emprestimo, data_devolucao, usuario):
    with transaction.atomic():
        if not leitor.ativo:
            raise ValueError("Este leitor está bloqueado no sistema.")
            
        if leitor.possui_multa:
            raise ValueError("Leitor possui livros em atraso ou multas financeiras não pagas.")

        if exemplar.status != Exemplar.Status.DISPONIVEL:
            raise ValueError("Este exemplar físico não está disponível no momento.")

        exemplar.status = Exemplar.Status.EMPRESTADO
        exemplar.save()

        return Emprestimo.objects.create(
            leitor=leitor, exemplar=exemplar, data_emprestimo=data_emprestimo,
            data_devolucao=data_devolucao, cadastrado_por=usuario
        )

def realizar_devolucao(emprestimo, data_entrega, valor_multa_paga, usuario):
    with transaction.atomic():
        multa_devida = calcular_valor_multa(emprestimo, data_entrega)
        valor_pago_decimal = decimal.Decimal(str(valor_multa_paga)) if valor_multa_paga else decimal.Decimal('0.00')
        multa_foi_paga = True if multa_devida == 0 or valor_pago_decimal >= multa_devida else False

        devolucao = Devolucao.objects.create(
            emprestimo=emprestimo, data_devolucao_real=data_entrega,
            valor_multa=multa_devida, multa_paga=multa_foi_paga, recebido_por=usuario if multa_foi_paga and multa_devida > 0 else None
        )

        emprestimo.exemplar.status = Exemplar.Status.DISPONIVEL
        emprestimo.exemplar.save()
        
        return devolucao

def renovar_emprestimo(emprestimo):
    with transaction.atomic():
        config = Configuracao.objects.first()
        dias = config.dias_renovacao if config else 7
        
        # A nova data de devolução é a data atual prevista + os dias de renovação
        emprestimo.data_devolucao = emprestimo.data_devolucao + timezone.timedelta(days=dias)
        emprestimo.save()
        
        return emprestimo