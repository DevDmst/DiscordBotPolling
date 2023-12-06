# This example requires the 'message_content' intent.
import asyncio
import datetime
import logging
from typing import Callable

import discord
from discord import Message, Member, TextChannel, Embed
from discord.ext import commands
from discord.ext.commands import Context, CheckFailure
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
        /start_date \<t:0000000000:f> - время начала опроса.
        /end_date \<t:0000000001:f> - время окончания опроса.
        /where  <link> - указать канал куда будет публиковаться опрос.
        /start - начать опрос(или нажать кнопку)
    
    /pools - показать все опросы
    Даты можно получить на сайте https://hammertime.cyou/ru
    """

pool_message = \
    """Опрос(/exit)
    Заголовок: {0} (/title <название>)
    Текст: {1} (/text <текст>)
    Время начала опроса: {2} (/start_date \<t:1701663900:f>)
    Время окончания: {3} (/end_date \<t:1701663910:f>)
    Разрешённые реакции: {4} (для указания укажите реакции на данное сообщение)
    В каком канале: {5} (/where <link>)
    
    Даты можно получить на сайте https://hammertime.cyou/ru
    Начать опрос: /start
    """

pools_message = \
    """Список твоих опросов:
     {0}"""

pools_pool_message = "\"```{0}```\" от {1} до {2} в канале <#{3}> с реакциями \"{4}\""


def get_user(discord_user: Member) -> User:
    user = User.get_user(discord_user.id)
    if user is None:
        User.add_new_user(discord_user.id, discord_user.name, discord_user.global_name)
        user = User.get_user(discord_user.id)
    return user


async def create_view(*args):
    #     btn = Button(label=label)
    #     btn.callback = callback
    view = View()
    view.add_item(*args)
    return view


async def check_editing_pool(ctx: Context, user: User):
    if not user.editing_pool:
        await ctx.send("У Вас нет текущих опросов.", delete_after=3)
        return False
    return True


async def update_chat__creating_pool(ctx, pool):
    old_msg = await ctx.channel.fetch_message(pool.message_id)
    await old_msg.delete()
    new_msg = await ctx.send(content=format_pool(pool), suppress_embeds=True)
    pool.message_id = new_msg.id


def is_private_chat(ctx: Context):
    if ctx.channel.type.name == "private":
        return True
    return False


@bot.event
async def on_ready():
    logging.info("Бот запущен")


@bot.command()
@commands.check(is_private_chat)
async def help(ctx: Context):
    await ctx.send(help_message)


@bot.command()
@commands.check(is_private_chat)
async def pools(ctx: Context):
    user = get_user(ctx.author)

    output = ""
    for i in user.pools:
        output += pools_pool_message.format(
            i.title if i.title else no,
            i.start_date if i.start_date else no,
            i.end_date if i.end_date else no,
            f"<#{i.channel_id}>" if i.channel_id else no,
            ''.join(i.reactions) if i.reactions else no,
        )

    await ctx.send(output)
    # mess = await channel.send('Набор в игру')
    # await asyncio.sleep(10)
    # mess = await ctx.channel.fetch_message(mess.id)
    # if yes_react := discord.utils.get(mess.reactions, emoji=ctx.guild.get_emoji(471483388532742130)):
    #     async for user in yes_react.users:
    #         print(str(user))  # выведет всех пользователей поставивших реакцию в консоль


@bot.command()
@commands.check(is_private_chat)
async def exit_(ctx: Context, *args):
    user = get_user(ctx.author)
    if user.editing_pool:
        user.editing_pool = None
    user.update(True)
    await ctx.send('Готово. Можете создавать новый опрос!', )


@bot.command()
@commands.check(is_private_chat)
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
        message_ = await ctx.send(format_pool(pool), suppress_embeds=True)
        pool.message_id = message_.id

        user.update(True)


@bot.command(
    help="Используйте команду в формате /title \<заголовок>",
    description="Устанавливает заголовок для текущего опроса",
    brief="Устанавливает заголовок",
)
async def title(ctx: Context, *args):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    title_ = ' '.join(args)
    pool = user.get_editing_pool()
    pool.title = title_

    await update_chat__creating_pool(ctx, pool)

    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
async def text(ctx, *args):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    text_ = ' '.join(args)
    pool = user.get_editing_pool()
    pool.text = text_

    await update_chat__creating_pool(ctx, pool)

    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
async def start_date(ctx, datetime_formatted):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    pool = user.get_editing_pool()
    pool.start_date = utils.convert_formatted_timestamp_to_datetime(datetime_formatted)

    await update_chat__creating_pool(ctx, pool)

    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
async def end_date(ctx, datetime_formatted):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    pool = user.get_editing_pool()
    pool.end_date = utils.convert_formatted_timestamp_to_datetime(datetime_formatted)

    await update_chat__creating_pool(ctx, pool)

    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
async def where(ctx: Context, *args):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    link = " ".join(args)
    try:
        channel_id = int(link[link.rfind("/") + 1:])
    except:
        await ctx.send("Введите команду в формате: /where \\<link>. Например:\n"
                       "https://discord.com/channеls/1180510913149800478/1180510913149800481", delete_after=7)
        user.close_session()
        return

    pool = user.get_editing_pool()
    pool.channel_id = channel_id

    await update_chat__creating_pool(ctx, pool)

    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
async def start(ctx, ):
    """Отправить опрос в чат"""
    pass


@new_pool.error
@exit_.error
@title.error
@text.error
@start_date.error
@end_date.error
@where.error
@pools.error
async def handler_creating_pool_errors(ctx: Context, error):
    if isinstance(error, CheckFailure):
        await ctx.message.delete(delay=4)
        await ctx.send("Данная команда доступна только в личных сообщениях бота", delete_after=3.5)
    else:
        await ctx.send(error)
        logging.error(error)


def pool_str_representation(pool: Pool):
    return f"Опрос: {pool.title}\n\n{pool.text}"


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


bot.run(BOT_TOKEN, log_level=logging.INFO, log_handler=handler, root_logger=True)
