# utils.py
from pathlib import Path

def get_data_dirs(base_path: Path):
    """
    Retorna os diretórios de entrada e saída com base no diretório base do projeto.
    """
    input_dir = base_path / "data" / "input"
    output_dir = base_path / "data" / "output"
    return input_dir, output_dir

