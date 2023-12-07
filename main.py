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
from database_classes import Pool, User, PoolStatus

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
dict_time = {
    's': 'seconds',
    'm': 'minutes',
    'h': 'hours',
    'd': 'days',
    'w': 'weeks',
    'M': 'months',
    'y': 'years'
}

no = "*не указано*"
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


def format_time(args) -> datetime.datetime:
    if args[0].startswith('<t:') and args[1].endswith('>'):
        return utils.convert_formatted_timestamp_to_datetime(args[0])
    else:
        output_time = datetime.datetime.now()
        for i in args:
            output_time += datetime.timedelta(**{})

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
    return ctx.channel.type.name == "private"


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
@commands.check(is_private_chat)
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
@commands.check(is_private_chat)
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
@commands.check(is_private_chat)
async def start_date(ctx, *args):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    pool = user.get_editing_pool()
    pool.start_date = format_time(args)

    await update_chat__creating_pool(ctx, pool)

    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
@commands.check(is_private_chat)
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
@commands.check(is_private_chat)
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
@commands.check(is_private_chat)
async def start(ctx: Context, index: int=0):
    """Отправить опрос по индексу в чат"""
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    pool = user.get_editing_pool()
    pool_str = pool_str_representation(pool)
    if pool.channel_id:
        await bot.get_channel(pool.channel_id).send(pool_str, suppress_embeds=True)
    else:
        await ctx.send("Прежде чем отправлять опрос, укажите канал для отправки (команда /where)", suppress_embeds=True)
    pool.status = PoolStatus.PUBLISHED

    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
@commands.check(is_private_chat)
async def run(ctx, ):
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


# async def send_pool_to_chat():
#     user = get_user(ctx.author)
#     if not await check_editing_pool(ctx, user):
#         return
#
#
#     pool = user.get_editing_pool()
#     pool.channel_id = channel_id
#
#     await update_chat__creating_pool(ctx, pool)
#
#     pool.update()
#     user.close_session()
#     pool.close_session()

def pool_str_representation(pool: Pool):
    return f"Опрос: {pool.title}\n\n{pool.text}"


async def edit_message_pool(message, pool):
    message = message.channel.get_partial_message(pool.message_id)
    await message.edit(content=format_pool(pool))

async def test():
    pass

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
