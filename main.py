import os
import re
import fitz  # PyMuPDF

# Expressão regular para capturar CPFs em formatos diversos:
# - 123.456.789-00
# - 12345678900
# - Qualquer mistura de pontos e traços (opcionais)
CPF_PATTERN = re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b')


def mask_cpf_digits(cpf_text: str) -> str:
    """
    Dado o texto capturado de CPF (que pode ter pontos e traços),
    retorna uma forma padronizada na qual apenas 3 primeiros e 2 últimos
    dígitos são censurados (substituídos por X).

    Exemplos:
      - "123.456.789-00" => "XXX.456.789-XX"
      - "12345678900"    => "XXX456789XX"
    """

    # Extrai somente dígitos
    digits_only = re.sub(r'\D', '', cpf_text)  # "12345678900"

    if len(digits_only) != 11:
        # Se não tiver exatamente 11 dígitos, retornamos o próprio texto
        # ou alguma forma de fallback. Aqui opto por devolver igual.
        return cpf_text

    # Quebra:  [123] [456789] [00]
    first_3 = digits_only[:3]      # ex: 123
    middle_6 = digits_only[3:9]    # ex: 456789
    last_2 = digits_only[9:11]     # ex: 00

    # Monta a parte censurada:
    #   - Substitui primeiros 3 por "XXX"
    #   - Substitui últimos 2 por "XX"
    #   - Mantém meio intacto
    censored_digits = f"XXX{middle_6}XX"  # "XXX456789XX"

    # (1) Se quisermos manter a pontuação original (por exemplo, a mesma posição
    #     de pontos e traços do CPF encontrado), precisamos analisar caractere
    #     por caractere. Isso pode ficar mais complexo, pois teríamos que mapear
    #     a posição exata dos símbolos.
    #
    # (2) Se quisermos forçar um formato padrão (###.###.###-##):
    #     "XXX.456.789-XX"
    #     É muitas vezes mais simples e direto.
    #
    # Abaixo, opto por **reformatar** para um padrão com pontuação:
    if '.' in cpf_text or '-' in cpf_text:
        # Ex.: "XXX.456.789-XX"
        return f"{censored_digits[:3]}.{censored_digits[3:6]}.{censored_digits[6:9]}-{censored_digits[9:11]}"
    else:
        # Ex.: "XXX456789XX"
        return censored_digits


def censor_cpfs_in_pdf(input_pdf_path: str, output_pdf_path: str):
    """
    Abre um PDF, encontra CPFs e redige somente os 3 primeiros dígitos e os
    2 últimos, preservando os dígitos do meio.
    
    :param input_pdf_path: Caminho completo do arquivo PDF de entrada.
    :param output_pdf_path: Caminho completo do arquivo PDF de saída.
    """
    doc = fitz.open(input_pdf_path)

    for page in doc:
        # Extrai todo o texto da página
        text = page.get_text()

        # Localiza todos os CPFs via regex
        matches = list(CPF_PATTERN.finditer(text))

        # Para cada CPF encontrado...
        for match in matches:
            original_cpf = match.group()  # Ex.: "123.456.789-10"
            censored_cpf = mask_cpf_digits(original_cpf)

            # Buscamos a(s) área(s) de localização do CPF original
            areas = page.search_for(original_cpf)
            
            # Em cada área, criaremos um "redact annotation"
            for area in areas:
                # Adiciona a anotação de redação, mas passando 'text=censored_cpf'
                # para sobrescrever o trecho original com a forma censurada.
                annot = page.add_redact_annot(
                    area,
                    text=censored_cpf,   # texto que sobrepõe
                )
                # Ajusta cores de fundo e borda para branco, se desejar mostrar o texto censurado
                # sobre fundo branco (sem retângulo preto).
                # Caso queira um retângulo preto, use fill=(0,0,0).
                annot.set_colors(stroke=(1,1,1), fill=(1,1,1))
                annot.set_opacity(1)
                annot.update()

        # Aplica as redações
        page.apply_redactions()

    # Salva o PDF resultante
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

            print(f"[PROCESSANDO] {filename} ...")
            censor_cpfs_in_pdf(input_pdf, output_pdf)
            print(f"[OK] Arquivo censurado salvo em {output_pdf}\n")


if __name__ == "__main__":
    main()
