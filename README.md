<div align="center">
  <img width="300" alt="acervo" src="capa-readme.png" />
</div>

# 📚 Acervo Virtual

O **Acervo Virtual** é um sistema completo de gestão bibliotecária desenvolvido em **Python (Django)**. Projetado para otimizar o dia a dia de bibliotecas, o sistema permite que administradores e bibliotecários gerenciem o acervo de livros, estoques físicos (tombos), leitores, empréstimos, devoluções, reservas e até mesmo o controle financeiro de multas por atraso.

Este projeto foi desenvolvido como parte do Projeto Aplicado III/IV.

---

## ✨ Principais Funcionalidades

- **📖 Gestão de Acervo:** Cadastro detalhado de livros, autores, editoras e gêneros. Controle físico de exemplares através de Códigos de Tombo únicos.
- **🔄 Circulação:** Empréstimos dinâmicos, devoluções (com cálculo automático de multas baseadas em configurações do sistema), renovações e fila de reservas.
- **👥 Gestão de Leitores:** Cadastro completo de leitores com suporte nativo a captura de fotos via webcam do sistema, histórico de locações e controle de inadiplência.
- **💰 Financeiro:** Controle de multas geradas por atraso na devolução e painel de recebimentos.
- **⚙️ Administração:** Relatórios gerenciais de uso, configurações globais (valor de multa diária) e gerenciamento de permissões de funcionários.

---

## 🛠️ Tecnologias Utilizadas

- **Back-end:** Python 3, Django 5.x
- **Banco de Dados:** SQLite3 (Embarcado, ideal para o ambiente de desenvolvimento)
- **Front-end:** HTML5, CSS3, JavaScript Puro (Vanilla JS)
- **Estilização & UI/UX:** Bootstrap 5, FontAwesome 6, Paleta de Cores Customizada (Grafite, Verde Água e Areia)
- **Processamento e Mídia:** Biblioteca `Pillow` (para o processamento de capas de livros e fotos em Base64 da câmera)

---

## 🚀 Guia Rápido de Configuração (Para Desenvolvedores)

Siga o passo a passo abaixo para preparar o ambiente virtual na sua IDE (VS Code, PyCharm, etc.), instalar as dependências e rodar a aplicação localmente pela primeira vez.

### 1. Pré-requisitos
Certifique-se de ter instalado em sua máquina:
- Python 3.10 ou superior (Não esqueça de marcar a opção *"Add Python to PATH"* na instalação do Windows).
- Git

### 2. Clonar o Repositório
Abra o terminal em sua máquina, navegue até a pasta onde deseja manter o código e execute:
```bash
git clone https://github.com/23Aline/biblioteca_virtual.git
cd biblioteca_virtual
```

### 3. Criar e Ativar o Ambiente Virtual (VENV)
O uso do ambiente virtual é obrigatório para evitar conflitos de bibliotecas.
- **No Windows:**
  ```bash
  python -m venv venv
  venv\Scripts\activate
  ```
- **No Linux/Mac:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
> *Dica: Se a ativação for bem-sucedida, você verá um `(venv)` no início da linha do seu terminal.*

### 4. Instalar as Dependências do Projeto
Com o ambiente ativado, instale o Django, Pillow e quaisquer outros pacotes mapeados no projeto executando:
```bash
pip install -r requirements.txt
```
*(Se o arquivo `requirements.txt` não existir, você pode instalar as bases manualmente rodando: `pip install django pillow`).*

### 5. Aplicar as Migrações do Banco de Dados
O sistema utiliza o SQLite. Para criar as tabelas e a estrutura do banco a partir dos nossos *Models*, rode em sequência:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Criar um Superusuário (Console)
Para ter o acesso global no sistema, crie o primeiro usuário rodando o comando:
```bash
python manage.py createsuperuser
```
> **⚠️ Nota de Arquitetura:** Nosso sistema requer um "PerfilUsuario". Se você criar um usuário administrador direto por esse comando no terminal, a própria aplicação interceptará o seu primeiro login e **gerará um Perfil de Administrador automaticamente** para você não ficar travado!

### 7. Executar o Servidor Local
Tudo pronto! Para iniciar a aplicação, utilize:
```bash
python manage.py runserver
```
O projeto estará acessível pelo navegador no endereço: **`http://127.0.0.1:8000/`**

---

## 🔐 Acesso ao Sistema (Contas Padrão)

Caso você possua um banco de dados pré-populado ou decida criar estas contas pela interface da aplicação, utilize as credenciais de teste abaixo:

**Acesso de Administrador (Total)**
*Permite cadastrar funcionários, alterar valor de multas, acessar relatórios e apagar registros.*
- **Usuário:** `Admin`
- **Senha:** `Biblioteca123*`

**Acesso de Bibliotecário (Comum)**
*Permite fluxo de caixa diário (empréstimos, devoluções, multas) e cadastro de leitores/livros.*
- **Usuário:** `Bibliotecário`
- **Senha:** `Biblioteca123*`

---

## 🔗 Link na plataforma SAGA
```text
https://plataforma.gpinovacao.senai.br/plataforma/demandas-da-industria/interna/11036
```

## 👨‍💻 Desenvolvedores
🔗 [Mizaela](https://linkedin.com/in/mizaela-nunes) | 🔗 [Aline](https://linkedin.com/in/aline-nunes-037937297) | 🔗 [Eduardo](https://linkedin.com/in/eduardo-tonon-a5057020a) | 🔗 [Lucas](https://linkedin.com/in/lucas-fernando-796633199)
