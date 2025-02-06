
import re
import fitz  # PyMuPDF
from pathlib import Path

def censor_partial_cpf_in_pdf(input_pdf_path: Path, output_pdf_path: Path):
    """
    Abre o PDF de entrada, localiza números de CPF (formatos 'xxx.xxx.xxx-xx' ou 11 dígitos)
    e redata apenas os 3 primeiros dígitos e os 2 últimos, salvando o PDF processado.
    """
    # Expressão regular para detectar CPF com ou sem formatação
    cpf_regex = re.compile(r'\b(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})\b')

    try:
        doc = fitz.open(str(input_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir {input_pdf_path}: {e}")

    for page in doc:
        text = page.get_text()
        for match in cpf_regex.finditer(text):
            matched_text = match.group()
            rects = page.search_for(matched_text)
            for rect in rects:
                total_chars = len(matched_text)
                if total_chars < 5:
                    continue  # Garante que haja caracteres suficientes para aplicar a censura

                # Supondo espaçamento uniforme entre os caracteres:
                char_width = rect.width / total_chars

                # Define a área para censurar os 3 primeiros dígitos
                left_rect = fitz.Rect(
                    rect.x0,
                    rect.y0,
                    rect.x0 + 3 * char_width,
                    rect.y1
                )

                # Define a área para censurar os 2 últimos dígitos
                right_rect = fitz.Rect(
                    rect.x0 + (total_chars - 2) * char_width,
                    rect.y0,
                    rect.x1,
                    rect.y1
                )

                # Adiciona as anotações de redacção (preenchidas com preto)
                page.add_redact_annot(left_rect, fill=(0, 0, 0))
                page.add_redact_annot(right_rect, fill=(0, 0, 0))

        page.apply_redactions()

    try:
        doc.save(str(output_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar {output_pdf_path}: {e}")
    finally:
        doc.close()

def process_all_pdfs(input_dir: Path, output_dir: Path):
    """
    Processa todos os arquivos PDF presentes em 'input_dir', aplicando a censura dos CPFs,
    e salva os arquivos modificados em 'output_dir' com os mesmos nomes.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for pdf_file in input_dir.glob("*.pdf"):
        print(f"Processando {pdf_file.name}...")
        output_file = output_dir / pdf_file.name
        try:
            censor_partial_cpf_in_pdf(pdf_file, output_file)
            print(f"Arquivo salvo em: {output_file}\n")
        except Exception as e:
            print(f"Erro ao processar {pdf_file.name}: {e}\n")
