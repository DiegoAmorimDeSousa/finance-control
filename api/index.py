import os
import re
import asyncio
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


# SEU HANDLER ORIGINAL (COMENTADO PARA TESTAR O ECHO PRIMEIRO)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.message.from_user.first_name

    try:
        type_match = find_match(r"Tipo:\s*(.+)", text)
        description_match = find_match(r"Descrição:\s*(.+)", text)
        category_match = find_match(r"Categoria:\s*(.+)", text)
        cost_match = find_match(r"Valor:\s*([\d.,]+)", text)

        if not all([type_match, description_match, category_match, cost_match]):
            await update.message.reply_text(f"⚠️ Formato incorreto. Envie assim:\n{instructions}", parse_mode=ParseMode.MARKDOWN_V2)
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
            await update.message.reply_text(f"✅ Adicionado: {data['description']} ({data['category']}) - R${data['cost']:.2f}")
        else:
            await update.message.reply_text("❌ Erro ao salvar na planilha.")

    except Exception as e:
        print(f"Erro ao processar mensagem: {e}")
        await update.message.reply_text("❌ Erro ao processar a mensagem.")

# -----------------------------------------------------------
# 👉 Configuração do Flask e Inicialização Controlada do PTB
# -----------------------------------------------------------

app = Flask(__name__)

# Instancia o Application do python-telegram-bot globalmente
application = Application.builder().token(BOT_TOKEN).build()

# Flag para garantir que a inicialização ocorra apenas uma vez
_application_initialized = False

# Adicione os handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
# application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


# Rota POST para o webhook
@app.post('/api')
async def webhook():
    """Handle incoming Telegram updates."""
    global _application_initialized # Acessa a flag global

    if not _application_initialized:
        try:
            # Inicializa a Application apenas na primeira requisição da instância serverless
            await application.initialize()
            _application_initialized = True
            print("Application do python-telegram-bot inicializada na primeira requisição!")
        except Exception as e:
            print(f"Erro ao inicializar Application na primeira requisição: {e}")
            return jsonify({"status": "error", "message": "Failed to initialize bot"}), 500

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
        finally:
            # CORREÇÃO CRÍTICA: Desliga a aplicação do PTB para liberar conexões
            # Isso é crucial para funções serverless para evitar "Connection pool is closed"
            await application.shutdown()
            print("Application do python-telegram-bot desligada após processamento.")


        return jsonify({"status": "ok"}), 200
    print("Método não permitido para /api.")
    return jsonify({"status": "method not allowed"}), 405

# Rota GET para teste no navegador (OPCIONAL)
@app.route('/api', methods=['GET'])
def api_get_test():
    return jsonify({"status": "API endpoint is active via GET method."}), 200

# -----------------------------------------------------------
# Para testes locais com Hypercorn (RECOMENDADO!)
# -----------------------------------------------------------
if __name__ == '__main__':
    print("Este script deve ser executado com Hypercorn para testes locais.")
    print("Use o comando: hypercorn api.index:app --bind 0.0.0.0:5000 --reload")
    # Removendo app.run() para forçar o uso de um servidor ASGI como Hypercorn
    # app.run(debug=True, port=5000)