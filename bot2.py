import os
import re
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import pytesseract
import requests

# 👉 Carregar variáveis de ambiente
load_dotenv()

# 👉 Configurações
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")

# 👉 (Descomente se estiver no Windows)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 👉 Mensagem de instruções
instructions = """
👋 Olá! Envie sua transação no formato:

👉 *Por texto:*
Tipo: Despesa ou Entrada
Descrição: Mercado
Categoria: Supermercado
Valor: 12.50

Ou envie uma *foto do comprovante* que eu tento ler os dados!
"""

# 👉 Lista de padrões para identificar categoria na imagem
test_data = [
    ("Compra no Carrefour Express", "Mercado"),
    ("Bistek", "Mercado"),
    ("Atacadista", "Mercado"),
    ("Koch", "Mercado"),
    ("Mercado", "Mercado"),
    ("Supermercado", "Mercado"),
    ("Giassi", "Mercado"),
    ("Angeloni", "Mercado"),
    ("Pagamento Angeloni Loja", "Mercado"),
    ("Supermercado Big Blumenau", "Mercado"),
    ("Assai Atacadista Compra", "Mercado"),
    ("Mercado São José", "Mercado"),
    ("Hiper Bom Preço", "Mercado"),
    ("Compra no Atacadão Joinville", "Mercado"),

    ("Pedido Ifood", "Lanche"),
    ("ifood", "Lanche"),
    ("Mc Donald", "Lanche"),
    ("Compra no Burger King", "Lanche"),
    ("Pagamento BK Delivery", "Lanche"),
    ("Habib's", "Lanche"),
    ("Kalzone", "Lanche"),
    ("Subway", "Lanche"),
    ("Pizza Hut", "Lanche"),
    ("Lanche da esquina", "Lanche"),

    ("Corrida Uber", "Transporte"),
    ("Pagamento 99Pop", "Transporte"),
    ("99 corrida", "Transporte"),
    ("Cabify viagem", "Transporte"),
    ("Pista", "Pedágio"),

    ("Compra na Drogasil", "Farmácia"),
    ("Panvel Farmácia", "Farmácia"),
    ("Farmácia Santa Maria", "Farmácia"),
    ("Droga Raia", "Farmácia"),
    ("Drogaria Pacheco", "Farmácia"),

    ("Assinatura Netflix", "Entretenimento"),
    ("Spotify pagamento", "Entretenimento"),
    ("Cinema Arcoplex", "Entretenimento"),
    ("Prime Video", "Entretenimento"),
    ("Disney Plus", "Entretenimento"),
    ("HBO Max", "Entretenimento"),

    ("Bar do Zé", "Restaurante"),
    ("Restaurante Sabor", "Restaurante"),
    ("Churrascaria Fogo de Chão", "Restaurante"),
    ("Padaria Pão Quente", "Restaurante"),

    ("Parque Beto Carrero", "Lazer"),
    ("Escape Room", "Lazer"),
    ("Boliche Strike", "Lazer"),
    ("Clube de Tiro", "Lazer"),
    ("Academia Smartfit", "Lazer"),
    ("futpanelas1@gmail.com", "Lazer"),

    ("Barbearia", "Estética"),

    ("Fatura", "Cartão de crédito"),
    ("Pagamento fatura", "Cartão de crédito"),
    ("Compra no cartão", "Cartão de crédito"),
    ("Pagamento parcelado", "Cartão de crédito"),
    ("Fatura do cartão", "Cartão de crédito"),
    ("Pagamento parcelado", "Cartão de crédito"),

    ("Conta de luz Celesc", "Casa"),
    ("CELESC", "Casa"),
    ("CASAN", "Casa"),
    ("Pagamento Casan", "Casa"),
    ("Compra Cassol", "Casa"),
    ("Cobrança de condomínio", "Casa"),
    ("Internet Claro", "Casa"),
    ("Compra na Leroy Merlin", "Casa"),
    ("Madeireira São José", "Casa"),
    ("HDI SEGUROS", "Casa"),
    ("VERO", "Casa"),

    ("Posto Shell", "Carro"),
    ("Abastecimento Ipiranga", "Carro"),
    ("Posto Petrobras", "Carro"),
    ("Mecânica Auto Center", "Carro"),
    ("Troca de óleo Lubicar", "Carro"),
    ("Oficina Mecânica São Pedro", "Carro"),
    ("Estacionamento Central Park", "Carro"),
    ("CATARINENSE ASSOCIACAO", "Carro"),

    ("Transferência PIX", "Transferência"),
    ("PIX", "Transferência"),
    ("TED recebida", "Transferência"),
    ("Depósito em conta", "Transferência"),
    ("Pagamento desconhecido", "Transferência"),
]

def identify_category(description_text):
    description_text = description_text.lower()
    for pattern, category in test_data:
        if pattern.lower() in description_text:
            return category
    return "Outros"

# 👉 Funções auxiliares
def find_match(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None

# 👉 Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(instructions)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(instructions)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.message.from_user.first_name

    try:
        type_match = find_match(r"Tipo:\s*(.+)", text)
        description_match = find_match(r"Descrição:\s*(.+)", text)
        category_match = find_match(r"Categoria:\s*(.+)", text)
        cost_match = find_match(r"Valor:\s*([\d.,]+)", text)

        if not all([type_match, description_match, category_match, cost_match]):
            await update.message.reply_text(f"⚠️ Formato incorreto. Envie assim:\n{instructions}")
            return

        data = {
            "type": type_match,
            "description": description_match,
            "category": category_match,
            "cost": float(cost_match.replace(",", ".")),
            "user": user,
        }

        response = requests.post(GOOGLE_SHEET_URL, json=data)
        result = response.json()

        if result.get("result") == "Success":
            await update.message.reply_text(f"✅ Adicionado: {data['description']} ({data['category']}) - R${data['cost']}")
        else:
            await update.message.reply_text("❌ Erro ao salvar na planilha.")

    except Exception as e:
        print(e)
        await update.message.reply_text("❌ Erro ao processar a mensagem.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.first_name
    await update.message.reply_text("🔍 Processando imagem...")

    photo_file = await update.message.photo[-1].get_file()
    photo_path = "temp_photo.jpg"
    await photo_file.download_to_drive(photo_path)

    try:
        text = pytesseract.image_to_string(Image.open(photo_path), lang="por")
        print("Texto extraído da imagem:", text)
        os.remove(photo_path)

        # Identificar categoria com base no texto extraído
        category = identify_category(text)

        # Extrair descrição: pegar a primeira linha não vazia
        description = next((line.strip() for line in text.splitlines() if line.strip()), "Sem descrição")

        cost_match = re.search(r"[Vv]alor\s*:?\s*R?\$?\s*([\d.,]+)", text)

        # Se não encontrar, tenta só pegar o valor que começa com R$
        if not cost_match:
            cost_match = re.search(r"R\$\s*([\d.,]+)", text)

        if cost_match:
            cost = float(cost_match.group(1).replace(",", "."))
            print("Valor identificado:", cost)
        else:
            print("Valor não encontrado")


        # Tipo fixo como Despesa (você pode melhorar a lógica aqui)
        type_ = "Despesa"

        data = {
            "type": type_,
            "description": description,
            "category": category,
            "cost": cost,
            "user": user,
        }

        print("Dados a enviar:", data)

        response = requests.post(GOOGLE_SHEET_URL, json=data)
        result = response.json()

        if result.get("result") == "Success":
            await update.message.reply_text(
                f"✅ Adicionado: {data['description']} ({data['category']}) - R${data['cost']}"
            )
        else:
            await update.message.reply_text("❌ Erro ao salvar na planilha.")

    except Exception as e:
        print(e)
        await update.message.reply_text("❌ Erro ao processar a imagem.")

# 👉 Função principal
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("🤖 Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
