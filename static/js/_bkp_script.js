// 🔍 SISTEMA DE AUTOCOMPLETE INTELIGENTE
class AutocompleteCliente {
    constructor() {
        this.initEventListeners();
        this.setupValidation();
    }

    initEventListeners() {
        const razaoInput = document.getElementById('razaoSocial');
        const cnpjInput = document.getElementById('cnpj');

        if (razaoInput) {
            razaoInput.addEventListener('input', (e) => this.handleRazaoInput(e));
            razaoInput.addEventListener('blur', () => this.hideDropdown());
        }

        if (cnpjInput) {
            cnpjInput.addEventListener('input', (e) => this.handleCnpjInput(e));
            cnpjInput.addEventListener('blur', () => this.validateCliente());
        }

        document.getElementById('pedidoForm').addEventListener('input', () => this.calculaFrete());
    }

    async handleRazaoInput(event) {
        const termo = event.target.value;

        if (termo.length < 2) {
            this.hideDropdown();
            return;
        }

        try {
            const response = await fetch(`/api/buscar_clientes?q=${encodeURIComponent(termo)}`);
            const resultados = await response.json();

            this.showDropdown(resultados, 'razao');
        } catch (error) {
            console.error('Erro ao buscar clientes:', error);
        }
    }

    async handleCnpjInput(event) {
        let cnpj = event.target.value;

        // Formatação automática do CNPJ
        cnpj = this.formatCNPJ(cnpj);
        event.target.value = cnpj;

        if (cnpj.length >= 14) {
            try {
                const response = await fetch(`/api/buscar_clientes?q=${encodeURIComponent(cnpj)}`);
                const resultados = await response.json();

                if (resultados.length > 0) {
                    this.showDropdown(resultados, 'cnpj');
                }
            } catch (error) {
                console.error('Erro ao buscar por CNPJ:', error);
            }
        }
    }

    formatCNPJ(cnpj) {
        cnpj = cnpj.replace(/\D/g, '');
        cnpj = cnpj.replace(/(\d{2})(\d)/, '$1.$2');
        cnpj = cnpj.replace(/(\d{3})(\d)/, '$1.$2');
        cnpj = cnpj.replace(/(\d{3})(\d)/, '$1/$2');
        cnpj = cnpj.replace(/(\d{4})(\d)/, '$1-$2');

        return cnpj;
    }

    showDropdown(resultados, tipo) {
        this.hideDropdown();

        const dropdown = document.createElement('div');
        dropdown.id = 'autocomplete-dropdown';
        dropdown.className = 'autocomplete-dropdown';

        resultados.forEach(resultado => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.innerHTML = `
                <div class="autocomplete-cnpj">${resultado.cnpj}</div>
                <div class="autocomplete-razao">${resultado.razao_social}</div>
            `;

            item.addEventListener('mousedown', () => {
                this.selectCliente(resultado);
            });

            dropdown.appendChild(item);
        });

        const container = tipo === 'razao' ?
            document.getElementById('razaoSocial').parentNode :
            document.getElementById('cnpj').parentNode;

        container.style.position = 'relative';
        container.appendChild(dropdown);
    }

    selectCliente(cliente) {
        document.getElementById('cnpj').value = cliente.cnpj;
        document.getElementById('razaoSocial').value = cliente.razao_social;

        this.hideDropdown();
        this.showValidationSuccess('Cliente válido selecionado!');
    }

    hideDropdown() {
        const dropdown = document.getElementById('autocomplete-dropdown');
        if (dropdown) {
            dropdown.remove();
        }
    }

    async validateCliente() {
        const cnpj = document.getElementById('cnpj').value;
        const razao = document.getElementById('razaoSocial').value;

        if (!cnpj && !razao) return;

        try {
            const response = await fetch(`/api/validar_cliente?cnpj=${encodeURIComponent(cnpj)}&razao=${encodeURIComponent(razao)}`);
            const result = await response.json();

            if (result.valido) {
                document.getElementById('cnpj').value = result.cnpj;
                document.getElementById('razaoSocial').value = result.razao_social;
                this.showValidationSuccess(result.message);
            } else {
                this.showValidationError(result.message);
            }
        } catch (error) {
            console.error('Erro na validação:', error);
        }
    }

    calculaFrete() {
        const products = document.querySelectorAll('.produto-item');
        let total = 0;

        products.forEach(product => {
            const metragem = parseFloat(product.querySelector('.produto-metragem').value) || 0;
            const preco = parseFloat(product.querySelector('.produto-preco').value) || 0;
            total += metragem * preco;
        });

        if (total > 5000) {
            document.querySelector('select[name="tipoFrete"]').value = 'CIF';
            document.getElementById('transportadoraCIF').disabled = true;
        } else {
            document.getElementById('transportadoraCIF').disabled = false;
        }
    }

    showValidationSuccess(message) {
        this.showValidationMessage(message, 'success');
    }

    showValidationError(message) {
        this.showValidationMessage(message, 'error');
    }

    showValidationMessage(message, type) {
        const existing = document.querySelector('.validation-message');
        if (existing) existing.remove();

        const messageDiv = document.createElement('div');
        messageDiv.className = `validation-message validation-${type}`;
        messageDiv.textContent = message;

        const cnpjInput = document.getElementById('cnpj');
        cnpjInput.parentNode.insertBefore(messageDiv, cnpjInput.nextSibling);

        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 3000);
    }

    setupValidation() {
        document.getElementById('nomeRepresentante')?.addEventListener('blur', this.validateRepresentante);
        document.getElementById('telefone')?.addEventListener('input', this.formatTelefone);
    }

    validateRepresentante(event) {
        const nome = event.target.value.trim();
        if (nome.length < 2) {
            event.target.style.borderColor = '#e74c3c';
        } else {
            event.target.style.borderColor = '#27ae60';
        }
    }

    formatTelefone(event) {
        let telefone = event.target.value.replace(/\D/g, '');

        if (telefone.length <= 11) {
            if (telefone.length <= 10) {
                telefone = telefone.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
            } else {
                telefone = telefone.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
            }
        }

        event.target.value = telefone;
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    new AutocompleteCliente();
});
// ========== ENVIO DO FORMULÁRIO ==========
document.getElementById('pedidoForm').addEventListener('submit', function (e) {
    e.preventDefault();

    // Validar se há pelo menos um produto
    const produtos = document.querySelectorAll('.produto-item');
    if (produtos.length === 0) {
        alert('⚠️ Adicione pelo menos um produto ao pedido!');
        return;
    }

    // Coletar dados do formulário
    const dadosPedido = coletarDadosFormulario();

    // Mostrar loading
    const btnSubmit = document.querySelector('button[type="submit"]');
    const textoOriginal = btnSubmit.innerHTML;
    btnSubmit.innerHTML = '📤 Enviando...';
    btnSubmit.disabled = true;

    // Enviar para o servidor
    fetch('/submit_pedido', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(dadosPedido)
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`✅ Pedido ${data.numero_pedido} enviado com sucesso!\n\n📧 Emails enviados para:\n- pedido@designtextecidos.com.br\n- design2@designtextecidos.com.br`);
                limparFormulario();
            } else {
                alert(`❌ Erro: ${data.error}`);
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('❌ Erro ao enviar pedido. Tente novamente.');
        })
        .finally(() => {
            btnSubmit.innerHTML = textoOriginal;
            btnSubmit.disabled = false;
        });
});

function coletarDadosFormulario() {
    // Dados do cabeçalho
    const dados = {
        nomeRepresentante: document.getElementById('nomeRepresentante').value,
        razaoSocial: document.getElementById('razaoSocial').value,
        cnpj: document.getElementById('cnpj').value,
        telefone: document.getElementById('telefone').value,
        prazoPagamento: document.getElementById('prazoPagamento').value,
        tipoPedido: document.getElementById('tipoPedido').value,
        numeroOP: document.getElementById('numeroOP').value || 'N/A',
        tipoFrete: document.getElementById('tipoFrete').value,
        tipoProduto: document.getElementById('tipoProduto').value,
        vendaTriangular: document.getElementById('vendaTriangular').value,
        regimeRET: document.getElementById('regimeRET').value,
        observacoes: document.getElementById('observacoes').value
    };

    // Tabela de preços selecionada
    const tabelaPrecos = document.querySelector('input[name="tabelaPrecos"]:checked');
    dados.tabelaPrecos = tabelaPrecos ? tabelaPrecos.value : '';

    // Dados de frete
    if (dados.tipoFrete === 'FOB') {
        dados.transportadora = document.getElementById('transportadoraFOB').value;
    } else if (dados.tipoFrete === 'CIF') {
        dados.transportadora = document.getElementById('transportadoraCIF').value;
    }

    // Dados de triangulação
    if (dados.vendaTriangular === 'Sim') {
        dados.dadosTriangulacao = document.getElementById('dadosTriangulacao').value;
    }

    // Produtos
    dados.produtos = [];
    const produtoElements = document.querySelectorAll('.produto-item');

    produtoElements.forEach(produto => {
        const metragem = parseFloat(produto.querySelector('input[name="metragem"]').value) || 0;
        const preco = parseFloat(produto.querySelector('input[name="preco"]').value) || 0;

        dados.produtos.push({
            artigo: produto.querySelector('input[name="artigo"]').value,
            codigo: produto.querySelector('input[name="codigo"]').value,
            desenho_cor: produto.querySelector('input[name="desenho_cor"]').value,
            metragem: metragem,
            preco: preco,
            subtotal: metragem * preco
        });
    });

    // Calcular valor total
    dados.valorTotal = dados.produtos.reduce((total, produto) => total + produto.subtotal, 0);

    return dados;
}

function limparFormulario() {
    document.getElementById('pedidoForm').reset();
    document.getElementById('produtos-container').innerHTML = '';
    document.getElementById('valorTotal').textContent = '0,00';
    contadorProdutos = 0;
    limparDadosCliente();
}

// ========== INICIALIZAR ==========
document.addEventListener('DOMContentLoaded', function () {
    // Adicionar primeiro produto automaticamente
    adicionarProduto();
});
        </script >
    </body >
    </html > '''

return render_template_string(html_content)

// ========== MANIPULAÇÃO DE PRODUTOS ==========
function adicionarProduto() {
    contadorProdutos++;
    const container = document.getElementById('produtos-container');

    const produtoDiv = document.createElement('div');
    produtoDiv.className = 'produto-item mb-4 p-3 border rounded';
    produtoDiv.id = `produto-${contadorProdutos}`;

    produtoDiv.innerHTML = `
        <div class="row">
            <div class="col-md-3 mb-3">
                <label class="form-label">Artigo *</label>
                <input type="text" class="form-control" name="artigo" required>
            </div>
            <div class="col-md-2 mb-3">
                <label class="form-label">Código *</label>
                <input type="text" class="form-control" name="codigo" required>
            </div>
            <div class="col-md-3 mb-3">
                <label class="form-label">Desenho/Cor *</label>
                <input type="text" class="form-control" name="desenho_cor" required>
            </div>
            <div class="col-md-2 mb-3">
                <label class="form-label">Metragem *</label>
                <input type="number" class="form-control" name="metragem" step="0.01" min="0" required 
                       onchange="calcularSubtotal(${contadorProdutos})">
            </div>
            <div class="col-md-2 mb-3">
                <label class="form-label">Preço Unit. *</label>
                <input type="number" class="form-control" name="preco" step="0.01" min="0" required
                       onchange="calcularSubtotal(${contadorProdutos})">
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <strong>Subtotal: R$ <span id="subtotal-${contadorProdutos}">0,00</span></strong>
            </div>
            <div class="col-md-6 text-end">
                <button type="button" class="btn btn-danger btn-sm" onclick="removerProduto(${contadorProdutos})">
                    🗑️ Remover
                </button>
            </div>
        </div>
    `;

    container.appendChild(produtoDiv);
}

function removerProduto(id) {
    const produto = document.getElementById(`produto-${id}`);
    if (produto) {
        produto.remove();
        calcularTotal();
    }
}

function calcularSubtotal(id) {
    const produto = document.getElementById(`produto-${id}`);
    const metragem = parseFloat(produto.querySelector('[name="metragem"]').value) || 0;
    const preco = parseFloat(produto.querySelector('[name="preco"]').value) || 0;
    const subtotal = metragem * preco;

    document.getElementById(`subtotal-${id}`).textContent = subtotal.toFixed(2);
    calcularTotal();
}

function calcularTotal() {
    let total = 0;
    document.querySelectorAll('.produto-item').forEach(produto => {
        const metragem = parseFloat(produto.querySelector('[name="metragem"]').value) || 0;
        const preco = parseFloat(produto.querySelector('[name="preco"]').value) || 0;
        total += metragem * preco;
    });

    document.getElementById('valorTotal').textContent = total.toFixed(2);
}

// ========== CONTADOR DE CARACTERES ==========
document.getElementById('observacoes').addEventListener('input', function () {
    const count = this.value.length;
    document.getElementById('contadorCaracteres').textContent = count;
});

// ========== ENVIO DO FORMULÁRIO ==========
document.getElementById('pedidoForm').addEventListener('submit', function (e) {
    e.preventDefault();

    // Validar produtos
    const produtos = document.querySelectorAll('.produto-item');
    if (produtos.length === 0) {
        alert('❌ Adicione pelo menos um produto ao pedido!');
        return;
    }

    // Coletar dados
    const dados = {
        nomeRepresentante: document.getElementById('nomeRepresentante').value,
        razaoSocial: document.getElementById('razaoSocial').value,
        cnpj: document.getElementById('cnpj').value,
        telefone: document.getElementById('telefone').value,
        prazoPagamento: document.getElementById('prazoPagamento').value,
        tipoPedido: document.getElementById('tipoPedido').value,
        numeroOP: document.getElementById('numeroOP').value,
        tipoFrete: document.getElementById('tipoFrete').value,
        tipoProduto: document.getElementById('tipoProduto').value,
        vendaTriangular: document.getElementById('vendaTriangular').value,
        regimeRET: document.getElementById('regimeRET').value,
        tabelaPrecos: document.querySelector('input[name="tabelaPrecos"]:checked')?.value,
        observacoes: document.getElementById('observacoes').value,
        valorTotal: parseFloat(document.getElementById('valorTotal').textContent),
        produtos: []
    };

    // Coletar produtos
    produtos.forEach(produto => {
        const artigo = produto.querySelector('[name="artigo"]').value;
        const codigo = produto.querySelector('[name="codigo"]').value;
        const desenho_cor = produto.querySelector('[name="desenho_cor"]').value;
        const metragem = parseFloat(produto.querySelector('[name="metragem"]').value);
        const preco = parseFloat(produto.querySelector('[name="preco"]').value);

        dados.produtos.push({
            artigo,
            codigo,
            desenho_cor,
            metragem,
            preco,
            subtotal: metragem * preco
        });
    });

    // Enviar pedido
    enviarPedido(dados);
});

function enviarPedido(dados) {
    const submitBtn = document.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;

    submitBtn.innerHTML = '⏳ Enviando...';
    submitBtn.disabled = true;

    fetch('/submit_pedido', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(dados)
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(`✅ ${data.message}`);
                limparFormulario();
            } else {
                alert(`❌ Erro: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('❌ Erro ao enviar pedido. Tente novamente.');
        })
        .finally(() => {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        });
}

function limparFormulario() {
    document.getElementById('pedidoForm').reset();
    document.getElementById('produtos-container').innerHTML = '';
    document.getElementById('valorTotal').textContent = '0,00';
    contadorProdutos = 0;
}

// Adicionar primeiro produto automaticamente
adicionarProduto();

