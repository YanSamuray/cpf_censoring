# main.py
from pathlib import Path
from src import censor, utils

def main():
    base_dir = Path(__file__).resolve().parent
    input_dir, output_dir = utils.get_data_dirs(base_dir)
    
    if not input_dir.exists():
        print(f"Diretório de entrada não encontrado: {input_dir}")
        return

    print("Iniciando o processamento dos PDFs...\n")
    censor.process_all_pdfs(input_dir, output_dir)
    print("Processamento concluído.")

if __name__ == '__main__':
    main()