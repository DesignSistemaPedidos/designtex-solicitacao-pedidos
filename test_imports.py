try:
    import psycopg2
    print("✅ psycopg2 importado com sucesso!")

    import flask
    print("✅ Flask importado com sucesso!")

    import reportlab
    print("✅ ReportLab importado com sucesso!")

    print("🎉 Todas as dependências estão OK!")

except ImportError as e:
    print(f"❌ Erro de importação: {e}")
