# CPF Censoring Project

Este projeto tem como objetivo processar arquivos PDF e censurar os CPFs encontrados neles.  
A censura é aplicada apenas nos **3 primeiros dígitos** e nos **2 últimos dígitos** de cada CPF, preservando parcialmente a informação.

## 📂 Estrutura do Projeto

```
cpf_censoring/
├── data/
│   ├── input/           # Arquivos PDF de entrada
│   └── output/          # Arquivos PDF processados (saída)
├── src/
│   ├── __init__.py      # Torna o diretório um pacote Python
│   ├── censor.py        # Funções responsáveis pela censura dos CPFs
│   └── utils.py         # Funções utilitárias (ex.: obtenção dos diretórios de dados)
├── main.py              # Script principal para execução do projeto
├── requirements.txt     # Lista de dependências
└── README.md            # Documentação e instruções do projeto
```

## 📌 Funcionalidades

- 🔍 Detecta CPFs nos formatos:
  - `123.456.789-00`
  - `12345678900`
- 🖊️ Censura apenas os **três primeiros dígitos** e os **dois últimos**, preservando o restante do CPF.
- 📝 Processa múltiplos arquivos PDF automaticamente.
- 💾 Salva os arquivos censurados na pasta `data/output`.

---

## 🚀 Como Executar o Projeto

### 1⃣ Criar o Ambiente Virtual (opcional, mas recomendado)

Se desejar rodar o projeto dentro de um ambiente isolado:

#### 🔹 Windows (cmd ou PowerShell)

```cmd
cd caminho\para\cpf_censoring
python -m venv venv
venv\Scripts\activate
```

#### 🔹 Linux/macOS (Terminal)

```bash
cd /caminho/para/cpf_censoring
python3 -m venv venv
source venv/bin/activate
```

---

### 2⃣ Instalar as Dependências

Após ativar o ambiente virtual, instale as bibliotecas necessárias:

```bash
pip install -r requirements.txt
```

---

### 3⃣ Preparar os Arquivos PDF

- Coloque os arquivos que deseja processar na pasta **`data/input/`**.
- O script salvará os PDFs processados em **`data/output/`**.

Se a pasta `data/output` não existir, o script criará automaticamente.

---

### 4⃣ Executar o Script Principal

Com o ambiente virtual ativado e os PDFs na pasta `data/input`, execute:

```bash
python main.py
```

O script processará **todos** os arquivos `.pdf` encontrados em `data/input`, aplicará a censura e salvará os resultados em `data/output`.

---

## 🗂 Como Funciona o Código

O código está dividido em módulos dentro da pasta `src/`, facilitando manutenção e expansão:

- **`censor.py`**: Implementa a lógica de censura dos CPFs nos PDFs.
- **`utils.py`**: Funções auxiliares para manipulação de diretórios.
- **`main.py`**: Script principal que gerencia a execução.

---

## 📝 Exemplo de CPF Processado

📌 **Antes da Censura:**
```
Nome: João Silva
CPF: 123.456.789-00
```

🔒 **Após a Censura:**
```
Nome: João Silva
CPF: ███.456.789-██
```

---

## 💙 Possíveis Melhorias Futuras

- 🎨 Melhorar o suporte para PDFs com diferentes tipos de formatação de texto.
- 📊 Criar um relatório de processamento para acompanhar os arquivos modificados.
- 🗃️ Adicionar suporte para subdiretórios em `data/input`.

---

## 🖥️ Tecnologias Utilizadas

- **Python 3.x**
- **PyMuPDF (fitz)** - Para manipulação de PDFs

---

## ❓ Dúvidas?

Caso tenha dúvidas ou sugestões, sinta-se à vontade para contribuir ou abrir uma issue no repositório. 😊

---

📈 **Autor:** *Yan Samuray*  
📅 **Última atualização:** *05/02/2025*  
💌 **Contato:** *[LinkedIn](https://www.linkedin.com/in/yansamuray/) ou e-mail: [yansamuray@gmail.com](mailto:yansamuray@gmail.com)*

