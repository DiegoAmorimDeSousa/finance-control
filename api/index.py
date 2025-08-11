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

# ✨ CORREÇÃO AQUI: Adiciona uma variável para verificar o ambiente
# A Vercel define a variável de ambiente 'VERCEL' com o valor '1' em produção.
# Isso nos permite diferenciar o ambiente local do ambiente serverless da Vercel.
IS_VERCEL_ENV = os.getenv("VERCEL") == "1"

print(f"BOT_TOKEN carregado: {BOT_TOKEN}")
print(f"Ambiente Vercel detectado: {IS_VERCEL_ENV}") # Mensagem útil para depuração

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


# SEU HANDLER ORIGINAL
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.message.from_user.first_name
    
    # Divide o texto em partes, usando '||' como separador.
    # O resultado será uma lista, por exemplo: ['Tipo: Saída...', ' Tipo: Saída...']
    transactions_text = text.split('|')
    
    # Loop para processar cada parte do texto (cada transação)
    for transaction_text in transactions_text:
        try:
            # Note o .strip() para remover espaços em branco no início e no fim de cada item.
            type_match = find_match(r"Tipo:\s*(.+)", transaction_text.strip())
            description_match = find_match(r"Descrição:\s*(.+)", transaction_text.strip())
            category_match = find_match(r"Categoria:\s*(.+)", transaction_text.strip())
            cost_match = find_match(r"Valor:\s*([\d.,]+)", transaction_text.strip())

            # Se alguma das partes estiver faltando em uma transação, pula para a próxima
            # e informa o usuário sobre o erro.
            if not all([type_match, description_match, category_match, cost_match]):
                await update.message.reply_text(f"⚠️ Formato incorreto em uma das transações. Verifique a sintaxe: {transaction_text.strip()}", parse_mode=ParseMode.MARKDOWN_V2)
                continue  # Pula para a próxima iteração do loop

            data = {
                "type": type_match,
                "description": description_match,
                "category": category_match,
                "cost": float(cost_match.replace(",", ".")),
                "user": user,
            }

            # A requisição agora está dentro do loop
            response = requests.post('https://script.google.com/macros/s/AKfycbzdxJ_sNQ9vLMMybyZ79xWlZFOxni02rtZIb-C3xGGKH1in0GaGGF7v3C-jpobCeXEv/exec', json=data)
            
            # Checagem para garantir que a resposta é um JSON antes de tentar o parse
            try:
                result = response.json()
            except requests.exceptions.JSONDecodeError:
                print(f"Erro: Resposta não é um JSON válido. Resposta: {response.text}")
                await update.message.reply_text("❌ Erro ao processar a resposta da API do Google Sheets. O formato não é um JSON válido.")
                continue # Pula para a próxima iteração do loop

            if result.get("result") == "Success":
                await update.message.reply_text(f"✅ Adicionado: {data['description']} ({data['category']}) - R${data['cost']:.2f}")
            else:
                await update.message.reply_text(f"❌ Erro ao salvar '{data['description']}' na planilha.")

        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao processar uma das transações: {transaction_text.strip()}")

# -----------------------------------------------------------
# 👉 Configuração do Flask e Inicialização Controlada do PTB
# -----------------------------------------------------------

app = Flask(__name__)

# Instancia o Application do python-telegram-bot globalmente
application = Application.builder().token(BOT_TOKEN).build()

# Flag para garantir que a inicialização ocorra apenas uma vez por "boot" da instância serverless (Vercel)
# ou por processo local (Hypercorn).
_application_initialized = False

# Adicione os handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


# Rota POST para o webhook
@app.post('/api')
async def webhook():
    """Handle incoming Telegram updates."""
    global _application_initialized # Acessa a flag global

    # Inicializa a Application apenas na primeira requisição da instância serverless
    # ou na primeira requisição em ambiente local.
    if not _application_initialized:
        try:
            await application.initialize()
            _application_initialized = True
            print("Application do python-telegram-bot inicializada na primeira requisição!")
        except Exception as e:
            print(f"Erro ao inicializar Application na primeira requisição: {e}")
            return jsonify({"status": "error", "message": "Failed to initialize bot"}), 500

    if request.method == "POST":
        update_json = request.get_json(force=True)
        # ✨ Opcional: Adicione este print para ver o payload completo recebido ✨
        print(f"Payload recebido no webhook: {update_json}")
        
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
            # ✨ CORREÇÃO AQUI: Condiciona o desligamento da aplicação ao ambiente Vercel
            # Isso é crucial: em ambiente serverless (Vercel), a aplicação é efêmera e
            # precisa liberar recursos após cada requisição. Em ambiente local (Hypercorn),
            # o servidor é persistente e a aplicação deve permanecer ativa.
            if IS_VERCEL_ENV:
                await application.shutdown()
                print("Application do python-telegram-bot desligada após processamento (Ambiente Vercel).")
            else:
                print("Em ambiente local, a Application do python-telegram-bot permanece ativa.")


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