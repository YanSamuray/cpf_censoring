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
    Processa CPF, RG, Título de Eleitor e CNH com as seguintes regras:
      - CPF: redacção parcial (oculta os 3 primeiros e 2 últimos dígitos)
             – preserva o tratamento de CPF quebrado em duas linhas (usando retângulos individuais para grupos).
      - RG, Título e CNH: redacção total (oculta todo o número).
      
    O script ignora matches se:
      - A janela de 30 caracteres anteriores contiver "r$", "cnpj", "id" ou "c/c".
      - O match parecer um número financeiro (por exemplo, contém um separador decimal seguido de exatamente duas casas e o total de dígitos é menor que 10).
      - Para CPF ou RG, se logo após o match houver uma barra seguida de 4 dígitos (opcionalmente hífen e 2 dígitos), sugerindo parte de um CNPJ.
    """
    # Expressões regulares para os documentos:
    cpf_regex = re.compile(r'\b(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b', re.DOTALL)
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    titulo_regex = re.compile(r'\b(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b')
    cnh_regex = re.compile(
        r'\b(?:CNH|Carteira\s+(?:Nacional\s+)?de\s+Habilita(?:ção|cao))\s*[:\-]?\s*(\d{11})\b',
        re.IGNORECASE
    )
    
    # Lista de padrões com seus rótulos
    patterns = [
        ("CPF", cpf_regex),
        ("RG", rg_regex),
        ("Titulo", titulo_regex),
        ("CNH", cnh_regex)
    ]
    
    # Regex para identificar um valor financeiro: número que termina com um separador decimal e duas casas
    financeiro_regex = re.compile(r'^\d+[.,]\d{2}$')
    
    try:
        doc = fitz.open(str(input_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao abrir {input_pdf_path}: {e}")
    
    for page in doc:
        raw_text = page.get_text()
        # Junta as linhas para unir trechos quebrados
        text = " ".join(raw_text.splitlines())
        
        for label, regex in patterns:
            for match in regex.finditer(text):
                # Para CNH, usamos apenas o grupo que contém os 11 dígitos
                if label == "CNH":
                    matched_text = match.group(1)
                else:
                    matched_text = match.group()
                start_index = match.start()
                window = text[max(0, start_index-30):start_index].lower()
                
                # Ignora se a janela tiver indicadores indesejados
                if any(substr in window for substr in ["r$", "cnpj", "id", "c/c"]):
                    continue

                # Verifica se o match parece um valor financeiro (ex: "1234.56" ou "1234,56")
                if financeiro_regex.fullmatch(matched_text.strip()):
                    continue

                # Para CPF e RG, se logo após o match (ignorando espaços) houver padrão de CNPJ, ignora
                if label in ("CPF", "RG"):
                    after_text = text[match.end(): match.end()+20]
                    after_text_nospace = re.sub(r'\s+', '', after_text)
                    if re.match(r'^/\d{4}-?\d{2}', after_text_nospace):
                        continue

                # Extrai apenas os dígitos
                digits_only = "".join(ch for ch in matched_text if ch.isdigit())
                
                # Valida o tamanho para cada documento
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
                elif label == "CNH":
                    if len(digits_only) != 11:
                        continue

                # Localiza os retângulos na página
                rects = page.search_for(matched_text)
                # Se for CPF e não houver retângulos ou o retângulo parecer muito alto (indicando quebra em duas linhas),
                # usa os retângulos de cada grupo para redacionar somente os dígitos desejados.
                if label == "CPF":
                    use_groups = False
                    if not rects:
                        use_groups = True
                    else:
                        union_rect = rects[0]
                        if union_rect.height > 15:
                            use_groups = True
                    if use_groups:
                        groups = match.groups()  # Espera 4 grupos
                        for i, part in enumerate(groups, start=1):
                            if i in (1, 4):  # Apenas o primeiro (3 dígitos) e o último (2 dígitos)
                                found = page.search_for(part)
                                if found:
                                    for rect in found:
                                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        continue  # Pula para o próximo match

                if not rects:
                    continue
                
                for rect in rects:
                    total_chars = len(digits_only)
                    if total_chars < 5:
                        continue
                    if label == "CPF":
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
                        # Para RG, Título e CNH: redaciona todo o número
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
    Processa todos os PDFs em 'input_dir' e salva os modificados em 'output_dir'.
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
