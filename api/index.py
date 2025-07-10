import os
import re
import asyncio # Importar asyncio
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.ext import CallbackContext
import requests
from flask import Flask, request, jsonify

# -----------------------------------------------------------
# 👉 Configurações e Funções Auxiliares
# -----------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")

print(f"BOT_TOKEN carregado: {BOT_TOKEN}")

instructions = """
👋 Olá! Envie sua transação no formato:

👉 *Por texto:*
Tipo: Despesa ou Entrada
Descrição: Mercado
Categoria: Supermercado
Valor: 12.50
"""

def find_match(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(instructions, parse_mode=ParseMode.MARKDOWN_V2)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(instructions, parse_mode=ParseMode.MARKDOWN_V2)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo the user message."""
    if update.message:
        print(f"Recebida mensagem: {update.message.text} do usuário: {update.message.from_user.first_name}")
        await update.message.reply_text(f"Você disse: {update.message.text}")
    else:
        print("Recebida uma atualização sem mensagem de texto.")

# async def handle_text(...): # Seu handler original (comentado)

# -----------------------------------------------------------
# 👉 Configuração do Flask e Inicialização Assíncrona do PTB
# -----------------------------------------------------------

app = Flask(__name__)

# Instancia o Application do python-telegram-bot
application = Application.builder().token(BOT_TOKEN).build()

# Adicione os handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
# application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# CORREÇÃO CRÍTICA: Inicializa a aplicação PTB de forma assíncrona uma única vez
# Isso é necessário porque initialize() é uma corrotina.
try:
    asyncio.run(application.initialize())
    print("Application do python-telegram-bot inicializada com sucesso!")
except RuntimeError as e:
    if "Cannot run asyncio.run() while another loop is running" in str(e):
        # Isso pode acontecer em ambientes como Gunicorn/Werkzeug que já têm um loop
        # Deixe o initialize rodar no loop existente se já houver um.
        # Caso contrário, o erro "was never awaited" persiste.
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                loop.run_until_complete(application.initialize())
            else:
                # Se o loop já estiver rodando, use create_task para agendar
                loop.create_task(application.initialize())
            print("Application do python-telegram-bot agendada para inicialização no loop existente.")
        except Exception as inner_e:
            print(f"Erro ao tentar inicializar Application no loop existente: {inner_e}")
    else:
        print(f"Erro inesperado ao inicializar Application: {e}")

# Rotas do Flask
@app.post('/api')
async def webhook():
    """Handle incoming Telegram updates."""
    if request.method == "POST":
        update_json = request.get_json(force=True)
        if not update_json:
            print("Nenhum dado JSON recebido.")
            return jsonify({"status": "no data"}), 200

        try:
            update = Update.de_json(update_json, application.bot)
            await application.process_update(update)

        except Exception as e:
            print(f"Erro ao processar update do Telegram: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

        return jsonify({"status": "ok"}), 200
    print("Método não permitido para /api.")
    return jsonify({"status": "method not allowed"}), 405

@app.route('/api', methods=['GET'])
def api_get_test():
    return jsonify({"status": "API endpoint is active via GET method."}), 200

# -----------------------------------------------------------
# Para testes locais
# -----------------------------------------------------------
if __name__ == '__main__':
    print("Rodando Flask localmente. Use ngrok para expor para o Telegram.")
    app.run(debug=True, port=5000)