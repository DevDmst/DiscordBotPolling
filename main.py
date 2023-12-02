# This example requires the 'message_content' intent.
import asyncio
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


no = "*не указано*"
example = {"name": no, "text": no, "date": None, "reactions": [], "channel": None}
help = \
    """ Список команд:
    /help - вывести это.
    
    """
pool_message = \
    """Опрос(/exit)
    Название: {0}(/name <название>)
    Текст: {2}(/text <текст>)
    Время окончания: {1}(/data <02.12.23 19:20>)
    Разрешённые реакции: {3}(для указания укажите реакции на данное сообщение)
    В каком канале: {4}(/this)
    
    Начать опрос: /start
    """
all_pools = {}


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message: Message):
    print(message)
    if message.author == client.user:
        return
    if message.content.startswith('/'):
        await command_handler(message)

def is_user_added_to_db(id: int):
    if User.get_user(id):
        return True
    return False


async def command_handler(message: Message):
    text: str = message.content
    author: Member = message.author

    if not is_user_added_to_db(author.id):
        User.add_new_user(author.id, author.name, author.global_name)

    user: User = User.get_user(author.id)

    if text.startswith("/help"):
        await message.channel.send(help)

    elif text.startswith("/new_poll"):
        await message.channel.send(pool_message)

    elif text == "/pools":
        str_pools = '\n'.join([f"{num}. {pool}" for num, pool in enumerate(user.pools)])
        await message.channel.send(f"Текущие опросы:\n"
                                   f"{str_pools}\n\n"
                                   f"Для манипуляций с опросами нужно прописывать индекс опроса.")
    elif text.startswith("/name"):
        pass

    elif text.startswith("/text"):
        pass

    elif text.startswith("/data"):
        pass

    elif text.startswith("/this"):
        pass

    user.close_session()


def add_new_pool(id, user_id, title, text, end_date, reactions, channel):
    return Pool(id=id,
                user_id=user_id,
                title=title,
                text=text,
                end_date=end_date,
                reactions=reactions,
                channel=channel)


client.run(BOT_TOKEN, log_level=logging.INFO, log_handler=handler, root_logger=True)
