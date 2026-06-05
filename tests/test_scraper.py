from src.tools.scraper_tools import buscar_vagas_concurso

def testar():
    print("Buscando concursos de TI no PCI Concursos...")
    resultado = buscar_vagas_concurso("tecnologia da informação")
    print("\n--- RESULTADO DO SCRAPER ---")
    print(resultado)

if __name__ == "__main__":
    testar()