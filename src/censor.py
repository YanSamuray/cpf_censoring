import re
import fitz  # PyMuPDF
from pathlib import Path
import numpy as np
import cv2
import easyocr

def convert_bbox_to_rect(bbox, img_height):
    """
    Converte uma bounding box retornada pelo EasyOCR (lista de 4 pontos [x, y] com origem no topo)
    para um objeto fitz.Rect no sistema de coordenadas do PDF (origem em baixo).
    """
    # Converte cada ponto: (x, y_image) -> (x, img_height - y_image)
    converted = [(pt[0], img_height - pt[1]) for pt in bbox]
    left = min(pt[0] for pt in converted)
    right = max(pt[0] for pt in converted)
    bottom = min(pt[1] for pt in converted)
    top = max(pt[1] for pt in converted)
    return fitz.Rect(left, bottom, right, top)

def censor_partial_cpf_in_pdf(input_pdf_path: Path, output_pdf_path: Path, force_ocr: bool = False):
    """
    Abre o PDF de entrada, localiza números de CPF (nos formatos 'xxx.xxx.xxx-xx' ou 11 dígitos)
    e redige (censura) os 3 primeiros dígitos e os 2 últimos, salvando o PDF processado.
    
    Se force_ocr for True, o método convencional de extração de texto é ignorado e o OCR (EasyOCR)
    é utilizado para todas as páginas.
    """
    # Expressão regular para detectar CPF com ou sem formatação
    cpf_regex = re.compile(r'\b(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})\b')
    
    try:
        doc = fitz.open(str(input_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir {input_pdf_path}: {e}")
    
    # Inicializa o leitor do EasyOCR (a inicialização pode demorar na primeira chamada)
    reader = easyocr.Reader(['pt'], gpu=False)
    
    for page in doc:
        # Se não for forçado o OCR, tenta extrair o texto normalmente.
        # Se force_ocr for True, força o uso do EasyOCR.
        if not force_ocr:
            text = page.get_text().strip()
        else:
            text = ""
            
        if text:
            # Método convencional: usa o texto extraído pela camada do PDF
            for match in cpf_regex.finditer(text):
                matched_text = match.group()
                # Busca as ocorrências do texto na página para obter as coordenadas
                rects = page.search_for(matched_text)
                for rect in rects:
                    total_chars = len(matched_text)
                    if total_chars < 5:
                        continue  # Garante que haja caracteres suficientes
                    # Considera espaçamento uniforme entre os caracteres
                    char_width = rect.width / total_chars
                    # Define a área para censurar os 3 primeiros dígitos
                    left_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + 3 * char_width, rect.y1)
                    # Define a área para censurar os 2 últimos dígitos
                    right_rect = fitz.Rect(rect.x0 + (total_chars - 2) * char_width, rect.y0, rect.x1, rect.y1)
                    page.add_redact_annot(left_rect, fill=(0, 0, 0))
                    page.add_redact_annot(right_rect, fill=(0, 0, 0))
            page.apply_redactions()
        else:
            # Método com OCR: renderiza a página como imagem e utiliza o EasyOCR
            pix = page.get_pixmap()
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            img_height = pix.height
            results = reader.readtext(img)
            for bbox, detected_text, conf in results:
                # Se o texto detectado corresponder exatamente ao formato de CPF, aplica a censura
                if cpf_regex.fullmatch(detected_text):
                    rect = convert_bbox_to_rect(bbox, img_height)
                    total_chars = len(detected_text)
                    if total_chars < 5:
                        continue
                    char_width = rect.width / total_chars
                    left_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + 3 * char_width, rect.y1)
                    right_rect = fitz.Rect(rect.x0 + (total_chars - 2) * char_width, rect.y0, rect.x1, rect.y1)
                    page.add_redact_annot(left_rect, fill=(0, 0, 0))
                    page.add_redact_annot(right_rect, fill=(0, 0, 0))
            page.apply_redactions()
    
    try:
        doc.save(str(output_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar {output_pdf_path}: {e}")
    finally:
        doc.close()

def process_all_pdfs(input_dir: Path, output_dir: Path, force_ocr: bool = False):
    """
    Processa todos os arquivos PDF presentes em 'input_dir', aplicando a censura dos CPFs,
    e salva os arquivos modificados em 'output_dir' com os mesmos nomes.
    
    O parâmetro force_ocr força o uso do OCR (EasyOCR) em todas as páginas, mesmo que a camada
    de texto esteja presente.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for pdf_file in input_dir.glob("*.pdf"):
        print(f"Processando {pdf_file.name}...")
        output_file = output_dir / pdf_file.name
        try:
            censor_partial_cpf_in_pdf(pdf_file, output_file, force_ocr=force_ocr)
            print(f"Arquivo salvo em: {output_file}\n")
        except Exception as e:
            print(f"Erro ao processar {pdf_file.name}: {e}\n")
