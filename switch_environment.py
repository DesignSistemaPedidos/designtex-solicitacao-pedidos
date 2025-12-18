import os

def alterar_ambiente():
    """Script para alterar entre local e Railway"""
    
    print("🔄 ALTERNAR AMBIENTE")
    print("1. LOCAL (desenvolvimento)")
    print("2. RAILWAY (produção)")
    
    escolha = input("Escolha (1/2): ").strip()
    
    # Ler arquivo .env atual
    env_file = '.env'
    lines = []
    
    try:
        with open(env_file, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("❌ Arquivo .env não encontrado")
        return
    
    # Atualizar linha ENVIRONMENT
    new_lines = []
    found = False
    
    for line in lines:
        if line.startswith('ENVIRONMENT='):
            found = True
            if escolha == '1':
                new_lines.append('ENVIRONMENT=development\n')
                print("✅ Configurado para LOCAL")
            elif escolha == '2':
                new_lines.append('ENVIRONMENT=production\n')
                print("✅ Configurado para RAILWAY")
            else:
                print("❌ Opção inválida")
                return
        else:
            new_lines.append(line)
    
    if not found:
        if escolha == '1':
            new_lines.append('ENVIRONMENT=development\n')
            print("✅ Configurado para LOCAL")
        elif escolha == '2':
            new_lines.append('ENVIRONMENT=production\n')
            print("✅ Configurado para RAILWAY")
    
    # Salvar arquivo .env
    with open(env_file, 'w') as f:
        f.writelines(new_lines)
    
    print("🔄 Execute 'python app.py' para aplicar")

if __name__ == '__main__':
    alterar_ambiente()
