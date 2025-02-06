# censor.py
import re
import fitz  # PyMuPDF
from pathlib import Path
import subprocess
import tempfile
import os

def apply_ocr_if_needed(input_pdf_path: Path) -> (Path, bool):
    """
    Verifica se o PDF possui camada de texto.
    Se não possuir, aplica OCR usando o OCRmyPDF e retorna o caminho do PDF com texto.
    Retorna uma tupla: (caminho_do_pdf, foi_ocr_aplicado)
    """
    try:
        doc = fitz.open(str(input_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir {input_pdf_path}: {e}")
    
    # Verifica se ao menos uma página possui algum texto extraído
    has_text = any(page.get_text().strip() for page in doc)
    doc.close()
    
    if has_text:
        return input_pdf_path, False
    else:
        # Cria um arquivo temporário para armazenar o PDF com OCR aplicado
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(tmp_fd)  # Fechamos o descritor; usaremos apenas o caminho
        ocr_pdf_path = Path(tmp_path)
        try:
            subprocess.run(
                ["ocrmypdf", str(input_pdf_path), str(ocr_pdf_path)],
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Erro ao aplicar OCR no arquivo {input_pdf_path}: {e}")
        return ocr_pdf_path, True

def censor_partial_cpf_in_pdf(input_pdf_path: Path, output_pdf_path: Path):
    """
    Abre o PDF de entrada, localiza números de CPF (formatos 'xxx.xxx.xxx-xx' ou 11 dígitos)
    e redige (censura) os 3 primeiros dígitos e os 2 últimos, salvando o PDF processado.
    Se o PDF não possuir camada de texto, aplica OCR para extrair o texto.
    """
    # Verifica se o PDF possui camada de texto e aplica OCR se necessário
    processed_input_pdf, ocr_applied = apply_ocr_if_needed(input_pdf_path)

    # Expressão regular para detectar CPF com ou sem formatação
    cpf_regex = re.compile(r'\b(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})\b')

    try:
        doc = fitz.open(str(processed_input_pdf))
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir {processed_input_pdf}: {e}")

    for page in doc:
        text = page.get_text()
        for match in cpf_regex.finditer(text):
            matched_text = match.group()
            rects = page.search_for(matched_text)
            for rect in rects:
                total_chars = len(matched_text)
                if total_chars < 5:
                    continue  # Garante que haja caracteres suficientes para aplicar a censura

                # Considerando espaçamento uniforme entre os caracteres:
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

                # Adiciona as anotações de redacção (com preenchimento preto)
                page.add_redact_annot(left_rect, fill=(0, 0, 0))
                page.add_redact_annot(right_rect, fill=(0, 0, 0))

        page.apply_redactions()

    try:
        doc.save(str(output_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar {output_pdf_path}: {e}")
    finally:
        doc.close()

    # Se o OCR foi aplicado, remove o arquivo temporário
    if ocr_applied:
        try:
            processed_input_pdf.unlink()
        except Exception as e:
            print(f"Não foi possível remover o arquivo temporário {processed_input_pdf}: {e}")

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
