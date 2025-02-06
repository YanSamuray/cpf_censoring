import re
import fitz  # PyMuPDF
from pathlib import Path
import re

def union_rectangles(rects):
    """Recebe uma lista de fitz.Rect e retorna o retângulo que os envolve todos."""
    if not rects:
        return None
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return fitz.Rect(x0, y0, x1, y1)

def censor_partial_identifiers_in_pdf(input_pdf_path: Path, output_pdf_path: Path):
    """
    Abre o PDF de entrada, localiza identificadores (CPF, RG e Título de Eleitor) e redige parte dos dígitos.
    As regras são:
      - CPF: redatação parcial (oculta os 3 primeiros e 2 últimos dígitos);
      - RG e Título de Eleitor: redatação total (oculta o número inteiro).
      
    Uma janela de 30 caracteres (antes do match) é analisada para:
      - Ignorar trechos se houver indicação de valores financeiros (ex.: "R$") ou a palavra "cnpj".
      - Para Título de Eleitor, exige que o contexto contenha "títul" ou "eleitor".
      
    Além disso, se o match for feito para RG (normalmente 7 a 9 dígitos) e logo após houver um padrão do tipo 
    "/XXXX-XX" (característico da parte final de um CNPJ), esse match será ignorado.
    
    Para CPF, se o número estiver quebrado em duas linhas, o script tenta localizar cada grupo separadamente e unir os retângulos.
    """
    # Padrão para CPF: 3-3-3-2 dígitos com possíveis espaços, pontos ou traços.
    cpf_regex = re.compile(r'\b(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b', re.DOTALL)
    # Padrão para RG (exemplo simplificado; pode variar conforme o documento)
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    # Padrão para Título de Eleitor: 12 dígitos (com ou sem separadores)
    titulo_regex = re.compile(r'\b(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b')
    
    # Lista de padrões com rótulo – a ordem aqui não interfere no processamento, pois cada match é validado
    patterns = [
        ("CPF", cpf_regex),
        ("RG", rg_regex),
        ("Titulo", titulo_regex)
    ]
    
    try:
        doc = fitz.open(str(input_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir {input_pdf_path}: {e}")
    
    for page in doc:
        raw_text = page.get_text()
        # Junta as linhas para tentar unir trechos quebrados
        text = " ".join(raw_text.splitlines())
        
        for label, regex in patterns:
            for match in regex.finditer(text):
                matched_text = match.group()
                start_index = match.start()
                # Janela de 30 caracteres antes do match (em minúsculas)
                window = text[max(0, start_index-30):start_index].lower()
                
                # Se a janela contiver "r$" ou "cnpj", ignora este match
                if "r$" in window or "cnpj" in window:
                    continue

                # Para CPF não precisamos de alteração adicional, pois nosso teste de comprimento
                # (abaixo) já exige 11 dígitos.
                # Para RG: se o match tiver 7–9 dígitos e logo após (ignorando espaços) houver um padrão de CNPJ,
                # vamos descartar esse match.
                # (Essa verificação não é necessária para Título, pois ele exige 12 dígitos.)
                
                # Obter somente os dígitos do trecho
                digits_only = "".join(ch for ch in matched_text if ch.isdigit())
                
                if label == "CPF":
                    if len(digits_only) != 11:
                        continue
                elif label == "Titulo":
                    if len(digits_only) != 12:
                        continue
                    # Exige que o contexto mencione "títul" ou "eleitor"
                    if not ("títul" in window or "eleitor" in window):
                        continue
                elif label == "RG":
                    # Se não estiver no intervalo típico ou se não houver a palavra "rg" no contexto, descarta.
                    if not (7 <= len(digits_only) <= 9 or "rg" in window):
                        continue
                    # Verificação extra: se logo após o match (ignorando espaços) houver uma barra seguida de 4 dígitos,
                    # opcionalmente um hífen e 2 dígitos, descarta esse match (pois provavelmente é parte de um CNPJ).
                    after_text = text[match.end(): match.end()+20]
                    after_text_nospace = re.sub(r'\s+', '', after_text)
                    if re.match(r'^/\d{4}-?\d{2}', after_text_nospace):
                        continue

                # Tenta localizar as coordenadas do trecho na página
                rects = page.search_for(matched_text)
                # Se não encontrar – por exemplo, no caso de CPF quebrado – tenta buscar cada grupo individualmente (somente para CPF)
                if not rects and label == "CPF":
                    groups = match.groups()  # Espera 4 grupos para CPF
                    group_rects = []
                    for part in groups:
                        found = page.search_for(part)
                        if found:
                            group_rects.append(found[0])
                    if group_rects:
                        rect = union_rectangles(group_rects)
                        rects = [rect]
                if not rects:
                    continue
                
                # Para cada retângulo encontrado, calcula a área a ser redigida com base no número de dígitos
                for rect in rects:
                    total_chars = len(digits_only)
                    if total_chars < 5:
                        continue
                    # Define quantos dígitos serão ocultados para cada tipo
                    if label == "CPF":
                        left_chars, right_chars = 3, 2
                    elif label == "RG":
                        left_chars, right_chars = total_chars, 0  # redaciona o número inteiro (RG)
                    elif label == "Titulo":
                        left_chars, right_chars = total_chars, 0  # redaciona o número inteiro (Título)
                    else:
                        left_chars, right_chars = 0, 0
                        
                    if label == "CPF":
                        char_width = rect.width / total_chars
                        left_rect = fitz.Rect(
                            rect.x0,
                            rect.y0,
                            rect.x0 + left_chars * char_width,
                            rect.y1
                        )
                        right_rect = fitz.Rect(
                            rect.x0 + (total_chars - right_chars) * char_width,
                            rect.y0,
                            rect.x1,
                            rect.y1
                        )
                        page.add_redact_annot(left_rect, fill=(0, 0, 0))
                        page.add_redact_annot(right_rect, fill=(0, 0, 0))
                    else:
                        # Para RG e Título, redaciona (oculta) todo o número
                        page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()
    
    try:
        doc.save(str(output_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar {output_pdf_path}: {e}")
    finally:
        doc.close()

def process_all_pdfs(input_dir: Path, output_dir: Path):
    """
    Processa todos os PDFs presentes em 'input_dir' e salva os arquivos modificados em 'output_dir'.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for pdf_file in input_dir.glob("*.pdf"):
        print(f"Processando {pdf_file.name}...")
        output_file = output_dir / pdf_file.name
        try:
            censor_partial_identifiers_in_pdf(pdf_file, output_file)
            print(f"Arquivo salvo em: {output_file}\n")
        except Exception as e:
            print(f"Erro ao processar {pdf_file.name}: {e}\n")
