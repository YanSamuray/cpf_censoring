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
    Processa CPF, RG, Título de Eleitor e CNH conforme as seguintes regras:
      - CPF: redacção parcial – apenas os 3 primeiros e os 2 últimos dígitos (usando grupos).  
        Se o CPF estiver quebrado em duas linhas (retângulo com altura > 15), procura os retângulos de cada grupo.
      - Título de Eleitor: redacção total – oculta todos os dígitos (os 12 dígitos, agrupados em 3 grupos de 4).
      - CNH: redacção total – oculta os 11 dígitos.
      - RG: redacção total – oculta o número inteiro.
    
    Ignora o match se, na janela de 30 caracteres anteriores, houver alguma das palavras indesejadas:
       "r$", "cnpj", "id", "c/c" ou "matrícula:".
    Também ignora matches que aparentem ser valores financeiros (contendo ponto ou vírgula e com menos de 10 dígitos).
    Para RG, se logo após o match (ignorando espaços) houver uma barra seguida de 4 dígitos (com opcional hífen e 2 dígitos), descarta o match.
    """
    # Regex para CPF: aceita opcionalmente "CPF:" e captura 4 grupos de dígitos
    cpf_regex = re.compile(
        r'\b(?:cpf[:\s]*)?(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b',
        re.DOTALL | re.IGNORECASE
    )
    # Regex para RG (padrão simplificado)
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    # Regex para Título de Eleitor: aceita opcionalmente "Título de Eleitor:" e captura 3 grupos de 4 dígitos
    titulo_regex = re.compile(
        r'\b(?:título\s*de\s*eleitor[:\s]*)?(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b',
        re.IGNORECASE
    )
    # Regex para CNH: aceita variações do rótulo e captura somente os 11 dígitos
    cnh_regex = re.compile(
        r'\b(?:cnh\b|carteira\s+nacional\s+de\s+habilita(?:[çc]ã?o))\s*[:\-]?\s*(\d{11})\b',
        re.IGNORECASE
    )
    
    # Configura uma lista com tuplas: (Label, regex, usar grupos?).
    # Para CPF, Título e CNH, usaremos os grupos (True) para trabalhar somente com os dígitos.
    patterns = [
        ("CPF", cpf_regex, True),
        ("Titulo", titulo_regex, True),
        ("CNH", cnh_regex, True),
        ("RG", rg_regex, False)
    ]
    
    # Lista de palavras que, se encontradas na janela de contexto (30 caracteres antes), fazem o match ser ignorado.
    ignore_contexts = ["r$", "cnpj", "id", "c/c", "matrícula:"]
    # Regex para identificar valor financeiro simples (ex.: "1234.56" ou "1234,56")
    financeiro_regex = re.compile(r'^\d+[.,]\d{2}$')
    
    doc = fitz.open(str(input_pdf_path))
    
    for page in doc:
        raw_text = page.get_text()
        # Une as linhas para tentar “juntar” trechos quebrados
        text = " ".join(raw_text.splitlines())
        
        for label, regex, use_groups in patterns:
            for match in regex.finditer(text):
                start_index = match.start()
                window = text[max(0, start_index - 30):start_index].lower()
                if any(substr in window for substr in ignore_contexts):
                    continue
                # Se o match contém ponto ou vírgula e, ao remover não-numéricos, tiver menos de 10 dígitos, ignora (valor financeiro)
                m_text = match.group()
                if (',' in m_text or '.' in m_text):
                    temp = re.sub(r'[^\d]', '', m_text)
                    if len(temp) < 10:
                        continue
                # Para RG: se logo após o match (ignorando espaços) houver uma barra seguida de 4 dígitos (opcionalmente com hífen e 2 dígitos), ignora.
                if label == "RG":
                    after_text = text[match.end(): match.end()+20]
                    after_text_nospace = re.sub(r'\s+', '', after_text)
                    if re.match(r'^/\d{4}-?\d{2}', after_text_nospace):
                        continue
                        
                # Obter os dígitos do match usando os grupos (se configurado) ou o match completo.
                if use_groups:
                    groups = match.groups()
                    digits_only = "".join(groups)
                else:
                    digits_only = "".join(ch for ch in match.group() if ch.isdigit())
                
                # Validação dos dígitos conforme o documento:
                if label == "CPF":
                    if len(digits_only) != 11:
                        continue
                elif label == "Titulo":
                    if len(digits_only) != 12:
                        continue
                elif label == "CNH":
                    if len(digits_only) != 11:
                        continue
                elif label == "RG":
                    if not (7 <= len(digits_only) <= 9):
                        continue
                        
                # Agora, a redacção:
                if label == "CPF":
                    # Tentamos obter o retângulo para o match completo
                    rects = page.search_for(match.group())
                    use_groups_flag = False
                    if not rects:
                        use_groups_flag = True
                    elif rects[0].height > 15:
                        use_groups_flag = True
                    if use_groups_flag:
                        # Para CPF quebrado, redaciona apenas o grupo 1 (3 dígitos) e o grupo 4 (2 dígitos)
                        for i, part in enumerate(groups, start=1):
                            if i in (1, 4):
                                found = page.search_for(part)
                                if found:
                                    for rect in found:
                                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        continue
                    else:
                        # Para CPF em linha única, também usamos os grupos
                        for i, part in enumerate(groups, start=1):
                            if i in (1, 4):
                                found = page.search_for(part)
                                if found:
                                    for rect in found:
                                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        continue
                elif label in ("Titulo", "CNH"):
                    # Para Título de Eleitor e CNH: redaciona todos os dígitos capturados (usando os grupos)
                    for part in match.groups():
                        found = page.search_for(part)
                        if found:
                            for rect in found:
                                page.add_redact_annot(rect, fill=(0, 0, 0))
                else:  # Para RG
                    rects = page.search_for(match.group())
                    if not rects:
                        continue
                    for rect in rects:
                        page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()
    
    try:
        doc.save(str(output_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar {output_pdf_path}: {e}")
    finally:
        doc.close()

def process_all_pdfs(input_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    for pdf_file in input_dir.glob("*.pdf"):
        print(f"Processando {pdf_file.name}...")
        output_file = output_dir / pdf_file.name
        try:
            censor_partial_identifiers_in_pdf(pdf_file, output_file)
            print(f"Arquivo salvo em: {output_file}\n")
        except Exception as e:
            print(f"Erro ao processar {pdf_file.name}: {e}\n")
