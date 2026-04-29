document.addEventListener('DOMContentLoaded', function () {

    const toggleSenha = document.getElementById('toggleSenha');
    const inputSenha = document.getElementById('password');

    if (toggleSenha && inputSenha) {
        toggleSenha.addEventListener('click', () => {
            const tipo = inputSenha.getAttribute('type') === 'password' ? 'text' : 'password';
            inputSenha.setAttribute('type', tipo);

            toggleSenha.classList.toggle('fa-eye');
            toggleSenha.classList.toggle('fa-eye-slash');
        });
    }

    const botoesExcluir = document.querySelectorAll(".btn-excluir");
    botoesExcluir.forEach(botao => {
        botao.addEventListener("click", e => {
            if (!confirm("Tem certeza que deseja excluir?")) {
                e.preventDefault();
            }
        });
    });

    /*MENU LATERAL*/
    const menuToggle = document.querySelector('.menu-toggle');
    const sideMenu = document.querySelector('.side-menu');
    const body = document.body;

    if (menuToggle) {
        menuToggle.addEventListener('click', function (event) {
            event.stopPropagation(); 
            body.classList.toggle('menu-open');
        });
    }

    document.addEventListener('click', function (event) {
        if (
            body.classList.contains('menu-open') &&
            !sideMenu.contains(event.target) &&
            !menuToggle.contains(event.target)
        ) {
            body.classList.remove('menu-open');
        }
    });
    const hasSubmenuItems = document.querySelectorAll('.has-submenu > a');

    hasSubmenuItems.forEach(item => {
        item.addEventListener('click', function (event) {
            const parentLi = this.parentElement;

            if (this.getAttribute('href') === '#') {
                event.preventDefault();
                parentLi.classList.toggle('open');

                document.querySelectorAll('.has-submenu').forEach(otherItem => {
                    if (otherItem !== parentLi && otherItem.classList.contains('open')) {
                        otherItem.classList.remove('open');
                    }
                });
            }
        });
    });

    /*CEP*/
    const urlEmprestimo = window.urlEmprestimo || '/';

    const cepInput = document.getElementById('cep');
    if (cepInput) {
        const enderecoInput = document.getElementById('endereco-edicao') || document.getElementById('endereco');
        const cidadeInput = document.getElementById('cidade-edicao') || document.getElementById('cidade');

        cepInput.addEventListener('blur', () => {
            const cep = cepInput.value.replace(/\D/g, '');
            if (cep.length === 8) {
                fetch(`https://viacep.com.br/ws/${cep}/json/`)
                    .then(res => res.json())
                    .then(data => {
                        if (!data.erro) {
                            enderecoInput.value = `${data.logradouro}, ${data.bairro}`;
                            cidadeInput.value = `${data.localidade} - ${data.uf}`;
                        } else {
                            abrirModalFeedback('CEP não encontrado.', 'erro');
                            enderecoInput.value = '';
                            cidadeInput.value = '';
                        }
                    })
                    .catch(() => {
                        abrirModalFeedback('Erro ao buscar o CEP.', 'erro');
                        enderecoInput.value = '';
                        cidadeInput.value = '';
                    });
            }
        });
    }

    /*BUSCA POR CPF*/
    const cpfInput = document.getElementById('cpf');
    if (cpfInput) {
        const leitorNomeDisplay = document.getElementById('leitor-nome');
        const multaInfoDisplay = document.getElementById('multa-info');

        cpfInput.addEventListener('blur', () => {
            const cpf = cpfInput.value.replace(/\D/g, '');

            if (cpf.length !== 11) {
                leitorNomeDisplay.innerText = '❌ Erro: CPF deve ter 11 dígitos.';
                leitorNomeDisplay.style.color = '#b14942';
                multaInfoDisplay.innerText = '';
                return;
            }
            leitorNomeDisplay.style.color = 'inherit';
            leitorNomeDisplay.innerText = 'Buscando...';

            fetch(`${window.apiUrls.buscarLeitor}?cpf=${cpf}`)
                .then(response => response.json())
                .then(data => {
                    if (data.erro) throw new Error(data.erro);
                    leitorNomeDisplay.innerText = data.nome;
                    multaInfoDisplay.innerText = data.tem_multa ? 'Possui multa por atraso' : 'Não possui multas';
                })
                .catch(error => {
                    leitorNomeDisplay.innerText = error.message;
                    leitorNomeDisplay.style.color = '#b14942';
                    multaInfoDisplay.innerText = 'N/A';
                    console.error('Erro:', error);
                });
        });
    }

    /*BUSCA LIVRO EMPRESTIMO*/
    const livroBuscaInput = document.getElementById('livro-busca');
    if (livroBuscaInput) {
        const livroCapaDisplay = document.getElementById('livro-capa');
        const livroTituloDisplay = document.getElementById('livro-titulo');
        const livroAutorDisplay = document.getElementById('livro-autor');
        const livroEdicaoDisplay = document.getElementById('livro-edicao');
        const livroNumeroPaginasDisplay = document.getElementById('livro-numero_paginas');
        const livroGeneroDisplay = document.getElementById('livro-genero');
        const livroClassificacaoDisplay = document.getElementById('livro-classificacao');
        const modalIndisponivel = document.getElementById('modal-livro-indisponivel');
        const mensagemIndisponivel = document.getElementById('mensagem-indisponivel');

        function fecharModalIndisponivel() { modalIndisponivel.style.display = 'none'; }

        if (modalIndisponivel) {
            modalIndisponivel.querySelectorAll('.fechar-modal, .btn-voltar-modal').forEach(btn => {
                btn.addEventListener('click', fecharModalIndisponivel);
            });
            window.addEventListener('click', (e) => {
                if (e.target === modalIndisponivel) fecharModalIndisponivel();
            });
        }


        tomboInput.addEventListener('change', () => {
            const tomboBusca = tomboInput.value.trim();
            if (tomboBusca) {
                fetch(`${window.apiUrls.buscarExemplar}?tombo=${encodeURIComponent(tomboBusca)}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data.erro) throw new Error(data.erro);

                        livroCapaDisplay.src = data.capa || '';
                        livroCapaDisplay.style.display = data.capa ? 'block' : 'none';
                        livroTituloDisplay.innerText = data.titulo;
                        livroAutorDisplay.innerText = data.autor;
                        livroEdicaoDisplay.innerText = `Edição: ${data.edicao}`;
                        livroNumeroPaginasDisplay.innerText = `Páginas: ${data.numero_paginas}`;
                        livroGeneroDisplay.innerText = `Gênero: ${data.genero}`;
                        livroClassificacaoDisplay.innerText = `Classificação: ${data.classificacao}`;
                        if (exemplarTomboDisplay) exemplarTomboDisplay.innerHTML = `<i class="fa-solid fa-barcode"></i> Tombo: ${tomboBusca}`;

                        if (data.status !== 'disponivel') {
                            mensagemIndisponivel.innerText = `Este exemplar físico está com status: ${data.status_display}.`;
                            modalIndisponivel.style.display = 'block';
                            tomboInput.value = '';
                        }
                    })
                    .catch(error => {
                        abrirModalFeedback(error.message, 'erro');
                        livroCapaDisplay.style.display = 'none';
                        livroTituloDisplay.innerText = 'Exemplar não encontrado.';
                        livroAutorDisplay.innerText = '';
                        livroEdicaoDisplay.innerText = '';
                        livroNumeroPaginasDisplay.innerText = '';
                        livroGeneroDisplay.innerText = '';
                        livroClassificacaoDisplay.innerText = '';
                        if (exemplarTomboDisplay) exemplarTomboDisplay.innerText = '';
                    });
            }
        });
    }

    /*LIMPAR FORMULÁRIO DE EMPRÉSTIMO*/
    const limparBtn = document.querySelector('.btn-limpar');
    if (limparBtn) {
        limparBtn.addEventListener('click', () => {
            const form = document.getElementById('form-emprestimo');
            form.reset();
            ['leitor-nome', 'multa-info', 'livro-capa', 'livro-titulo', 'livro-autor', 'livro-edicao', 'livro-numero_paginas', 'livro-genero', 'livro-classificacao'].forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    if (el.tagName === 'IMG') { el.src = ''; el.style.display = 'none'; }
                    else el.innerText = '';
                }
            });
        });
    }

    /*MODAIS*/
    const modalSucesso = document.getElementById("modal-sucesso");
    const modalErro = document.getElementById("modal-erro");

    if (modalSucesso) {
        const mensagemSucesso = modalSucesso.querySelector("#mensagem-sucesso").textContent.trim();
        if (mensagemSucesso) {
            modalSucesso.style.display = "block";
        }
        document.querySelectorAll(".fechar-modal-sucesso, .btn-fechar-modal-sucesso").forEach(function (btn) {
            btn.addEventListener("click", function () {
                modalSucesso.style.display = "none";
            });
        });
    }

    if (modalErro) {
        const mensagemErro = modalErro.querySelector("#mensagem-erro").textContent.trim();
        if (mensagemErro) {
            modalErro.style.display = "block";
        }
        document.querySelectorAll(".fechar-modal-erro, .btn-fechar-modal-erro").forEach(function (btn) {
            btn.addEventListener("click", function () {
                modalErro.style.display = "none";
            });
        });
    }

    /*MODAL DE EDIÇÃO DE LEITOR*/
    const btnsEditarLeitor = document.querySelectorAll(".leitor-item .btn-editar, .btn-editar-leitor");
    const modalEdicaoLeitor = document.getElementById("modal-edicao-leitor");

    btnsEditarLeitor.forEach(btn => {
        btn.addEventListener("click", (event) => {
            const container = event.target.closest(".leitor-item") || event.target.closest("[data-leitor-id]");
            if (!container) return;

            document.getElementById("leitor-id-edicao").value = container.dataset.leitorId;
            document.getElementById("id_leitor-edicao").value = container.dataset.idLeitor || '';
            document.getElementById("nome-edicao").value = container.dataset.nome || '';
            document.getElementById("celular-edicao").value = container.dataset.celular || '';
            document.getElementById("email-edicao").value = container.dataset.email || '';
            document.getElementById("cep-edicao").value = container.dataset.cep || '';
            document.getElementById("endereco-edicao").value = container.dataset.endereco || '';
            document.getElementById("complemento-edicao").value = container.dataset.complemento || '';
            document.getElementById("cidade-edicao").value = container.dataset.cidade || '';
            document.getElementById("recebimento_alertas-edicao").value = container.dataset.alertas || 'email';
            document.getElementById("ativo-edicao").checked = container.dataset.ativo === 'true';

            const form = document.getElementById("form-edicao-leitor");
            if (form) form.action = `/leitores/editar/${container.dataset.leitorId}/`;
            
            if (modalEdicaoLeitor) {
                const modal = bootstrap.Modal.getInstance(modalEdicaoLeitor) || new bootstrap.Modal(modalEdicaoLeitor);
                modal.show();
            }
        });
    });

    /* MODAL DE EDIÇÃO DE LIVRO*/
    const btnsEditarLivro = document.querySelectorAll(".btn-editar:not([data-leitor-id])");
    const modalEdicaoLivro = document.getElementById("modal-edicao");

    btnsEditarLivro.forEach(btn => {
        btn.addEventListener("click", (event) => {
            const container = event.target.closest(".book-item");
            if (!container) return;
            const livroId = container.dataset.livroId;

            const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
            
            setVal("livro-id-edicao", livroId);
            setVal("titulo-edicao", container.dataset.livroTitulo || "");
            setVal("autor-edicao", container.dataset.autor || "");
            setVal("genero-edicao", container.dataset.genero || "");
            setVal("editora-edicao", container.dataset.editora || "");
            setVal("idioma-edicao", container.dataset.idioma || "Português");
            setVal("edicao-edicao", container.dataset.edicao || "");
            setVal("numero_paginas-edicao", container.dataset.numeroPaginas || "");
            setVal("data_publicacao-edicao", container.dataset.dataPublicacao || "");
            setVal("classificacao-edicao", container.dataset.classificacao || "");
            setVal("sinopse-edicao", container.dataset.sinopse || "");
            
            const preview = document.getElementById("capa-preview");
            if (preview) preview.src = container.dataset.capa || "";

            const form = document.getElementById("form-edicao");
            if (form) form.action = `/acervo/editar/${livroId}/`;
            
            if (modalEdicaoLivro) {
                modalEdicaoLivro.style.display = ""; 
                const modal = bootstrap.Modal.getInstance(modalEdicaoLivro) || new bootstrap.Modal(modalEdicaoLivro);
                modal.show();
            }
        });
    });

    /*MODAL CONTAS*/
    const btnsEditarConta = document.querySelectorAll('.configuracoes-main .btn-editar');
    const modalEditar = document.getElementById("modal-editar");
    const formEditar = modalEditar ? modalEditar.querySelector('form') : null;

    if (btnsEditarConta.length > 0 && modalEditar && formEditar) {
        btnsEditarConta.forEach(btn => {
            btn.addEventListener('click', function () {
                const id = this.getAttribute('data-id');
                const email = this.getAttribute('data-email');
                const endereco = this.getAttribute('data-endereco');

                document.getElementById("usuario_id").value = id;
                document.getElementById("modal-email").value = email;
                document.getElementById("modal-endereco").value = endereco;

                modalEditar.style.display = "flex";

            });
        });
    }

    /*MODAL DE DEVOLUÇÃO*/
    const btnsDevolucao = document.querySelectorAll(".btn-devolucao");
    const modalDevolucao = document.getElementById("modal-devolucao");
    const fecharModalDevolucao = modalDevolucao?.querySelector(".fechar-modal");
    const btnVoltarDevolucao = modalDevolucao?.querySelector(".btn-voltar-modal");

    const dataEntregaInput = document.getElementById("data-entrega");
    const valorMultaP = document.getElementById("valor-multa");
    const valorMultaHidden = document.getElementById("valor-multa-hidden");
    const atrasadoP = document.getElementById("atrasado-devolucao");
    const btnPago = document.getElementById("btn-pago");
    const formDevolucao = document.getElementById("form-devolucao");
    const emprestimoIdInput = document.getElementById("emprestimo-id");

    function formatarData(dataStr) {
        if (!dataStr) return '';
        try {
            const [ano, mes, dia] = dataStr.split('-');
            return `${dia}/${mes}/${ano}`;
        } catch (e) {
            console.error("Erro ao formatar a data:", e);
            return dataStr;
        }
    }

    btnsDevolucao.forEach(btn => {
        btn.addEventListener("click", () => {
            const tr = btn.closest("tr");

            const emprestimoId = tr.dataset.emprestimoId;
            const titulo = tr.children[0].textContent;
            const leitor = tr.children[1].textContent;
            const dataEmprestimo = formatarData(tr.dataset.emprestimoData);
            const dataDevolucaoPrevista = formatarData(tr.dataset.emprestimoDevolucao);

            const atrasado = tr.dataset.emprestimoAtrasado === "1" ? "Sim" : "Não";
            const valorMulta = tr.dataset.emprestimoMulta || "0.00";

            emprestimoIdInput.value = emprestimoId;
            document.getElementById("titulo-devolucao").textContent = titulo;
            document.getElementById("leitor-devolucao").textContent = leitor;
            document.getElementById("data-emprestimo-devolucao").textContent = dataEmprestimo;
            document.getElementById("data-devolucao-prevista").textContent = dataDevolucaoPrevista;
            atrasadoP.textContent = atrasado;
            valorMultaP.textContent = valorMulta;
            valorMultaHidden.value = valorMulta;

            const hoje = new Date().toISOString().substring(0, 10);
            dataEntregaInput.value = hoje;

            formDevolucao.action = `/circulacao/devolver/${emprestimoId}/`;
            modalDevolucao.style.display = "block";

        });
    });

    [fecharModalDevolucao, btnVoltarDevolucao].forEach(el => {
        el?.addEventListener("click", () => {
            modalDevolucao.style.display = "none";
        });
    });

    window.addEventListener("click", e => {
        if (e.target === modalDevolucao) {
            modalDevolucao.style.display = "none";
        }
    });

    btnPago?.addEventListener("click", () => {
        valorMultaHidden.value = "0.00";
        valorMultaP.textContent = "PAGO";
    });

    /*MODAL DE EDIÇÃO DE CONTA*/
    window.abrirModal = function (id, email, cpf, endereco) {
        document.getElementById("usuario_id").value = id;
        document.getElementById("modal-email").value = email;
        document.getElementById("modal-endereco").value = endereco;
        const modalEditar = document.getElementById("modal-editar");
        if (modalEditar) {
            modalEditar.style.display = "flex";
        }
    };

    window.fecharModal = function () {
        const modalEditar = document.getElementById("modal-editar");
        if (modalEditar) {
            modalEditar.style.display = "none";
        }
    };

    /*TRATAMENTO DE MENSAGENS DJANGO*/
    const djangoMensagensEl = document.getElementById("django-mensagens");
    if (djangoMensagensEl) {
        try {
            const mensagens = JSON.parse(djangoMensagensEl.textContent);
            if (mensagens.length > 0) {
                abrirModalFeedback(mensagens[0].mensagem, mensagens[0].tipo);
            }
        } catch (e) {
            console.error("Erro ao parsear mensagens do Django:", e);
        }
    }

    // Lógica para "Selecionar Tudo" na tela de Devolução/Renovação
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = this.checked);
        });
    }
});


window.fecharModalFeedback = function () {
    const modal1 = document.getElementById("modal-feedback");
    if (modal1) { modal1.style.display = "none"; }
}

window.abrirModalFeedback = function (mensagem = null, tipo = null) {
    const modal = document.getElementById("modal-feedback");
    const conteudo = document.getElementById("conteudo-feedback");

    if (mensagem && conteudo) {
        conteudo.innerHTML = `
            <span class="fechar-modal" onclick="fecharModalFeedback()">&times;</span>
            <p class="mensagem-feedback ${tipo || 'info'}">${mensagem}</p>
            <button class="btn-voltar-modal" onclick="fecharModalFeedback()">Fechar</button>
        `;
    }

    if (modal) {
        modal.style.display = "flex";
    }
}
