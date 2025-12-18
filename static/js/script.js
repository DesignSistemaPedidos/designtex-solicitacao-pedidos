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
