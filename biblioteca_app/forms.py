import base64
from django import forms
from django.core.files.base import ContentFile
from .models import Leitor, Livro, Autor, Genero, Editora
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

class LeitorEditForm(forms.ModelForm):
    class Meta:
        model = Leitor
        fields = [
            'id_leitor', 'nome', 'celular', 'email', 'cep', 'endereco',
            'complemento', 'cidade', 'recebimento_alertas', 'ativo'
        ]
        # Excluímos 'cpf' e 'data_nascimento' pois geralmente não são editados
        # após o cadastro. Se precisar editá-los, adicione-os aqui e no template.
        # Excluímos 'foto' pois a view de edição atual não lida com upload de foto.

    def clean_id_leitor(self):
        id_leitor = self.cleaned_data.get('id_leitor')
        if Leitor.objects.filter(id_leitor=id_leitor).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este ID de Leitor já está em uso por outro leitor.')
        return id_leitor

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Leitor.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este endereço de e-mail já está em uso por outro leitor.')
        return email

class LivroEditForm(forms.ModelForm):
    # Campos para Autor, Gênero e Editora que virão como strings do formulário
    autor_nome = forms.CharField(max_length=200, required=True, label="Autor")
    genero_nome = forms.CharField(max_length=100, required=True, label="Gênero")
    editora_nome = forms.CharField(max_length=200, required=False, label="Editora")
    
    # Campo para nova capa (opcional)
    capa_nova = forms.ImageField(required=False, label="Nova Capa")

    class Meta:
        model = Livro
        fields = [
            'titulo', 'edicao', 'numero_paginas', 'classificacao', 'sinopse',
            'idioma', 'data_publicacao', 'localizacao'
        ]
        # 'autor', 'genero', 'editora', 'capa' são excluídos daqui pois são tratados pelos campos customizados acima.
        widgets = {
            'sinopse': forms.Textarea(attrs={'rows': 3}),
            'data_publicacao': forms.DateInput(attrs={'type': 'date'}),
        }
        error_messages = {
            'titulo': {'required': 'O título é obrigatório.'},
            'edicao': {'required': 'A edição é obrigatória.'},
            'numero_paginas': {'required': 'O número de páginas é obrigatório.', 'invalid': 'Digite um número válido de páginas.'},
            'classificacao': {'required': 'A classificação é obrigatória.', 'invalid': 'Digite uma classificação válida.'},
            'sinopse': {'required': 'A sinopse é obrigatória.'},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance: # Preenche os campos de texto com os valores atuais do livro
            self.fields['autor_nome'].initial = self.instance.autor.nome
            self.fields['genero_nome'].initial = self.instance.genero.nome
            if self.instance.editora:
                self.fields['editora_nome'].initial = self.instance.editora.nome

    def save(self, commit=True):
        livro = super().save(commit=False)
        livro.autor, _ = Autor.objects.get_or_create(nome=self.cleaned_data['autor_nome'].strip())
        livro.genero, _ = Genero.objects.get_or_create(nome=self.cleaned_data['genero_nome'].strip())
        livro.editora, _ = Editora.objects.get_or_create(nome=self.cleaned_data['editora_nome'].strip()) if self.cleaned_data['editora_nome'] else (None, False)
        if self.cleaned_data.get('capa_nova'):
            livro.capa = self.cleaned_data['capa_nova']
        if commit:
            livro.save()
        return livro

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