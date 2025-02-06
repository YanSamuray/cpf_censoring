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
    Abre o PDF de entrada, localiza CPFs, RGs e Títulos de Eleitor e redige parte dos dígitos para censurá-los.
    
    Para tentar corrigir CPFs quebrados em duas linhas, utiliza uma expressão regular flexível para CPF.
    Também evita redacionar números que estejam associados a valores financeiros (precedidos por "R$").
    """
    # Expressões regulares – ajuste conforme os padrões dos seus documentos.
    # CPF: permite espaços, quebras de linha, pontos e traços opcionais, mas exige 4 grupos: 3-3-3-2 dígitos.
    cpf_regex = re.compile(r'\b(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b', re.DOTALL)
    # RG (exemplo): 1 ou 2 dígitos, opcional ponto, 3 dígitos, opcional ponto, 3 dígitos, opcional traço e dígito ou X
    rg_regex = re.compile(r'\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]?\b')
    # Título de Eleitor (exemplo): 12 dígitos ou em grupos com espaços
    titulo_regex = re.compile(r'\b(?:\d{4}\s?\d{4}\s?\d{4}|\d{12})\b')

    # Lista de padrões com um rótulo para facilitar o tratamento:
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
        # Junta as linhas – isso ajuda a unir trechos quebrados, embora nem sempre seja perfeito.
        text = " ".join(raw_text.splitlines())

        for label, regex in patterns:
            # Procura todos os trechos que casem com o padrão
            for match in regex.finditer(text):
                matched_text = match.group()
                start_index = match.start()

                # Se o trecho estiver precedido de um símbolo de moeda (ex.: "R$"), ignora-o.
                window = text[max(0, start_index-5):start_index]
                if "R$" in window:
                    continue

                # Tenta localizar as coordenadas na página usando o texto encontrado.
                rects = page.search_for(matched_text)
                # Se não encontrou (ex.: no caso de CPF quebrado em duas linhas), tenta procurar por cada grupo (somente para CPF).
                if not rects and label == "CPF":
                    groups = match.groups()  # Espera 4 grupos: (ddd, ddd, ddd, dd)
                    group_rects = []
                    for part in groups:
                        found = page.search_for(part)
                        if found:
                            # Se encontrar mais de uma ocorrência, seleciona a que estiver mais próxima das demais.
                            group_rects.append(found[0])
                    if group_rects:
                        rect = union_rectangles(group_rects)
                        rects = [rect]
                # Se ainda não encontrou, pula para o próximo
                if not rects:
                    continue

                for rect in rects:
                    # Calcula o número total de dígitos do trecho (somente dígitos)
                    digits_only = "".join(ch for ch in matched_text if ch.isdigit())
                    total_chars = len(digits_only)
                    if total_chars < 5:
                        continue  # ignora ocorrências muito curtas

                    # Define quantos dígitos serão censurados (ajuste conforme cada tipo)
                    if label == "CPF":
                        left_chars = 3
                        right_chars = 2
                    elif label == "RG":
                        left_chars = 2
                        right_chars = 1
                    elif label == "Titulo":
                        left_chars = 4
                        right_chars = 2
                    else:
                        left_chars = 0
                        right_chars = 0

                    # Pressupondo espaçamento uniforme entre os caracteres:
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
        page.apply_redactions()

    try:
        doc.save(str(output_pdf_path))
    except Exception as e:
        raise RuntimeError(f"Erro ao salvar {output_pdf_path}: {e}")
    finally:
        doc.close()

def process_all_pdfs(input_dir: Path, output_dir: Path):
    """
    Processa todos os arquivos PDF presentes em 'input_dir', aplicando a censura
    para CPFs, RGs e Títulos de Eleitor, e salva os arquivos modificados em 'output_dir'
    com os mesmos nomes.
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
