import os
import re
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode # Importe ParseMode para usar HTML/Markdown
from telegram.ext.callbackcontext import CallbackContext # Necessário para o RequestHandler
from http.server import BaseHTTPRequestHandler # Para tipagem do RequestHandler
import requests

# Importa Flask e Request (para lidar com a requisição HTTP)
from flask import Flask, request, jsonify

# -----------------------------------------------------------
# 👉 Configurações e Funções Auxiliares (mantêm-se as mesmas)
# -----------------------------------------------------------

load_dotenv() # Carregar variáveis de ambiente localmente (para desenvolvimento)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")

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

# 👉 Handlers assíncronos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(instructions, parse_mode=ParseMode.MARKDOWN_V2) # Use Markdown para formatação

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(instructions, parse_mode=ParseMode.MARKDOWN_V2)

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
# 👉 Configuração do Flask para a função Serverless da Vercel
# -----------------------------------------------------------

# Instancia o aplicativo Flask
app = Flask(__name__)

# Instancia o Application do python-telegram-bot
# É importante construir o Application fora da função `handler`
# para evitar recriá-lo a cada requisição (otimização para serverless)
application = Application.builder().token(BOT_TOKEN).build()

# Adicione os handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

# Construa o objeto Bot para setar o webhook
# Isso será usado apenas uma vez para configurar o webhook no Telegram
ptb_bot = Bot(BOT_TOKEN)

@app.route('/', methods=['POST'])
async def webhook():
    """Handle incoming Telegram updates."""
    if request.method == "POST":
        update_json = request.get_json(force=True)
        if not update_json:
            return jsonify({"status": "no data"}), 200

        # Processa a atualização usando o Application do python-telegram-bot
        # Isso é o equivalente a run_webhook, mas dentro de uma função HTTP
        try:
            # O RequestHandler do PTB espera um BaseHTTPRequestHandler.
            # Para Flask, precisamos mockar isso ou usar um método mais direto.
            # A forma mais comum é passar o JSON diretamente para process_update.
            update = Update.de_json(update_json, ptb_bot)
            await application.process_update(update)
        except Exception as e:
            print(f"Erro ao processar update do Telegram: {e}")
            return jsonify({"status": "error"}), 500

        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "method not allowed"}), 405

# Para setar o webhook (isso deve ser chamado apenas UMA VEZ, não em cada requisição)
# Em um ambiente serverless, você faria isso manualmente ou como uma função separada.
# Para Vercel, o deploy já deve lidar com a exposição do endpoint.
# A URL final será a URL do seu deploy Vercel + /api/ (ex: https://seu-bot.vercel.app/api)
# Você precisará definir o webhook manualmente no Telegram para esta URL,
# ou criar um endpoint /set_webhook na Vercel para isso.

# -----------------------------------------------------------
# Para testes locais (opcional, requer ngrok ou similar para testar webhook)
# ou para rodar um servidor de desenvolvimento Flask
# -----------------------------------------------------------
if __name__ == '__main__':
    print("Rodando Flask localmente. Use ngrok para expor para o Telegram.")
    # Você pode rodar com Flask: flask run --host=0.0.0.0 --port=5000
    # Ou diretamente com o app.run:
    # app.run(debug=True, port=5000)
    pass # A Vercel vai chamar a função webhook diretamente