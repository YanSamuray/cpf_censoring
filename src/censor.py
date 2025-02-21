import re
import fitz  # PyMuPDF
from pathlib import Path

def is_valid_cpf(cpf: str) -> bool:
    """
    Valida o CPF usando o algoritmo dos dígitos verificadores.
    Retorna True se o CPF for válido, caso contrário, False.
    """
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = 11 - (soma % 11)
    if d1 >= 10:
        d1 = 0

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = 11 - (soma % 11)
    if d2 >= 10:
        d2 = 0

    return (int(cpf[9]) == d1) and (int(cpf[10]) == d2)

def censor_cpf_in_pdf(input_pdf_path: Path, output_pdf_path: Path):
    """
    Processa CPF com as seguintes regras:
      - Redação parcial: censura apenas os 3 primeiros e os 2 últimos dígitos.
      - Ignora o match se, na janela de 30 caracteres anteriores, houver
        alguma das palavras indesejadas, incluindo "certidão".
      - Ignora matches que aparentem ser valores financeiros.
      - Censura apenas se o número identificado for um CPF válido.
    """
    # Regex para CPF (aceita opcionalmente "CPF:" e diversos separadores)
    cpf_regex = re.compile(
        r'\b(?:cpf[:\s]*)?(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{3})[\s\.\-]*(\d{2})\b',
        re.DOTALL | re.IGNORECASE
    )
    # Adiciona "certidão" à lista de contextos que indicam que o número não é CPF
    ignore_contexts = ["r$", "cnpj", "id", "c/c", "matrícula:", "certidão"]
    
    doc = fitz.open(str(input_pdf_path))
    for page in doc:
        raw_text = page.get_text()
        # Junta as linhas para minimizar quebras inesperadas
        text = " ".join(raw_text.splitlines())
        
        for match in cpf_regex.finditer(text):
            start_index = match.start()
            context_window = text[max(0, start_index - 30):start_index].lower()
            if any(word in context_window for word in ignore_contexts):
                continue
            
            m_text = match.group()
            # Ignora se aparentar valor financeiro
            if (',' in m_text or '.' in m_text):
                temp = re.sub(r'[^\d]', '', m_text)
                if len(temp) < 10:
                    continue
            
            groups = match.groups()  # Grupos: (3, 3, 3 e 2 dígitos)
            digits_only = "".join(groups)
            if len(digits_only) != 11:
                continue
            
            # Só prossegue se for um CPF válido
            if not is_valid_cpf(digits_only):
                continue
            
            # Redação parcial: censura apenas o grupo 1 (3 dígitos) e o grupo 4 (2 dígitos)
            for idx, part in enumerate(groups, start=1):
                if idx in (1, 4):
                    found = page.search_for(part)
                    for rect in found:
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
            censor_cpf_in_pdf(pdf_file, output_file)
            print(f"Arquivo salvo em: {output_file}\n")
        except Exception as e:
            print(f"Erro ao processar {pdf_file.name}: {e}\n")
