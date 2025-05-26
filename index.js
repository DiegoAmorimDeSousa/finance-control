require('dotenv').config();
const { Telegraf } = require('telegraf');

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);

bot.start((ctx) => ctx.reply(`
  Olá! Envie sua nova transação no formato: 
  Tipo (Despesa / Entrada):
  Descrição: 
  Categoria:
  Valor: 
`));
bot.help((ctx) => ctx.reply(`
  Envie sua nova transação no formato: 
  Tipo (Despesa / Entrada):
  Descrição: 
  Categoria:
  Valor: 
`));

bot.on('text', async (ctx) => {
  const message = ctx.message.text;
  const user = ctx.message.from.first_name;

  try {
    const typeMatch = message.match(/Tipo:\s*(.+)/i);
    const descriptionMatch = message.match(/Descrição:\s*(.+)/i);
    const categoryMatch = message.match(/Categoria:\s*(.+)/i);
    const costMatch = message.match(/Valor:\s*([\d.,]+)/i);

    console.log('typeMatch', typeMatch)

    if (!typeMatch || !descriptionMatch || !categoryMatch || !costMatch) {
      ctx.reply(`
      ⚠️ Formato incorreto. Envie sua transação assim:

      Tipo: Despesa ou Entrada
      Descrição: Teste
      Categoria: Mercado
      Valor: 12.50
      `);
      return;
    }

    const description = descriptionMatch[1].trim();
    const category = categoryMatch[1].trim();
    const cost = parseFloat(costMatch[1].replace(',', '.'));
    const type = typeMatch[1].trim().toLowerCase();

    const data = {
      type,
      description,
      category,
      cost,
      user,
    };

    const response = await fetch(process.env.GOOGLE_SHEET_URL, {
      method: 'POST',
      body: JSON.stringify(data),
      headers: { 'Content-Type': 'application/json' },
    });

    const result = await response.json();

    if (result.result === 'Success') {
      ctx.reply(`✅ Adicionado: ${description} (${category}) - R$${cost}`);
    } else {
      ctx.reply('❌ Erro ao salvar na planilha.');
    }
  } catch (error) {
    console.error(error);
    ctx.reply('❌ Erro ao conectar com a planilha.');
  }
});

bot.launch();
console.log('Bot rodando...');
