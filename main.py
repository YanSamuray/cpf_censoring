import os
import re
import fitz  # PyMuPDF

def censor_cpfs_in_pdf(input_pdf_path: str, output_pdf_path: str):
    """
    Abre um PDF, encontra padrões de CPF e redige-os (censura) no arquivo de saída.
    
    :param input_pdf_path: Caminho completo do arquivo PDF de entrada.
    :param output_pdf_path: Caminho completo do arquivo PDF de saída.
    """
    # Regex para capturar CPFs em formatos comuns:
    # - 123.456.789-00
    # - 12345678900
    cpf_pattern = re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b')

    # Abre o PDF com PyMuPDF
    doc = fitz.open(input_pdf_path)

    # Itera sobre cada página do PDF
    for page in doc:
        # Extrai o texto da página
        text = page.get_text()
        
        # Busca todas as ocorrências que batem com o padrão de CPF
        for match in cpf_pattern.finditer(text):
            cpf_text = match.group()
            
            # Localiza a posição do texto (bounding box) para cada ocorrência
            areas = page.search_for(cpf_text)
            # Cria anotações de redação (censura) para cada área encontrada
            for area in areas:
                # Adiciona uma anotação de redação na região do CPF
                redact_annot = page.add_redact_annot(area)
                # Opcionalmente, podemos customizar a cor do retângulo da redação
                # Por exemplo, colocar uma cor preta:
                redact_annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
                redact_annot.update()
        
        # Aplica as redações na página
        page.apply_redactions()

    # Salva o PDF redigido em um novo arquivo
    doc.save(output_pdf_path)
    doc.close()


def main():
    # Diretórios de entrada e saída
    input_dir = "data/input"
    output_dir = "data/output"

    # Cria o diretório de saída se não existir
    os.makedirs(output_dir, exist_ok=True)

    # Lista todos os PDFs no diretório de entrada
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            input_pdf_path = os.path.join(input_dir, filename)
            output_pdf_path = os.path.join(output_dir, filename)

            print(f"Censurando CPFs no arquivo: {filename}")
            censor_cpfs_in_pdf(input_pdf_path, output_pdf_path)
            print(f"Arquivo censurado salvo em: {output_pdf_path}\n")


if __name__ == "__main__":
    main()
