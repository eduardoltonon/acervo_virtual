import base64
from django import forms
from django.core.files.base import ContentFile
from .models import Leitor
from . import services

class LeitorForm(forms.ModelForm):
    foto_base64 = forms.CharField(required=False)

    class Meta:
        model = Leitor
        fields = [
            'id_leitor', 'nome', 'data_nascimento', 'celular', 'cpf',
            'email', 'cep', 'endereco', 'complemento', 'cidade',
            'recebimento_alertas'
        ]

    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if not cpf:
            return cpf
            
        cpf_limpo = ''.join(filter(str.isdigit, str(cpf)))
        
        # Validação de CPF
        if len(cpf_limpo) != 11 or len(set(cpf_limpo)) == 1:
            raise forms.ValidationError('CPF inválido. Verifique os números digitados.')
            
        for i in range(9, 11):
            value = sum((int(cpf_limpo[num]) * ((i+1) - num) for num in range(0, i)))
            digit = ((value * 10) % 11) % 10
            if digit != int(cpf_limpo[i]):
                raise forms.ValidationError('CPF inválido. Verifique os números digitados.')
                
        # Verifica duplicidade
        if Leitor.objects.filter(cpf=cpf_limpo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este CPF já está cadastrado para outro leitor.')
            
        return cpf_limpo

    def clean_id_leitor(self):
        id_leitor = self.cleaned_data.get('id_leitor')
        if Leitor.objects.filter(id_leitor=id_leitor).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este ID de Leitor já está cadastrado no sistema.')
        return id_leitor

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Leitor.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este endereço de e-mail já está cadastrado para outro leitor.')
        return email

    def save(self, commit=True):
        leitor = super().save(commit=False)
        foto_base64 = self.cleaned_data.get('foto_base64')
        self.foto_aviso = None
        
        if foto_base64:
            try:
                formato, imgstr = foto_base64.split(';base64,')
                ext = formato.split('/')[-1]
                cpf_limpo = self.cleaned_data.get('cpf')
                leitor.foto.save(f"leitor_{cpf_limpo}.{ext}", ContentFile(base64.b64decode(imgstr)), save=False)
            except Exception as e:
                self.foto_aviso = f'Aviso: Não foi possível processar a foto da câmera ({str(e)}).'
                
        if commit:
            leitor.save()
        return leitor

class LivroCadastroForm(forms.Form):
    titulo = forms.CharField(max_length=200, error_messages={'required': 'O título é obrigatório.'})
    autor = forms.CharField(max_length=200, error_messages={'required': 'O autor é obrigatório.'})
    edicao = forms.CharField(max_length=100, error_messages={'required': 'A edição é obrigatória.'})
    numero_paginas = forms.IntegerField(min_value=1, error_messages={'required': 'O número de páginas é obrigatório.', 'invalid': 'Digite um número válido de páginas.'})
    genero = forms.CharField(max_length=100, error_messages={'required': 'O gênero é obrigatório.'})
    classificacao = forms.IntegerField(error_messages={'required': 'A classificação é obrigatória.', 'invalid': 'Digite uma classificação válida.'})
    sinopse = forms.CharField(widget=forms.Textarea, error_messages={'required': 'A sinopse é obrigatória.'})
    capa = forms.ImageField(required=False, error_messages={'invalid': 'Envie um arquivo de imagem válido para a capa.'})
    quantidade = forms.IntegerField(min_value=1, max_value=50, initial=1, error_messages={'required': 'A quantidade é obrigatória.', 'invalid': 'Digite uma quantidade válida.'})
    editora = forms.CharField(max_length=200, required=False)
    idioma = forms.CharField(max_length=50, required=False)
    data_publicacao = forms.DateField(required=False, error_messages={'invalid': 'Insira uma data de publicação válida no formato correto.'})
    localizacao = forms.CharField(max_length=100, required=False)

    def save(self, imagens_adicionais=None):
        cd = self.cleaned_data
        return services.criar_livro_com_exemplares(
            titulo=cd['titulo'],
            autor_nome=cd['autor'],
            edicao=cd['edicao'],
            numero_paginas=cd['numero_paginas'],
            genero_nome=cd['genero'],
            classificacao=cd['classificacao'],
            sinopse=cd['sinopse'],
            capa=cd['capa'],
            imagens_adicionais=imagens_adicionais,
            quantidade=cd['quantidade'],
            editora_nome=cd['editora'],
            idioma=cd['idioma'],
            data_publicacao=cd['data_publicacao'] or None,
            localizacao=cd['localizacao']
        )