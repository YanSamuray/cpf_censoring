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
      - CPF: redacção parcial (oculta os 3 primeiros e 2 últimos dígitos). Se estiver quebrado em duas linhas,
             utiliza os retângulos individuais para redacionar somente o primeiro grupo (3 dígitos) e o quarto (2 dígitos).
      - RG: redacção total (oculta o número inteiro).
      - Título de Eleitor: redacção total (oculta o número inteiro).
      - CNH: redacção total (oculta apenas os 11 dígitos, sem o rótulo textual).
      
    O script ignora um match se na janela de 30 caracteres anteriores aparecer alguma das palavras indesejadas
    ("r$", "cnpj", "id", "c/c", "matrícula:") ou se o match parecer um valor financeiro simples.
    
    Além disso, para CPF e RG, se logo após o match (ignorando espaços) houver uma barra seguida de 4 dígitos
    (opcionalmente hífen e 2 dígitos), o match é descartado (para evitar parte de CNPJ).
    
    Para tratar problemas de fundo (texto no fundo da página), algumas verificações contextuais foram mantidas.
    """
    # Regex para CPF: permite prefixo opcional "CPF:" e captura somente os 4 grupos de dígitos
    cpf_regex = re.compile(
        r'\b(?:cpf[:\s]*)?(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b',
        re.DOTALL | re.IGNORECASE
    )
    # Regex para RG (padrão simplificado)
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    # Regex para Título de Eleitor: permite prefixo opcional e captura apenas os dígitos
    titulo_regex = re.compile(
        r'\b(?:título\s+de\s+eleitor[:\s]*)?(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b',
        re.IGNORECASE
    )
    # Regex para CNH: permite variações e captura somente os 11 dígitos
    cnh_regex = re.compile(
        r'\b(?:cnh\b|carteira\s+nacional\s+de\s+habilita(?:[çc]ã?o))\s*[:\-]?\s*(\d{11})\b',
        re.IGNORECASE
    )
    
    # Lista de padrões com seus rótulos
    patterns = [
        ("CPF", cpf_regex),
        ("RG", rg_regex),
        ("Titulo", titulo_regex),
        ("CNH", cnh_regex)
    ]
    
    # Palavras a serem ignoradas na janela de contexto (todas em minúsculas)
    ignore_contexts = ["r$", "cnpj", "id", "c/c", "matrícula:"]
    
    # Regex para identificar um valor financeiro simples (ex.: "1234.56" ou "1234,56")
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
                # Para CNH, usamos somente o grupo 1 (os 11 dígitos)
                if label == "CNH":
                    matched_text = match.group(1)
                # Para Título, removemos prefixos (como "Título de Eleitor:") para obter apenas os dígitos
                elif label == "Titulo":
                    temp_text = match.group()
                    matched_text = re.sub(r'^(título\s+de\s+eleitor[:\s]*)', '', temp_text, flags=re.IGNORECASE)
                else:
                    matched_text = match.group()
                    
                start_index = match.start()
                window = text[max(0, start_index-30):start_index].lower()
                
                # Ignora se a janela contiver alguma das palavras indesejadas
                if any(substr in window for substr in ignore_contexts):
                    continue

                # Se o match parecer ser um valor financeiro (contendo ponto ou vírgula e tendo menos de 10 dígitos após remoção de não-numéricos), ignora
                if (',' in matched_text or '.' in matched_text):
                    temp = re.sub(r'[^\d]', '', matched_text)
                    if len(temp) < 10:
                        continue

                # Para CPF e RG, verificação extra: se logo após o match (ignorando espaços) houver uma barra seguida de 4 dígitos
                # (opcionalmente hífen e 2 dígitos), descarta o match
                if label in ("CPF", "RG"):
                    after_text = text[match.end(): match.end()+20]
                    after_text_nospace = re.sub(r'\s+', '', after_text)
                    if re.match(r'^/\d{4}-?\d{2}', after_text_nospace):
                        # Se o contexto explicitamente conter "cpf", pode ser um erro de fundo; caso contrário, descarta.
                        if label == "CPF" and "cpf" in window:
                            pass
                        else:
                            continue

                # Extrai somente os dígitos
                digits_only = "".join(ch for ch in matched_text if ch.isdigit())
                
                # Valida o número de dígitos conforme o documento
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

                # Tenta localizar os retângulos na página para o matched_text
                rects = page.search_for(matched_text)
                
                # Tratamento especial para CPF quebrado em duas linhas
                if label == "CPF":
                    use_groups = False
                    if not rects:
                        use_groups = True
                    else:
                        union_rect = rects[0]
                        if union_rect.height > 15:
                            use_groups = True
                    if use_groups:
                        groups = match.groups()  # Os 4 grupos do CPF
                        # Redaciona apenas o primeiro grupo (3 dígitos) e o quarto (2 dígitos)
                        for i, part in enumerate(groups, start=1):
                            if i in (1, 4):
                                found = page.search_for(part)
                                if found:
                                    for rect in found:
                                        page.add_redact_annot(rect, fill=(0,0,0))
                        continue

                if not rects:
                    continue
                
                # Para cada retângulo encontrado, aplica a redacção
                for rect in rects:
                    total_chars = len(digits_only)
                    if total_chars < 5:
                        continue
                    if label == "CPF":
                        # Redacção parcial para CPF: oculta os 3 primeiros e os 2 últimos dígitos
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
                        page.add_redact_annot(left_rect, fill=(0,0,0))
                        page.add_redact_annot(right_rect, fill=(0,0,0))
                    else:
                        # Para RG, Título e CNH: redaciona (oculta) o número inteiro
                        page.add_redact_annot(rect, fill=(0,0,0))
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
