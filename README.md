# 🏭 DESIGNTEX TECIDOS - Sistema de Pedidos

Sistema de pedidos de vendas desenvolvido em Python Flask com PostgreSQL.

## 🚀 Features

- ✅ PostgreSQL (local e Railway Cloud)
- ✅ API REST para clientes e preços
- ✅ Sistema de numeração automática de pedidos
- ✅ Health check endpoint
- ✅ Configuração flexível (local/produção)

## 📡 Endpoints

- `GET /` - Homepage
- `GET /health` - Status do sistema
- `GET /clientes` - Lista de clientes (JSON)
- `GET /precos` - Tabela de preços (JSON)

## 🔧 Como usar

### Local
```bash
pip install -r requirements.txt
python app.py
