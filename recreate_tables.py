import psycopg2
import os


def recriar_tabelas_railway():
    """Recriar tabelas no Railway PostgreSQL"""

    database_url = "postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway"

    try:
        print("🔧 RECRIANDO TABELAS NO RAILWAY")
        print("=" * 50)

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # 1. LIMPAR TABELAS EXISTENTES (se houver conflitos)
        print("🧹 Limpando tabelas existentes...")

        tabelas_para_limpar = ['pedidos', 'clientes',
                               'precos_normal', 'precos_ld', 'sequencia_pedidos']

        for tabela in tabelas_para_limpar:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")
                print(f"   🗑️  Removida: {tabela}")
            except:
                pass

        conn.commit()

        # 2. CRIAR TABELAS DO ZERO
        print("\n📋 Criando tabelas...")

        # Tabela clientes
        cursor.execute("""
            CREATE TABLE clientes (
                id SERIAL PRIMARY KEY,
                cnpj VARCHAR(18) UNIQUE NOT NULL,
                razao_social VARCHAR(200) NOT NULL,
                nome_fantasia VARCHAR(150),
                telefone VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ clientes")

        # Tabela pedidos
        cursor.execute("""
            CREATE TABLE pedidos (
                id SERIAL PRIMARY KEY,
                numero_pedido VARCHAR(10) UNIQUE NOT NULL,
                cnpj_cliente VARCHAR(18),
                representante VARCHAR(100),
                observacoes TEXT,
                valor_total DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ pedidos")

        # Tabela sequencia_pedidos
        cursor.execute("""
            CREATE TABLE sequencia_pedidos (
                id INTEGER PRIMARY KEY DEFAULT 1,
                ultimo_numero INTEGER DEFAULT 0
            )
        """)
        print("   ✅ sequencia_pedidos")

        # Tabela precos_normal
        cursor.execute("""
            CREATE TABLE precos_normal (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                icms_18 DECIMAL(10,2),
                icms_12 DECIMAL(10,2),
                icms_7 DECIMAL(10,2),
                ret_mg DECIMAL(10,2)
            )
        """)
        print("   ✅ precos_normal")

        # Tabela precos_ld
        cursor.execute("""
            CREATE TABLE precos_ld (
                id SERIAL PRIMARY KEY,
                artigo VARCHAR(50),
                codigo VARCHAR(20),
                descricao VARCHAR(200),
                icms_18_ld DECIMAL(10,2),
                icms_12_ld DECIMAL(10,2),
                icms_7_ld DECIMAL(10,2),
                ret_ld_mg DECIMAL(10,2)
            )
        """)
        print("   ✅ precos_ld")

        conn.commit()

        # 3. INSERIR DADOS INICIAIS
        print("\n📝 Inserindo dados iniciais...")

        # Sequência inicial
        cursor.execute("""
            INSERT INTO sequencia_pedidos (id, ultimo_numero) 
            VALUES (1, 0)
        """)

        # Clientes iniciais
        clientes = [
            ('12.345.678/0001-90', 'EMPRESA ABC LTDA', 'EMPRESA ABC', '11999990001'),
            ('98.765.432/0001-10', 'COMERCIAL XYZ SA',
             'COMERCIAL XYZ', '11999990002'),
            ('11.222.333/0001-44', 'DISTRIBUIDORA 123 LTDA',
             'DISTRIBUIDORA 123', '11999990003')
        ]

        for cnpj, razao, fantasia, telefone in clientes:
            cursor.execute("""
                INSERT INTO clientes (cnpj, razao_social, nome_fantasia, telefone) 
                VALUES (%s, %s, %s, %s)
            """, (cnpj, razao, fantasia, telefone))

        print(f"   👥 {len(clientes)} clientes inseridos")

        # Preços iniciais
        precos = [
            ('ALGODAO 30/1', 'ALG301', 'Tecido algodao 30/1',
             12.50, 11.80, 11.20, 10.90),
            ('POLIESTER 150D', 'POL150', 'Tecido poliester 150D',
             15.30, 14.60, 13.90, 13.50),
            ('VISCOSE 120', 'VIS120', 'Tecido viscose 120', 18.20, 17.40, 16.80, 16.20)
        ]

        for artigo, codigo, desc, p18, p12, p7, ret in precos:
            cursor.execute("""
                INSERT INTO precos_normal (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (artigo, codigo, desc, p18, p12, p7, ret))

        print(f"   💰 {len(precos)} preços inseridos")

        conn.commit()

        # 4. VERIFICAR RESULTADO
        print("\n🔍 Verificando resultado...")

        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tabelas_criadas = cursor.fetchall()

        for tabela in tabelas_criadas:
            cursor.execute(f"SELECT COUNT(*) FROM {tabela[0]}")
            count = cursor.fetchone()[0]
            print(f"   ✅ {tabela[0]}: {count} registros")

        cursor.close()
        conn.close()

        print("\n🎉 TABELAS RECRIADAS COM SUCESSO NO RAILWAY!")
        return True

    except Exception as e:
        print(f"❌ Erro ao recriar tabelas: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


if __name__ == '__main__':
    recriar_tabelas_railway()
