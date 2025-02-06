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
    Processa CPF, RG, Título de Eleitor e CNH segundo as seguintes regras:
      - CPF: redacção parcial (oculta os 3 primeiros e 2 últimos dígitos). Se o CPF estiver quebrado em duas linhas,
             utiliza os retângulos de cada grupo (apenas o 1º e o 4º grupo são redacionados).
      - RG, Título de Eleitor e CNH: redacção total (oculta o número inteiro).
      
    O script ignora matches se:
      - A janela de 30 caracteres anteriores contiver "r$", "cnpj", "id", "c/c" ou "matrícula:".
      - O match parecer um valor financeiro (por conter um separador decimal seguido de exatamente duas casas e possuir menos de 10 dígitos).
      - Para CPF e RG, se logo após o match (ignorando espaços) houver uma barra seguida de 4 dígitos (opcionalmente um hífen e 2 dígitos), sugerindo parte de um CNPJ.
      
    Também há um tratamento para remover prefixos como "CPF:" do match, de forma que o redimensionamento (redacção parcial) seja aplicado apenas aos dígitos.
    """
    # Expressões regulares:
    cpf_regex = re.compile(
        r'\b(?:cpf[:\s]*)?(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b',
        re.DOTALL | re.IGNORECASE
    )
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    titulo_regex = re.compile(r'\b(?:título\s+de\s+eleitor[:\s]*)?(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b', re.IGNORECASE)
    cnh_regex = re.compile(
        r'\b(?:cnh|carteira\s+(?:nacional\s+)?de\s+habilita(?:ção|cao))\s*[:\-]?\s*(\d{11})\b',
        re.IGNORECASE
    )
    
    # Lista de padrões com seus rótulos
    patterns = [
        ("CPF", cpf_regex),
        ("RG", rg_regex),
        ("Titulo", titulo_regex),
        ("CNH", cnh_regex)
    ]
    
    # Lista de palavras a serem ignoradas na janela de contexto (todas em minúsculas)
    ignore_contexts = ["r$", "cnpj", "id", "c/c", "matrícula:"]
    
    # Regex para identificar valor financeiro simples (ex: "1234.56" ou "1234,56")
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
                # Obter o match e remover prefixos desnecessários (como "CPF:" ou "Título de Eleitor:")
                matched_text = match.group()
                # Para CPF, remova qualquer prefixo "cpf:" (já que o regex permite opcionalmente)
                if label == "CPF":
                    matched_text = re.sub(r'^(cpf[:\s]*)', '', matched_text, flags=re.IGNORECASE)
                # Para Título, se houver prefixo "título de eleitor:" remova-o
                if label == "Titulo":
                    matched_text = re.sub(r'^(título\s+de\s+eleitor[:\s]*)', '', matched_text, flags=re.IGNORECASE)
                start_index = match.start()
                window = text[max(0, start_index-30):start_index].lower()
                
                # Ignorar se a janela contiver alguma das palavras indesejadas
                if any(substr in window for substr in ignore_contexts):
                    continue

                # Se o match parece ser um valor financeiro (ex.: contém ponto ou vírgula e, quando removidos, possui menos de 10 dígitos), ignora
                if (',' in matched_text or '.' in matched_text):
                    temp = re.sub(r'[^\d]', '', matched_text)
                    if len(temp) < 10:
                        # Opcionalmente, pode testar com financeiro_regex se desejar algo mais restrito
                        continue

                # Para CPF e RG, verificação extra: se logo após o match (ignorando espaços) houver
                # uma barra seguida de 4 dígitos (opcionalmente hífen e 2 dígitos), descarta o match.
                if label in ("CPF", "RG"):
                    after_text = text[match.end(): match.end()+20]
                    after_text_nospace = re.sub(r'\s+', '', after_text)
                    if re.match(r'^/\d{4}-?\d{2}', after_text_nospace):
                        # Se o contexto tiver explicitamente "cpf" (no caso de CPF), pode ser um erro de fundo;
                        # caso contrário, descarta.
                        if label == "CPF" and "cpf" in window:
                            pass
                        else:
                            continue

                # Extrai somente os dígitos do matched_text
                digits_only = "".join(ch for ch in matched_text if ch.isdigit())
                
                # Valida o número de dígitos conforme o documento:
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
                
                # Para CPF: se não encontrar retângulos ou se o retângulo parecer alto (indicando quebra em duas linhas),
                # tenta usar os retângulos de cada grupo individualmente e redaciona somente os grupos 1 e 4.
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
                        # Redaciona apenas o primeiro grupo (3 dígitos) e o quarto grupo (2 dígitos)
                        for i, part in enumerate(groups, start=1):
                            if i in (1, 4):
                                found = page.search_for(part)
                                if found:
                                    for rect in found:
                                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        continue  # Pula para o próximo match

                if not rects:
                    continue
                
                # Para cada retângulo encontrado, aplica a redacção
                for rect in rects:
                    total_chars = len(digits_only)
                    if total_chars < 5:
                        continue
                    if label == "CPF":
                        # Redacção parcial: oculta os 3 primeiros e os 2 últimos dígitos
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
                        # Para RG, Título e CNH: redaciona o número inteiro
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
