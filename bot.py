import os
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

# 👉 Carregar variáveis de ambiente
load_dotenv()

# 👉 Configurações
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")

# 👉 Configurações para Webhook
# O Render define a porta para o seu serviço via variável de ambiente PORT
PORT = int(os.environ.get('PORT', 8080)) # Padrão para 8080 se não definida (para desenvolvimento local)

# O URL base do seu serviço Render. VOCÊ DEVE CONFIGURAR ISSO NO RENDER!
# Ex: https://seu-nome-do-servico.onrender.com
WEBHOOK_URL = os.getenv("WEBHOOK_URL") 

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
"""

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

# 👉 Função principal
def main():
    """Start the bot using webhooks."""
    if not BOT_TOKEN or not GOOGLE_SHEET_URL or not WEBHOOK_URL:
        print("Erro: Verifique se todas as variáveis de ambiente (TELEGRAM_BOT_TOKEN, GOOGLE_SHEET_URL, WEBHOOK_URL) estão definidas.")
        exit(1)

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Construa o URL completo do webhook
    # É uma boa prática usar o token do bot como parte do caminho do webhook para segurança
    webhook_path = BOT_TOKEN 
    full_webhook_url = f"{WEBHOOK_URL}/{webhook_path}"

    # Configure e inicie o webhook
    print(f"🤖 Bot configurado para Webhook em: {full_webhook_url}")
    print(f"Escutando na porta: {PORT}")

    application.run_webhook(
        listen="0.0.0.0", # Escuta em todas as interfaces
        port=PORT,         # A porta que o Render atribui
        url_path=webhook_path, # O caminho URL que o Telegram enviará as atualizações
        webhook_url=full_webhook_url # O URL completo que o Telegram deve usar
    )

if __name__ == "__main__":
    main()