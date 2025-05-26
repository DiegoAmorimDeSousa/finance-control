require('dotenv').config();
const { Telegraf } = require('telegraf');

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);

bot.start((ctx) => ctx.reply('Olá! Envie sua despesa no formato: categoria - valor'));
bot.help((ctx) => ctx.reply('Envie sua despesa no formato: categoria - valor\nExemplo: mercado - 12.00'));

bot.on('text', async (ctx) => {
  const message = ctx.message.text;
  const parts = message.split('-');

  if (parts.length !== 2) {
    ctx.reply('Formato inválido. Use: categoria - valor\nExemplo: mercado - 12.00');
    return;
  }

  const categoria = parts[0].trim();
  const valor = parts[1].trim().replace(',', '.');

  if (isNaN(parseFloat(valor))) {
    ctx.reply('Valor inválido. Envie um número. Exemplo: mercado - 12.00');
    return;
  }

  const data = {
    categoria,
    valor: parseFloat(valor)
  };

  try {
    console.log('process.env.GOOGLE_SHEET_URL', process.env.GOOGLE_SHEET_URL)
    const response = await fetch(process.env.GOOGLE_SHEET_URL, {
      method: 'POST',
      body: JSON.stringify(data),
      headers: { 'Content-Type': 'application/json' },
    });

    const result = await response.json();

    if (result.result === 'Success') {
      ctx.reply(`Adicionado: ${categoria} - R$${valor}`);
    } else {
      ctx.reply('Erro ao salvar na planilha.');
    }
  } catch (error) {
    console.error(error);
    ctx.reply('Erro ao conectar com a planilha.');
  }
});

bot.launch();
console.log('Bot rodando...');
