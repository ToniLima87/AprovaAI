import sqlite3
import os
import re

def limpar_nome_ficheiro(nome):
    nome_limpo = re.sub(r'[\\/*?:"<>|]', '', nome)
    return nome_limpo.lower().replace(' ', '_')

def limpar_markdown_excessivo(texto):
    """
    Remove linhas em branco duplicadas, limpa espaços inúteis
    e remove tabelas Markdown corrompidas ou incompletas no final do arquivo.
    """
    if not texto:
        return ""
    
    # 1. Divide o texto em linhas para analisar o final do documento
    linhas = [linha.rstrip() for linha in texto.splitlines()]
    
    # 2. Remove linhas do final se forem apenas marcações de tabela quebradas (como | :--- | :--- |)
    # ou se forem apenas espaços/traços longos sem conteúdo real.
    while linhas:
        ultima_linha = linhas[-1].strip()
        
        # Se a última linha for apenas traços, pipes, dois pontos e espaços (ex: | :--- | :--- )
        if ultima_linha and re.match(r'^[|:\-\s]+$', ultima_linha):
            linhas.pop() # Remove a linha corrompida
        elif not ultima_linha:
            linhas.pop() # Remove linhas em branco no final
        else:
            break # Encontrou conteúdo real, para de remover
            
    # 3. Junta as linhas novamente
    texto_limpo = "\n".join(linhas)
    
    # 4. Substitui 3 ou mais quebras de linha seguidas por apenas 2 (\n\n) para manter o padrão
    texto_limpo = re.sub(r'\n{3,}', '\n\n', texto_limpo)
    
    return texto_limpo.strip()

def exportar_ultimo_plano():
    if not os.path.exists("aprova_ai.db"):
        print("❌ Banco de dados 'aprova_ai.db' não encontrado na raiz!")
        return
        
    conn = sqlite3.connect("aprova_ai.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT concurso, banca, cronograma 
        FROM planos_estudo 
        ORDER BY id DESC 
        LIMIT 1
    """)
    res = cursor.fetchone()
    conn.close()
    
    if not res:
        print("📭 Nenhum plano encontrado no banco de dados.")
        return
        
    concurso, banca, cronograma = res
    
    # Executa a limpeza cirúrgica do texto
    cronograma_limpo = limpar_markdown_excessivo(cronograma)
    
    pasta_destino = "planos_gerados"
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
        
    nome_base = limpar_nome_ficheiro(concurso)
    caminho_completo = os.path.join(pasta_destino, f"plano_{nome_base}.md")
    
    with open(caminho_completo, "w", encoding="utf-8") as f:
        f.write(f"# 🎯 Plano de Estudos: {concurso}\n")
        f.write(f"**Banca Organizadora:** {banca}\n")
        f.write("---\n\n")
        f.write(cronograma_limpo)
        
    print(f"💾 [Sucesso] Ficheiro limpo sem linhas quebradas gerado em: {caminho_completo}")

if __name__ == "__main__":
    exportar_ultimo_plano()