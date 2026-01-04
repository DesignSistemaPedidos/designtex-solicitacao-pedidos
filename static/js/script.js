// ========== CONFIGURAÇÃO E INICIALIZAÇÃO ==========
let contadorProdutos = 0;
let clientesCache = [];
let precosCache = [];

// 🔍 SISTEMA DE AUTOCOMPLETE INTELIGENTE
class AutocompleteCliente {
    constructor() {
        this.initEventListeners();
        this.setupValidation();
        this.carregarDadosIniciais();
    }

    async carregarDadosIniciais() {
        try {
            // Carregar clientes do Railway
            const responseClientes = await fetch('/clientes');
            const dadosClientes = await responseClientes.json();
            clientesCache = dadosClientes.clientes || [];
            
            // Carregar preços do Railway
            const responsePrecos = await fetch('/precos');
            const dadosPrecos = await responsePrecos.json();
            precosCache = dadosPrecos.precos || [];
            
            console.log(`✅ Carregados ${clientesCache.length} clientes e ${precosCache.length} preços do Railway`);
            
        } catch (error) {
            console.error('❌ Erro ao carregar dados iniciais:', error);
            // Fallback para dados locais se necessário
        }
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

        // Listener para cálculo automático
        document.addEventListener('change', (e) => {
            if (e.target.matches('.produto-metragem, .produto-preco')) {
                this.calculaFrete();
            }
        });
    }

    async handleRazaoInput(event) {
        const termo = event.target.value.trim();

        if (termo.length < 2) {
            this.hideDropdown();
            return;
        }

        try {
            // Buscar primeiro no cache
            let resultados = clientesCache.filter(cliente => 
                cliente.razao_social.toLowerCase().includes(termo.toLowerCase()) ||
                cliente.nome_fantasia.toLowerCase().includes(termo.toLowerCase())
            );

            // Se não encontrou no cache, buscar na API
            if (resultados.length === 0) {
                const response = await fetch(`/api/buscar_clientes?q=${encodeURIComponent(termo)}`);
                const data = await response.json();
                resultados = data.clientes || [];
            }

            this.showDropdown(resultados, 'razao');
        } catch (error) {
            console.error('Erro ao buscar clientes:', error);
            // Usar dados do cache como fallback
            const resultados = clientesCache.filter(cliente => 
                cliente.razao_social.toLowerCase().includes(termo.toLowerCase())
            );
            this.showDropdown(resultados, 'razao');
        }
    }

    async handleCnpjInput(event) {
        let cnpj = event.target.value;

        // Formatação automática do CNPJ
        cnpj = this.formatCNPJ(cnpj);
        event.target.value = cnpj;

        if (cnpj.length >= 14) {
            try {
                // Buscar primeiro no cache
                let resultados = clientesCache.filter(cliente => 
                    cliente.cnpj.replace(/\D/g, '') === cnpj.replace(/\D/g, '')
                );

                // Se não encontrou no cache, buscar na API
                if (resultados.length === 0) {
                    const response = await fetch(`/api/buscar_clientes?q=${encodeURIComponent(cnpj)}`);
                    const data = await response.json();
                    resultados = data.clientes || [];
                }

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

        if (resultados.length === 0) return;

        const dropdown = document.createElement('div');
        dropdown.id = 'autocomplete-dropdown';
        dropdown.className = 'autocomplete-dropdown';
        dropdown.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        `;

        resultados.forEach(resultado => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            item.style.cssText = `
                padding: 12px;
                border-bottom: 1px solid #eee;
                cursor: pointer;
                transition: background-color 0.2s;
            `;
            
            item.innerHTML = `
                <div style="font-weight: bold; color: #2c5aa0;">${resultado.cnpj}</div>
                <div style="color: #333; margin-top: 4px;">${resultado.razao_social}</div>
                ${resultado.nome_fantasia ? `<div style="color: #666; font-size: 0.9em;">${resultado.nome_fantasia}</div>` : ''}
            `;

            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = '#f8f9fa';
            });

            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'white';
            });

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
        
        // Preencher nome fantasia se existir
        if (cliente.nome_fantasia) {
            const nomeFantasiaField = document.getElementById('nomeFantasia');
            if (nomeFantasiaField) {
                nomeFantasiaField.value = cliente.nome_fantasia;
            }
        }

        this.hideDropdown();
        this.showValidationSuccess('✅ Cliente selecionado com sucesso!');
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
            // Validar no cache primeiro
            const clienteCache = clientesCache.find(cliente => 
                cliente.cnpj.replace(/\D/g, '') === cnpj.replace(/\D/g, '') ||
                cliente.razao_social.toLowerCase() === razao.toLowerCase()
            );

            if (clienteCache) {
                document.getElementById('cnpj').value = clienteCache.cnpj;
                document.getElementById('razaoSocial').value = clienteCache.razao_social;
                this.showValidationSuccess('✅ Cliente encontrado!');
                return;
            }

            // Validar na API se não encontrou no cache
            const response = await fetch(`/api/validar_cliente?cnpj=${encodeURIComponent(cnpj)}&razao=${encodeURIComponent(razao)}`);
            const result = await response.json();

            if (result.valido) {
                document.getElementById('cnpj').value = result.cnpj;
                document.getElementById('razaoSocial').value = result.razao_social;
                this.showValidationSuccess(result.message);
            } else {
                this.showValidationError(result.message || '❌ Cliente não encontrado');
            }
        } catch (error) {
            console.error('Erro na validação:', error);
            this.showValidationError('⚠️ Erro ao validar cliente');
        }
    }

    calculaFrete() {
        const products = document.querySelectorAll('.produto-item');
        let total = 0;

        products.forEach(product => {
            const metragInput = product.querySelector('input[name="metragem"]');
            const precoInput = product.querySelector('input[name="preco"]');
            
            if (metragInput && precoInput) {
                const metragem = parseFloat(metragInput.value) || 0;
                const preco = parseFloat(precoInput.value) || 0;
                total += metragem * preco;
            }
        });

        // Atualizar total na tela
        const totalElement = document.getElementById('valorTotal');
        if (totalElement) {
            totalElement.textContent = total.toFixed(2).replace('.', ',');
        }

        // Lógica de frete automático
        const tipoFreteSelect = document.querySelector('select[name="tipoFrete"]');
        const transportadoraCIF = document.getElementById('transportadoraCIF');
        
        if (total > 5000) {
            if (tipoFreteSelect) {
                tipoFreteSelect.value = 'CIF';
            }
            if (transportadoraCIF) {
                transportadoraCIF.disabled = true;
                transportadoraCIF.value = 'DESIGNTEX';
            }
        } else {
            if (transportadoraCIF) {
                transportadoraCIF.disabled = false;
            }
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
        messageDiv.style.cssText = `
            padding: 8px 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 0.9em;
            ${type === 'success' ? 
                'background: #d4edda; color: #155724; border: 1px solid #c3e6cb;' :
                'background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;'
            }
        `;
        messageDiv.textContent = message;

        const cnpjInput = document.getElementById('cnpj');
        cnpjInput.parentNode.insertBefore(messageDiv, cnpjInput.nextSibling);

        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 4000);
    }

    setupValidation() {
        const nomeRepresentante = document.getElementById('nomeRepresentante');
        const telefone = document.getElementById('telefone');

        if (nomeRepresentante) {
            nomeRepresentante.addEventListener('blur', this.validateRepresentante);
        }

        if (telefone) {
            telefone.addEventListener('input', this.formatTelefone);
        }
    }

    validateRepresentante(event) {
        const nome = event.target.value.trim();
        if (nome.length < 2) {
            event.target.style.borderColor = '#e74c3c';
            event.target.style.boxShadow = '0 0 5px rgba(231, 76, 60, 0.3)';
        } else {
            event.target.style.borderColor = '#27ae60';
            event.target.style.boxShadow = '0 0 5px rgba(39, 174, 96, 0.3)';
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
                <input type="text" class="form-control" name="artigo" required 
                       onchange="buscarPrecoAutomatico(${contadorProdutos})">
            </div>
            <div class="col-md-2 mb-3">
                <label class="form-label">Código *</label>
                <input type="text" class="form-control" name="codigo" required 
                       onchange="buscarPrecoAutomatico(${contadorProdutos})">
            </div>
            <div class="col-md-3 mb-3">
                <label class="form-label">Desenho/Cor *</label>
                <input type="text" class="form-control" name="desenho_cor" required>
            </div>
            <div class="col-md-2 mb-3">
                <label class="form-label">Metragem *</label>
                <input type="number" class="form-control produto-metragem" name="metragem" 
                       step="0.01" min="0" required onchange="calcularSubtotal(${contadorProdutos})">
            </div>
            <div class="col-md-2 mb-3">
                <label class="form-label">Preço Unit. *</label>
                <input type="number" class="form-control produto-preco" name="preco" 
                       step="0.01" min="0" required onchange="calcularSubtotal(${contadorProdutos})">
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <strong>Subtotal: R$ <span id="subtotal-${contadorProdutos}">0,00</span></strong>
                <div id="preco-sugerido-${contadorProdutos}" class="text-muted mt-1"></div>
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

function buscarPrecoAutomatico(id) {
    const produto = document.getElementById(`produto-${id}`);
    const artigo = produto.querySelector('[name="artigo"]').value.trim();
    const codigo = produto.querySelector('[name="codigo"]').value.trim();
    
    if (!artigo && !codigo) return;

    // Buscar no cache de preços
    const precoEncontrado = precosCache.find(preco => 
        preco.artigo.toLowerCase().includes(artigo.toLowerCase()) ||
        preco.codigo.toLowerCase().includes(codigo.toLowerCase())
    );

    if (precoEncontrado) {
        // Sugerir preço baseado na tabela selecionada
        const tabelaSelecionada = document.querySelector('input[name="tabelaPrecos"]:checked')?.value;
        let precoSugerido = 0;

        switch (tabelaSelecionada) {
            case 'normal':
                precoSugerido = precoEncontrado.icms_18 || precoEncontrado.icms_12 || precoEncontrado.icms_7;
                break;
            case 'ld':
                precoSugerido = precoEncontrado.icms_18_ld || precoEncontrado.icms_12_ld || precoEncontrado.icms_7_ld;
                break;
            default:
                precoSugerido = precoEncontrado.icms_18;
        }

        if (precoSugerido > 0) {
            const precoInput = produto.querySelector('[name="preco"]');
            precoInput.value = precoSugerido.toFixed(2);
            
            const suggestionDiv = document.getElementById(`preco-sugerido-${id}`);
            suggestionDiv.innerHTML = `💡 Preço sugerido aplicado: R$ ${precoSugerido.toFixed(2)}`;
            suggestionDiv.style.color = '#28a745';
            
            calcularSubtotal(id);
        }
    }
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

    document.getElementById(`subtotal-${id}`).textContent = subtotal.toFixed(2).replace('.', ',');
    calcularTotal();
}

function calcularTotal() {
    let total = 0;
    document.querySelectorAll('.produto-item').forEach(produto => {
        const metragem = parseFloat(produto.querySelector('[name="metragem"]').value) || 0;
        const preco = parseFloat(produto.querySelector('[name="preco"]').value) || 0;
        total += metragem * preco;
    });

    const valorTotalElement = document.getElementById('valorTotal');
    if (valorTotalElement) {
        valorTotalElement.textContent = total.toFixed(2).replace('.', ',');
    }
}

// ========== CONTADOR DE CARACTERES ==========
function initContadorCaracteres() {
    const observacoes = document.getElementById('observacoes');
    if (observacoes) {
        observacoes.addEventListener('input', function () {
            const count = this.value.length;
            const contador = document.getElementById('contadorCaracteres');
            if (contador) {
                contador.textContent = count;
                
                // Indicador visual para limite de caracteres
                if (count > 500) {
                    contador.style.color = '#dc3545';
                } else if (count > 400) {
                    contador.style.color = '#fd7e14';
                } else {
                    contador.style.color = '#6c757d';
                }
            }
        });
    }
}

// ========== ENVIO DO FORMULÁRIO ==========
function initFormularioSubmit() {
    const form = document.getElementById('pedidoForm');
    if (!form) return;

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        // Validar se há pelo menos um produto
        const produtos = document.querySelectorAll('.produto-item');
        if (produtos.length === 0) {
            alert('⚠️ Adicione pelo menos um produto ao pedido!');
            return;
        }

        // Validar campos obrigatórios
        const camposObrigatorios = ['nomeRepresentante', 'razaoSocial', 'cnpj'];
        let camposVazios = [];

        camposObrigatorios.forEach(campo => {
            const elemento = document.getElementById(campo);
            if (!elemento || !elemento.value.trim()) {
                camposVazios.push(campo);
            }
        });

        if (camposVazios.length > 0) {
            alert(`⚠️ Preencha os campos obrigatórios: ${camposVazios.join(', ')}`);
            return;
        }

        // Coletar dados do formulário
        const dadosPedido = coletarDadosFormulario();

        // Mostrar loading
        const btnSubmit = document.querySelector('button[type="submit"]');
        const textoOriginal = btnSubmit.innerHTML;
        btnSubmit.innerHTML = '📤 Enviando pedido...';
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
            if (data.success || data.status === 'success') {
                const numeroPedido = data.numero_pedido || data.pedido_numero || 'N/A';
                alert(`✅ Pedido ${numeroPedido} enviado com sucesso!\n\n📧 Confirmação enviada por email!`);
                limparFormulario();
            } else {
                alert(`❌ Erro: ${data.error || data.message || 'Erro desconhecido'}`);
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('❌ Erro ao enviar pedido. Verifique sua conexão e tente novamente.');
        })
        .finally(() => {
            btnSubmit.innerHTML = textoOriginal;
            btnSubmit.disabled = false;
        });
    });
}

function coletarDadosFormulario() {
    // Dados do cabeçalho
    const dados = {
        nomeRepresentante: document.getElementById('nomeRepresentante')?.value || '',
        razaoSocial: document.getElementById('razaoSocial')?.value || '',
        cnpj: document.getElementById('cnpj')?.value || '',
        telefone: document.getElementById('telefone')?.value || '',
        prazoPagamento: document.getElementById('prazoPagamento')?.value || '',
        tipoPedido: document.getElementById('tipoPedido')?.value || '',
        numeroOP: document.getElementById('numeroOP')?.value || 'N/A',
        tipoFrete: document.getElementById('tipoFrete')?.value || '',
        tipoProduto: document.getElementById('tipoProduto')?.value || '',
        vendaTriangular: document.getElementById('vendaTriangular')?.value || '',
        regimeRET: document.getElementById('regimeRET')?.value || '',
        observacoes: document.getElementById('observacoes')?.value || ''
    };

    // Tabela de preços selecionada
    const tabelaPrecos = document.querySelector('input[name="tabelaPrecos"]:checked');
    dados.tabelaPrecos = tabelaPrecos ? tabelaPrecos.value : '';

    // Dados de frete
    if (dados.tipoFrete === 'FOB') {
        dados.transportadora = document.getElementById('transportadoraFOB')?.value || '';
    } else if (dados.tipoFrete === 'CIF') {
        dados.transportadora = document.getElementById('transportadoraCIF')?.value || '';
    }

    // Dados de triangulação
    if (dados.vendaTriangular === 'Sim') {
        dados.dadosTriangulacao = document.getElementById('dadosTriangulacao')?.value || '';
    }

    // Produtos
    dados.produtos = [];
    const produtoElements = document.querySelectorAll('.produto-item');

    produtoElements.forEach(produto => {
        const metragem = parseFloat(produto.querySelector('input[name="metragem"]')?.value) || 0;
        const preco = parseFloat(produto.querySelector('input[name="preco"]')?.value) || 0;

        dados.produtos.push({
            artigo: produto.querySelector('input[name="artigo"]')?.value || '',
            codigo: produto.querySelector('input[name="codigo"]')?.value || '',
            desenho_cor: produto.querySelector('input[name="desenho_cor"]')?.value || '',
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
    const form = document.getElementById('pedidoForm');
    if (form) {
        form.reset();
    }

    const container = document.getElementById('produtos-container');
    if (container) {
        container.innerHTML = '';
    }

    const valorTotal = document.getElementById('valorTotal');
    if (valorTotal) {
        valorTotal.textContent = '0,00';
    }

    contadorProdutos = 0;
    
    // Adicionar primeiro produto novamente
    adicionarProduto();
}

// ========== INICIALIZAÇÃO PRINCIPAL ==========
document.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 Iniciando Designtex Pedidos - Versão Railway');
    
    // Inicializar classes e componentes
    new AutocompleteCliente();
    initContadorCaracteres();
    initFormularioSubmit();
    
    // Adicionar primeiro produto automaticamente
    adicionarProduto();
    
    console.log('✅ Sistema inicializado com sucesso!');
});

// ========== UTILITÁRIOS ==========
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(valor);
}

function formatarCNPJ(cnpj) {
    return cnpj.replace(/\D/g, '')
               .replace(/(\d{2})(\d)/, '$1.$2')
               .replace(/(\d{3})(\d)/, '$1.$2')
               .replace(/(\d{3})(\d)/, '$1/$2')
               .replace(/(\d{4})(\d)/, '$1-$2');
}

// Exportar funções para uso global se necessário
window.adicionarProduto = adicionarProduto;
window.removerProduto = removerProduto;
window.calcularSubtotal = calcularSubtotal;
window.buscarPrecoAutomatico = buscarPrecoAutomatico;
