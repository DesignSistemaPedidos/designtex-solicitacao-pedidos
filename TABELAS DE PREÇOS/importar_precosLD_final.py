import psycopg2
import csv

DATABASE_URL = "postgresql://postgres:bkzJfMipXuDdSBzHSsUxZiftFmejCwnD@interchange.proxy.rlwy.net:14507/railway"
CSV_FILE = "PRECOS_LD.csv"


def parse_float(valor):
    try:
        valor = str(valor).replace(',', '.').strip()
        return float(valor) if valor else None
    except Exception:
        return None


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # Limpa a tabela antes de importar (opcional)
    cur.execute("DELETE FROM precos_ld;")
    conn.commit()

    with open(CSV_FILE, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            artigo = row.get('Artigo', '').strip()
            codigo = row.get('Codigo', '').strip()
            preco = parse_float(row.get('Preco', ''))
            observacao = row.get('Observacao', '').strip()

            cur.execute("""
                INSERT INTO precos_ld 
                (artigo, codigo, preco, observacao)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (codigo) DO UPDATE SET
                    artigo = EXCLUDED.artigo,
                    preco = EXCLUDED.preco,
                    observacao = EXCLUDED.observacao
            """, (
                artigo,
                codigo,
                preco,
                observacao
            ))
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Importação concluída!")


if __name__ == '__main__':
    main()
