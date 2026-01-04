import requests
import json

def testar_email():
    """Testar envio de email"""
    
    url = "http://127.0.0.1:5001/test-email"
    
    dados = {
        "email": "seu_email@gmail.com"  # SUBSTITUA pelo seu email
    }
    
    try:
        print("📧 Testando envio de email...")
        response = requests.post(url, json=dados)
        
        if response.status_code == 200:
            resultado = response.json()
            print(f"✅ {resultado['mensagem']}")
        else:
            print(f"❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro ao testar: {e}")

if __name__ == '__main__':
    testar_email()
