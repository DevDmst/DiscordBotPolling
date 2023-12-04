# This example requires the 'message_content' intent.
import asyncio
import datetime
import logging
from typing import Callable

import discord
from discord import Message, Member
from discord.ext import commands
from discord.ext.commands import Context
from discord.ui import Button, View
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from icecream import ic

import utils
from database_classes import Pool, User

# Создайте экземпляр планировщика
# scheduler = AsyncIOScheduler()

# Установите время запуска (здесь установлено на 2023-12-04 12:00:00)
# trigger_time = datetime.datetime(2023, 12, 4, 12, 0, 0)

# Запланируйте задачу
# scheduler.add_job(..., trigger='date', run_date=trigger_time)

# Запустите планировщик
# scheduler.start()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

description = 'An example bot to showcase the discord.ext.commands'

bot = commands.Bot(command_prefix='/', description=description, intents=intents)
bot.remove_command('help')

bot_config = utils.load_config_from_file("bot_config.yaml")
BOT_TOKEN = bot_config["bot_token"]

handler = logging.StreamHandler()
# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

TIME_FORMAT = "%d.%m.%Y %H:%M"

no = "*не указано*"
example = {"name": no, "text": no, "date": None, "reactions": [], "channel": None}
help_message = \
    """ Список команд:
    /help - вывести это.
    
    /new_pool - создать новый опрос.
        /title <название> - заголовок.
        /text <текст> - текст опроса.
        /date_start <t:0000000000:f> - время начала опроса.
        /date_end <t:0000000001:f> - время окончания опроса.
        /this - указать канал куда будет публиковаться опрос.
        /start - начать опрос(или нажать кнопку)
    
    /pools - вывети все свои опросы
    Даты можно получить на сайте https://hammertime.cyou/ru
    """

pool_message = \
    """Опрос(/exit)
    Заголовок: {0} (/title <название>)
    Текст: {1} (/text <текст>)
    Время начала опроса: {2} (/start_date \<t:1701663900:f>)
    Время окончания: {3} (/end_date \<t:1701663910:f>)
    Разрешённые реакции: {4} (для указания укажите реакции на данное сообщение)
    В каком канале: <#{5}> (/this)
    
    Даты можно получить на сайте https://hammertime.cyou/ru
    Начать опрос: /start
    """

pools_message = \
"""Список твоих опросов:
 {0}"""

pools_pool_message = "\"```{0}```\" от {1} до {2} в канале <#{3}> с реакциями \"{4}\""

def get_user(discord_user: Member):
    user = User.get_user(discord_user.id)
    if user is None:
        User.add_new_user(discord_user.id, discord_user.name, discord_user.global_name)
        user = User.get_user(discord_user.id)
    return user

async def delete_message(interaction: discord.Interaction):
    await interaction.response.delete()

async def create_view(*args):
#     btn = Button(label=label)
#     btn.callback = callback
    view = View()
    view.add_item(*args)
    return view

async def check_editing_pool(ctx: Context, user):
    if not user.editing_pool:
        await ctx.send("У Вас нет текущих опросов.")
        return False
    return True

@bot.command()
async def help(ctx: Context):
    await ctx.send(help_message)

@bot.command()
async def pools(ctx: Context):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    output = ""
    for i in user.pools:
        output += pools_pool_message.format(
            i.title if i.title else no,
            i.start_date if i.start_date else no,
            i.end_date if i.end_date else no,
            ''.join(i.reactions) if i.reactions else no,
            f"<#{i.channel_name}>" if i.channel_name else no,
            )

    return pools_pool_message.format(output)


@bot.command()
async def new_pool(ctx: Context, *args):
    user = get_user(ctx.author)
    if user.editing_pool:
        await ctx.send("Вы не можете начать создавать новый опрос, "
                       "пока не завершили старый. Чтобы завершить старый опрос,"
                       " введите команду /exit_", delete_after=5)
    else:
        pool = Pool()
        user.pools.append(pool)
        user.update()

        user.editing_pool = pool.id
        message_ = await ctx.send(format_pool(pool))
        pool.message_id = message_.id

        user.update(True)

@bot.command()
async def exit_(ctx: Context, *args):
    user = get_user(ctx.author)
    if user.editing_pool:
        user.editing_pool = None
    user.update(True)
    await ctx.send('Готово. Можете создавать новый опрос!')

@bot.command()
async def title(ctx: Context, *args):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    title = ' '.join(args)
    pool = user.get_editing_pool()
    pool.title = title
    pool.update()
    await edit_message_pool(ctx.message, pool)

    user.close_session()
    pool.close_session()


@bot.command()
async def text(ctx, *args):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    text = ' '.join(args)
    pool = user.get_editing_pool()
    pool.text = text
    pool.update()
    await edit_message_pool(ctx.message, pool)

    user.close_session()
    pool.close_session()


@bot.command()
async def start_date(ctx, datetime_formatted):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    pool = user.get_editing_pool()
    pool.start_date = utils.convert_formatted_timestamp_to_datetime(datetime_formatted)
    pool.update()
    await edit_message_pool(ctx.message, pool)

    user.close_session()
    pool.close_session()


@bot.command()
async def end_date(ctx, datetime_formatted):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    pool = user.get_editing_pool()
    pool.end_date = utils.convert_formatted_timestamp_to_datetime(datetime_formatted)
    pool.update()
    await edit_message_pool(ctx.message, pool)

    user.close_session()
    pool.close_session()


@bot.command()
async def this(ctx, *args):

    pass


@bot.command()
async def start(ctx, ):
    """Repeats a message multiple times."""
    pass


async def handle_private_messages(user, is_editing_pool_exist, message, text):
    text: str = message.content
    author: Member = message.author

    if not is_user_added_to_db(author.id):
        User.add_new_user(author.id, author.name, author.global_name)

    if text.startswith("/eval"):
        await message.channel.send(eval(text[6:]))

    if text.startswith("/help"):
        await message.channel.send(help_message)

    elif text == "/pools":
        str_pools = '\n'.join([f"{num}. {pool}" for num, pool in enumerate(user.pools)])
        pool = user.get_editing_pool()
        await message.channel.send(f"Ваши опросы:\n"
                                   f"{str_pools}\n\n"
                                   f"Текущий выбранный опрос:\n"
                                   f"{pool.title}\n\n"
                                   f"Для манипуляций с опросами нужно прописывать индекс опроса.")

    elif text.startswith("/new_pool"):
        # если у пользователя есть текущий редактируемый опрос,
        # спрашиваем его о том, как быть - продолжать редактирование старого или создать новый
        if user.editing_pool:
            # TODO отправить вопрос и добавить обработчики ответа
            pass
        else:
            pool = Pool()
            user.pools.append(pool)
            user.update()

            user.editing_pool = pool.id
            message_ = await message.channel.send(format_pool(pool))
            pool.message_id = message_.id

            user.update()

    elif text.startswith("/title"):
        # TODO добавить проверку на то, чтобы не было одинаковых titles у одного пользователя
        title = text.replace("/title", "").strip()
        if not title:
            await message.channel.send("Ошибка: некорректный формат. Правильный формат: /title <название>")
            pass

        if is_editing_pool_exist:
            pool = user.get_editing_pool()
            pool.title = title
            pool.update()

            await edit_message_pool(message, pool)

    elif text.startswith("/text"):
        if is_editing_pool_exist:
            text = text.replace("/text", "").strip()
            pool = user.get_editing_pool()
            pool.text = text
            pool.update()

            await edit_message_pool(message, pool)

    elif text.startswith("/start_data"):
        if is_editing_pool_exist:
            start_data_str = text.replace("/start_data", "").strip()
            pool = user.get_editing_pool()
            pool.start_date = utils.convert_formatted_timestamp_to_datetime(start_data_str)
            pool.update()

            await edit_message_pool(message, pool)

    elif text.startswith("/end_data"):
        if is_editing_pool_exist:
            end_data_str = text.replace("/end_data", "").strip()
            pool = user.get_editing_pool()
            pool.end_date = utils.convert_formatted_timestamp_to_datetime(end_data_str)
            pool.update()

            await edit_message_pool(message, pool)

    user.close_session()


async def edit_message_pool(message, pool):
    message = message.channel.get_partial_message(pool.message_id)
    await message.edit(content=format_pool(pool))

def format_pool(pool: Pool) -> str:
    return pool_message.format(
        pool.title if pool.title else no,
        pool.text if pool.text else no,
        utils.convert_datetime_to_formatted_timestamp(pool.start_date) if pool.start_date else no,
        utils.convert_datetime_to_formatted_timestamp(pool.end_date) if pool.end_date else no,
        ('[' + ''.join(pool.reactions) + ']') if pool.reactions else no,
        f"<#{pool.channel_id}>" if pool.channel_id else no,
    )

def is_user_added_to_db(id: int) -> bool:
    if User.get_user(id):
        return True
    return False

async def counter():
    while True:
        ...

bot.run(BOT_TOKEN, log_level=logging.INFO, log_handler=handler, root_logger=True)
