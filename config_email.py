"""
Configurações de email para DTX
Configure suas credenciais de email aqui
"""

# GMAIL (Recomendado)
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'email_remetente': 'SEU_EMAIL@gmail.com',  # ← ALTERE AQUI
    'senha_email': 'SUA_SENHA_APP',            # ← ALTERE AQUI
    'email_destino': 'pedido@designtextecidos.com.br',
    'nome_empresa': 'DTX Design Têxtil'
}

# OUTLOOK/HOTMAIL (Alternativa)
EMAIL_CONFIG_OUTLOOK = {
    'smtp_server': 'smtp-mail.outlook.com',
    'smtp_port': 587,
    'email_remetente': 'SEU_EMAIL@outlook.com',  # ← ALTERE AQUI
    'senha_email': 'SUA_SENHA',                  # ← ALTERE AQUI
    'email_destino': 'pedido@designtextecidos.com.br',
    'nome_empresa': 'DTX Design Têxtil'
}

# OUTROS PROVEDORES
EMAIL_CONFIG_OUTROS = {
    'smtp_server': 'smtp.seudominio.com.br',
    'smtp_port': 587,
    'email_remetente': 'sistema@seudominio.com.br',
    'senha_email': 'SUA_SENHA',
    'email_destino': 'pedido@designtextecidos.com.br',
    'nome_empresa': 'DTX Design Têxtil'
}
