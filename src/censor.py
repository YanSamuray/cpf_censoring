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
    Abre o PDF de entrada, localiza identificadores (CPF, RG, Título de Eleitor e CNH) e redige
    parte dos dígitos ou o número completo, conforme a regra:
      - CPF: redacção parcial (oculta os 3 primeiros e 2 últimos dígitos);
      - RG, Título de Eleitor e CNH: redacção total (oculta todo o número).
    
    Aplica uma janela de contexto para:
      - Ignorar trechos se na janela houver indicação de valores financeiros (ex.: "R$")
        ou "cnpj".
      - Para Título de Eleitor, exige que na janela apareçam termos como "títul" ou "eleitor".
      - Para RG, valida que haja entre 7 e 9 dígitos ou que "rg" apareça no contexto.
    
    Se o CPF estiver quebrado em duas linhas, tenta unir as áreas dos grupos.
    """
    # Padrões para os identificadores
    # CPF: espera 4 grupos (3-3-3-2 dígitos) com possíveis espaços, quebras, pontos ou traços
    cpf_regex = re.compile(r'\b(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b', re.DOTALL)
    # RG: padrão simplificado; pode ser ajustado conforme os documentos
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    # Título de Eleitor: espera 3 grupos de 4 dígitos (total 12 dígitos), com ou sem separadores
    titulo_regex = re.compile(r'\b(\d{4})[\s\-]*(\d{4})[\s\-]*(\d{4})\b')
    # CNH: procura a presença dos termos "CNH" ou "Carteira Nacional de Habilita(ção|cao)" seguidos de 11 dígitos
    cnh_regex = re.compile(
        r'\b(?:CNH|Carteira\s+(?:Nacional\s+)?de\s+Habilita(?:ção|cao))\s*[:\-]?\s*(\d{11})\b',
        re.IGNORECASE
    )
    
    # Lista de padrões com seu rótulo
    patterns = [
        ("CPF", cpf_regex),
        ("RG", rg_regex),
        ("Titulo", titulo_regex),
        ("CNH", cnh_regex)
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
                # Janela de 30 caracteres antes da ocorrência (convertida para minúsculas)
                window = text[max(0, start_index-30):start_index].lower()
                
                # Se a janela contiver indicadores de valores financeiros ou "cnpj", ignora
                if "r$" in window or "cnpj" in window:
                    continue

                # Extrai somente os dígitos do trecho
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
                elif label == "CNH":
                    if len(digits_only) != 11:
                        continue

                # Tenta localizar as coordenadas na página usando o trecho encontrado
                rects = page.search_for(matched_text)
                # Se não encontrar – por exemplo, no caso de CPF quebrado –, tenta buscar cada grupo individualmente (somente para CPF)
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
                        # Para RG, Título de Eleitor e CNH: oculta o número inteiro (redação total)
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
    Processa todos os arquivos PDF presentes em 'input_dir', aplicando a censura para os identificadores e
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
