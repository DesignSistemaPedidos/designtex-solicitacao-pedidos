import psycopg2


def testar_funcoes_pedidos():
    """Testar todas as funções relacionadas a pedidos"""

    database_url = "postgresql://postgres:JKOUPjecfpgkdvSOGUepsTvyloqygzFw@centerbeam.proxy.rlwy.net:15242/railway"

    try:
        print("🔍 TESTANDO FUNÇÕES DE PEDIDOS")
        print("-" * 50)

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # 1. Verificar tabela pedidos
        print("📋 Verificando tabela pedidos...")
        cursor.execute("SELECT COUNT(*) FROM pedidos")
        count_pedidos = cursor.fetchone()[0]
        print(f"   ✅ Pedidos existentes: {count_pedidos}")

        # 2. Verificar sequência
        print("\n🔢 Verificando sequência...")
        cursor.execute(
            "SELECT ultimo_numero FROM sequencia_pedidos WHERE id = 1")
        sequencia = cursor.fetchone()
        if sequencia:
            print(f"   ✅ Último número: {sequencia[0]}")
            proximo = sequencia[0] + 1
            print(f"   ✅ Próximo número: {proximo:04d}")

        # 3. Testar inserção de pedido
        print("\n💾 Testando inserção de pedido...")

        # Obter próximo número
        cursor.execute(
            "UPDATE sequencia_pedidos SET ultimo_numero = ultimo_numero + 1 WHERE id = 1 RETURNING ultimo_numero")
        numero = cursor.fetchone()[0]
        numero_formatado = str(numero).zfill(4)

        # Inserir pedido de teste
        pedido_teste = {
            'numero_pedido': numero_formatado,
            'cnpj_cliente': '12.345.678/0001-90',
            'representante': 'TESTE REPRESENTANTE',
            'observacoes': 'Pedido de teste do sistema',
            'valor_total': 1500.50
        }

        cursor.execute("""
            INSERT INTO pedidos (numero_pedido, cnpj_cliente, representante, observacoes, valor_total)
            VALUES (%(numero_pedido)s, %(cnpj_cliente)s, %(representante)s, %(observacoes)s, %(valor_total)s)
            RETURNING id, numero_pedido, created_at
        """, pedido_teste)

        resultado = cursor.fetchone()
        conn.commit()

        print(f"   ✅ Pedido criado com sucesso!")
        print(f"   📄 ID: {resultado[0]}")
        print(f"   📄 Número: {resultado[1]}")
        print(f"   📄 Data: {resultado[2]}")

        # 4. Verificar o pedido criado
        print("\n📋 Verificando pedido criado...")
        cursor.execute(
            "SELECT * FROM pedidos WHERE numero_pedido = %s", (numero_formatado,))
        pedido = cursor.fetchone()

        if pedido:
            print(
                f"   ✅ Pedido encontrado: {pedido[1]} - {pedido[2]} - R$ {pedido[5]}")

        cursor.close()
        conn.close()

        print("\n🎉 TODAS AS FUNÇÕES DE PEDIDOS ESTÃO FUNCIONANDO!")
        return True

    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


if __name__ == '__main__':
    testar_funcoes_pedidos()
