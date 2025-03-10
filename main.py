import os
import re
import fitz  # PyMuPDF

# Expressão regular para encontrar CPFs
CPF_PATTERN = re.compile(r'\b(?:nº\s*)?\d{3}[ .\/-]*\d{3}[ .\/-]*\d{3}[ .\/-]*\d{2}\b', re.IGNORECASE)


def mask_cpf_digits(cpf_text: str) -> str:
    """
    Recebe o texto que representa um CPF (podendo ter espaços, pontos, hífens ou barras)
    e retorna uma forma 'censurada' onde só se esconde os 3 primeiros e 2 últimos dígitos,
    mantendo visíveis os 6 dígitos centrais.

    Exemplos:
      - "123.456.789-00" => "***.456.789-**"
      - "12345678900"    => "***456789**"
      - "000 000 000/00" => "*** 000 000/**"
    """
    # Extrai apenas os dígitos
    digits_only = re.sub(r'\D', '', cpf_text)

    if len(digits_only) != 11:
        return cpf_text

    first_3  = digits_only[:3]
    middle_6 = digits_only[3:9]
    last_2   = digits_only[9:]
    
    # Monta a string censurada com asteriscos
    censored_digits = f"***{middle_6}**"
    
    # Preserva a formatação original (pontos, hífens, barras, etc.)
    censored_cpf_chars = []
    digit_index = 0
    for char in cpf_text:
        if char.isdigit():
            censored_cpf_chars.append(censored_digits[digit_index])
            digit_index += 1
        else:
            censored_cpf_chars.append(char)
    
    return "".join(censored_cpf_chars)

def censor_cpfs_in_pdf(input_pdf_path: str, output_pdf_path: str):
    """
    Abre um PDF, encontra CPFs (com ou sem pontuação/espacos/hifens/barras)
    e substitui apenas os 3 primeiros e 2 últimos dígitos.
    """
    doc = fitz.open(input_pdf_path)

    for page in doc:
        text = page.get_text()
        matches = list(CPF_PATTERN.finditer(text))

        for match in matches:
            original_cpf = match.group()
            censored_cpf = mask_cpf_digits(original_cpf)

            # Localiza a(s) área(s) de texto exata(s)
            areas = page.search_for(original_cpf)

            # Cria anotações de redação em cada área
            for area in areas:
                annot = page.add_redact_annot(area, text=censored_cpf)
                annot.set_colors(stroke=(1,1,1), fill=(1,1,1))  # Fundo branco
                annot.set_opacity(1)
                annot.update()

        page.apply_redactions()

    doc.save(output_pdf_path)
    doc.close()

def main():
    input_dir = "data/input"
    output_dir = "data/output"
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            input_pdf = os.path.join(input_dir, filename)
            output_pdf = os.path.join(output_dir, filename)

            print(f"[PROCESSANDO] {filename}...")
            censor_cpfs_in_pdf(input_pdf, output_pdf)
            print(f"[OK] Salvo em {output_pdf}\n")

if __name__ == "__main__":
    main()
