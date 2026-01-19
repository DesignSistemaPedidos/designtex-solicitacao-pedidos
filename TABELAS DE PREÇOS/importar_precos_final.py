import psycopg2
import csv

# Configurações do banco Railway
DATABASE_URL = "postgresql://postgres:bkzJfMipXuDdSBzHSsUxZiftFmejCwnD@interchange.proxy.rlwy.net:14507/railway"
CSV_FILE = "precos_consolidados.csv"


def parse_float(valor):
    """Converte string para float, retorna None se vazio."""
    try:
        valor = str(valor).replace(',', '.').strip()
        return float(valor) if valor else None
    except Exception:
        return None


def main():
    # Conexão
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Limpa a tabela antes de importar (opcional, comente se não quiser apagar antes!)
    cur.execute("DELETE FROM precos_normal;")
    conn.commit()

    # Leitura do CSV e inserção
    with open(CSV_FILE, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Remove espaços e padroniza acesso a colunas
            artigo = row.get('artigo', '').strip()
            codigo = row.get('codigo', '').strip()
            descricao = row.get('descricao', '').strip()
            icms_18 = parse_float(row.get('icms_18', ''))
            icms_12 = parse_float(row.get('icms_12', ''))
            icms_7 = parse_float(row.get('icms_7', ''))
            ret_mg = parse_float(row.get('ret_mg', ''))
            observacao = row.get('observacao', '').strip()

            cur.execute("""
                INSERT INTO precos_normal 
                (artigo, codigo, descricao, icms_18, icms_12, icms_7, ret_mg, observacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (codigo) DO UPDATE SET 
                    artigo = EXCLUDED.artigo,
                    descricao = EXCLUDED.descricao,
                    icms_18 = EXCLUDED.icms_18,
                    icms_12 = EXCLUDED.icms_12,
                    icms_7 = EXCLUDED.icms_7,
                    ret_mg = EXCLUDED.ret_mg,
                    observacao = EXCLUDED.observacao
            """, (
                artigo,
                codigo,
                descricao,
                icms_18,
                icms_12,
                icms_7,
                ret_mg,
                observacao
            ))
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Importação concluída!")


if __name__ == '__main__':
    main()
