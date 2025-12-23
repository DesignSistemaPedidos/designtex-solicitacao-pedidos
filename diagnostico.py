# diagnostico.py
import os
import json

def diagnosticar_railway():
    """Diagnosticar problemas Railway"""
    
    print("🔍 DIAGNÓSTICO RAILWAY")
    print("-" * 40)
    
    # Verificar arquivos Railway
    arquivos_railway = [
        'railway.json',
        '.railwayapp.json', 
        'railway.toml',
        'Dockerfile',
        '.railway'
    ]
    
    print("📁 Verificando arquivos Railway:")
    for arquivo in arquivos_railway:
        if os.path.exists(arquivo):
            print(f"   ⚠️  ENCONTRADO: {arquivo}")
            
            if arquivo.endswith('.json'):
                try:
                    with open(arquivo, 'r') as f:
                        content = f.read()
                        print(f"      Conteúdo: {content[:100]}...")
                        json.loads(content)  # Testar JSON
                        print(f"      ✅ JSON válido")
                except Exception as e:
                    print(f"      ❌ JSON inválido: {e}")
        else:
            print(f"   ✅ Não existe: {arquivo}")
    
    # Verificar variáveis ambiente
    print("\n🔧 Variáveis de ambiente:")
    env_vars = ['ENVIRONMENT', 'DATABASE_URL', 'RAILWAY_TOKEN']
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mascarar senha na DATABASE_URL
            if 'DATABASE_URL' in var and 'postgresql' in value:
                masked = value.split('@')[0].split(':')[:-1] + ['***@'] + [value.split('@')[1]]
                print(f"   {var}: {''.join(masked)}")
            else:
                print(f"   {var}: {value[:20]}...")
        else:
            print(f"   {var}: (não definida)")
    
    print("\n📋 Estrutura do projeto:")
    for item in os.listdir('.'):
        if os.path.isfile(item):
            print(f"   📄 {item}")
        else:
            print(f"   📁 {item}/")

if __name__ == '__main__':
    diagnosticar_railway()
