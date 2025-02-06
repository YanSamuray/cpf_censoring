import re
import fitz  # PyMuPDF
from pathlib import Path

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
    Abre o PDF de entrada, localiza identificadores (CPF, RG e Título de Eleitor) e redige (oculta)
    parte dos dígitos ou o número completo, conforme a regra:
      - CPF: oculta os 3 primeiros e 2 últimos dígitos.
      - RG e Título de Eleitor: oculta o número inteiro.
    
    Aplica uma janela de contexto para:
      - Ignorar trechos se houver indicação de valores financeiros ("R$") ou "CNPJ".
      - Para Título de Eleitor, exige que o contexto contenha "títul" ou "eleitor".
      - Para RG, valida a quantidade de dígitos ou a presença de "rg" no contexto.
    
    Se o CPF estiver quebrado em duas linhas, tenta unir as áreas dos grupos.
    """
    # Padrões para os identificadores
    cpf_regex = re.compile(r'\b(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b', re.DOTALL)
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    titulo_regex = re.compile(r'\b(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b')
    
    # Lista de padrões com seu rótulo
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
                # Janela de 30 caracteres antes da ocorrência (em minúsculas)
                window = text[max(0, start_index-30):start_index].lower()
                
                # Se a janela contiver indicadores de valores financeiros ou CNPJ, ignora
                if "r$" in window or "cnpj" in window:
                    continue

                # Extrai somente os dígitos
                digits_only = "".join(ch for ch in matched_text if ch.isdigit())
                
                # Validações específicas para cada identificador
                if label == "CPF":
                    if len(digits_only) != 11:
                        continue
                elif label == "Titulo":
                    if len(digits_only) != 12:
                        continue
                    if not ("títul" in window or "eleitor" in window):
                        continue
                elif label == "RG":
                    if not (7 <= len(digits_only) <= 9 or "rg" in window):
                        continue

                # Tenta localizar as coordenadas na página usando o trecho encontrado
                rects = page.search_for(matched_text)
                # Se não encontrar (ex.: CPF quebrado), tenta buscar cada grupo separadamente (somente para CPF)
                if not rects and label == "CPF":
                    groups = match.groups()  # Espera 4 grupos
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
                
                for rect in rects:
                    total_chars = len(digits_only)
                    if total_chars < 5:
                        continue
                    
                    if label == "CPF":
                        # Redação parcial para CPF: oculta os 3 primeiros e 2 últimos dígitos
                        left_chars, right_chars = 3, 2
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
                        # Para RG e Título de Eleitor, oculta o número inteiro (redação total)
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
    Processa todos os arquivos PDF em 'input_dir', aplicando a censura para os identificadores e 
    salvando os arquivos modificados em 'output_dir' com os mesmos nomes.
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
