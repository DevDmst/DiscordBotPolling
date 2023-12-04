# This example requires the 'message_content' intent.
import asyncio
import datetime
import logging

import discord
from discord import Message, Member

import utils
from database_classes import Pool, User

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

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
    
    """

pool_message = \
"""Опрос(/exit)
Заголовок: {0} (/title <название>)
Текст: {1} (/text <текст>)
Время начала опроса: {2} (/date_start <t:1701663900:f>)
Время окончания: {3} (/date_end <t:1701663910:f>)
Разрешённые реакции: {4} (для указания укажите реакции на данное сообщение)
В каком канале: {5} (/this)

Даты можно получить на сайте https://hammertime.cyou/ru
Начать опрос: /start
"""


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message: Message):

    if message.author == client.user:
        return
    if message.content.startswith('/'):
        await command_handler(message)


async def command_handler(message: Message):
    text: str = message.content
    author: Member = message.author

    # TODO нужно добавить разрешения для бота Permissions.manage_messages
    # await message.delete()

    # TODO сделать так, чтобы создавать и редактировать опрос можно было только в личных сообщениях с ботом.
    # в канале же должны быть только активны две команды - this и start(если пользователь решит
    # запустить опрос самостоятельно, а не через запланированную дату start_date)

    if not is_user_added_to_db(author.id):
        User.add_new_user(author.id, author.name, author.global_name)

    user: User = User.get_user(author.id)
    is_editing_pool_exist = True if user.editing_pool else False

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

    elif text.startswith("/this"):
        # TODO получить реакции с сообщения и сохранить их в pool.reactions
        # получить id канала и сохранить его в pool.channel_id
        pass

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
        ('['+''.join(pool.reactions)+']') if pool.reactions else no,
        pool.channel_id if pool.channel_id else no,
    )

def is_user_added_to_db(id: int):
    if User.get_user(id):
        return True
    return False


client.run(BOT_TOKEN, log_level=logging.INFO, log_handler=handler, root_logger=True)
