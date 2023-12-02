import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')

@bot.command()
async def poll(ctx, question, *options):
    if len(options) > 10:
        await ctx.send("Максимальное количество вариантов ответа - 10.")
        return

    reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

    embed = discord.Embed(title='Опрос', description=question, color=discord.Color.blue())

    for i, option in enumerate(options):
        embed.add_field(name=f'{reactions[i]}', value=option, inline=False)

    message = await ctx.send(embed=embed)

    for i in range(len(options)):
        await message.add_reaction(reactions[i])

    # Установите время опроса (в секундах)
    time_limit = 60

    # Ожидаем реакции в течение заданного времени
    await asyncio.sleep(time_limit)

    updated_message = await ctx.channel.fetch_message(message.id)

    result = []
    for reaction in updated_message.reactions:
        result.append(reaction.count-1)  # Исключаем реакцию бота

    # Формируем сообщение с результатами опроса
    result_message = "Результаты опроса:\n"
    for i, (option, count) in enumerate(zip(options, result)):
        result_message += f"{reactions[i]} {option}: {count} голосов\n"

    await ctx.send(result_message)

    # Если вы хотите отправить результаты в личные сообщения, раскомментируйте следующую строку
    # await ctx.author.send(result_message)

bot.run('YOUR_TOKEN')