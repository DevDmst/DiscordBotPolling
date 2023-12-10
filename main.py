import asyncio
import copy
import datetime
import logging

import discord
from discord import Message, Member, TextChannel, Embed, Colour, AllowedMentions
from discord.ext import commands
from discord.ext.commands import Context, CheckFailure
from discord.ui import Button, View
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from icecream import ic

import utils
from database_classes import Pool, User, PoolStatus
from sheduler import scheduler, schedule_start_pool, schedule_end_pool

intents = discord.Intents.default()
intents.message_content = True

description = 'An example bot to showcase the discord.ext.commands'

bot = commands.Bot(command_prefix='/', description=description, intents=intents)
bot.remove_command('help')

bot_config = utils.load_config_from_file("bot_config.yaml")
BOT_TOKEN = bot_config["bot_token"]

handler = logging.StreamHandler()
# handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

no = "*не указано*"
TIME_FORMAT = "%d.%m.%Y %H:%M"
ints = "1234567890"
pools_pool_message = "\"```{0}```\" от {1} до {2} в канале <#{3}> с реакциями \"{4}\""
time_dict = {
    's': 'seconds',
    'm': 'minutes',
    'h': 'hours',
    'd': 'days',
    'w': 'weeks',
    'M': 'months',
    'y': 'years'
}
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


channels_messages = []
admin_users = []


def init_channels_and_messages(channels_messages, admin_users):
    users, session = User.get_all_users()
    with (session):
        for user in users:
            admin_users.append(user.id)
            pools = user.get_pools()
            for pool in pools:
                str_1 = f"{pool.pool_channel_id}_{pool.pool_message_id}"
                str_2 = f"{pool.edit_channel_id}_{pool.edit_message_id}"
                if str_1 not in channels_messages:
                    channels_messages.append(str_1)
                if str_2 not in channels_messages:
                    channels_messages.append(str_2)


init_channels_and_messages(channels_messages, admin_users)


def format_time(args) -> datetime.datetime:
    if args[0].startswith('<t:') and args[0].endswith('>'):
        return utils.convert_formatted_timestamp_to_datetime(args[0])
    elif args[0] == "now":
        return None
    else:
        time = datetime.datetime.now()
        for i in args:
            time += datetime.timedelta(**{time_dict[i[-1]]: int(i[:-1])})
        return time


def get_user(discord_user: Member | int) -> User:
    if isinstance(discord_user, int):
        user_id = discord_user
    else:
        user_id = discord_user.id
    user = User.get_user(user_id)
    if user is None and not isinstance(discord_user, int):
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
    if not user.editing_pool_id:
        await ctx.send("У Вас нет текущих опросов.", delete_after=3)
        return False
    return True


async def update_chat__creating_pool(ctx, pool):
    old_msg = await ctx.channel.fetch_message(pool.edit_message_id)
    await old_msg.delete()
    new_msg = await ctx.send(content=format_pool(pool), suppress_embeds=True)
    pool.edit_message_id = new_msg.id


def is_private_chat(ctx: Context):
    return ctx.channel.type.name == "private"


async def pool_reactions_modify(payload: discord.RawReactionActionEvent, add=False):
    """Редактирование реакций в личных сообщениях с ботом"""
    channel_id = payload.channel_id
    channel = await bot.fetch_channel(channel_id)
    message_id = payload.message_id
    message = await channel.fetch_message(message_id)
    member = await bot.fetch_user(payload.user_id)

    user_ = get_user(payload.user_id)
    pool = user_.get_editing_pool()

    if (user_ and pool and
            pool.edit_channel_id == channel_id and
            pool.edit_message_id == message_id):
        if add:
            if pool.reactions is None:
                pool.reactions = str(payload.emoji)
            else:
                pool.reactions += str(payload.emoji)

            logging.info("Добавлена новая реакция.")
        else:
            out = ""
            for i in pool.reactions:
                if i != str(payload.emoji):
                    out += i
            pool.reactions = out
            logging.info("Удалено.")

        msg = await channel.fetch_message(pool.edit_message_id)
        await msg.edit(content=format_pool(pool), suppress=True)
        pool.update()


async def vote_pool(payload: discord.RawReactionActionEvent, add=False):
    """Приём голосов от пользователей в опубликованном опросе"""
    logging.info("Изменение реакции!")
    channel = await bot.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    rfind = message.content.rfind("@")
    author_id = int(message.content[rfind + 1:message.content.rfind(">")])
    user = User.get_user(author_id)

    pool = user.get_pool(channel.id, message.id)
    current_emoji = str(payload.emoji)

    votes = dict(pool.vote_users)

    if current_emoji not in pool.reactions:
        await message.remove_reaction(current_emoji, payload.member)
        return

    if add:
        if current_emoji not in votes:
            votes[current_emoji] = []

        for emoji, users in votes.items():
            if user.id not in users:
                users.append(user.id)
            else:
                users.remove(user.id)
                await message.remove_reaction(emoji, payload.member)
    else:
        for emoji, users in votes.items():
            if user.id in users:
                users.remove(user.id)
                break

    pool.vote_users = votes
    pool.update(True)
    user.close_session()


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await handle_reactions(payload, True)
    # # message.remove_reaction("😍", member)
    # user_ = get_user(payload.user_id)
    # pool = user_.get_editing_pool()

    # pool.vote_users = {}
    # pool.vote_users["😍"] = []
    # pool.vote_users["😍"].append(user.id)

    # if payload.member is None:
    #     # сообщение пришло из личного чата
    #     pass
    # else:
    #     # сообщение пришло из публичного чата
    #     pass

    # if (user_ and pool and
    #         pool.edit_channel_id == channel_id and
    #         pool.edit_message_id == message_id):
    #     if pool.reactions is None:
    #         pool.reactions = str(payload.emoji)
    #     else:
    #         pool.reactions += str(payload.emoji)
    #
    #     logging.info("Добавлена новая реакция.")
    #
    #     msg = await channel.fetch_message(pool.edit_message_id)
    #     await msg.edit(content=format_pool(pool), suppress=True)
    #     pool.update()
    # else:
    #     if message.type.name == "text" and message.type.name == "default":
    #         text = message.content
    #         owner = int(text[2: text.find(">")])
    #         user: User = get_user(owner)
    #         pool = user.get_pool(channel_id, message_id)
    #         current_emoji = str(payload.emoji)
    #         if current_emoji not in pool.vote_users:
    #             pool.vote_users[current_emoji] = []
    #
    #         for emoji, users_ in pool.vote_users.items():
    #             if user.id not in users_:
    #                 users_.append(user.id)
    #             else:
    #                 users_.remove(user.id)
    #                 await message.remove_reaction(emoji, user)
    #         copy_copy = copy.copy(pool.vote_users)
    #         pool.vote_users = copy_copy
    #
    #         pool.update(True)


#             user.close_session()

# user_.close_session()


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):

    await handle_reactions(payload, False)

    # message_id = payload.message_id  # ID сообщения
    # channel_id = payload.channel_id  # ID канала
    # channel = await bot.fetch_channel(channel_id)
    # user = get_user(payload.user_id)
    # if not user.editing_pool_id:
    #     user.close_session()
    #     return
    # pool = user.get_editing_pool()
    # if (pool.edit_channel_id == channel_id and
    #         pool.edit_message_id == message_id and
    #         pool.reactions and
    #         str(payload.emoji) in pool.reactions):
    #
    #     out = ""
    #     for i in pool.reactions:
    #         if i != str(payload.emoji):
    #             out += i
    #     pool.reactions = out
    #     logging.info("Удалено.")
    #
    # msg = await channel.fetch_message(pool.edit_message_id)
    # await msg.edit(content=format_pool(pool), suppress=True)
    #
    # pool.update()
    # user.close_session()
    # pool.close_session()


async def handle_reactions(payload: discord.RawReactionActionEvent, add=False):
    str_ = f"{payload.channel_id}_{payload.message_id}"
    if str_ not in channels_messages:
        return
    # когда через бота удаляешь чью-то реакцию, то member == None
    # TODO не знаю, как это разрулить
    if payload.member is None and payload.user_id in admin_users:  # редактирование
        await pool_reactions_modify(payload, add)
    else:
        if payload.member.bot:
            return
        await vote_pool(payload, add)


@bot.event
async def on_ready():
    logging.info("Бот запущен")


@bot.command()
@commands.check(is_private_chat)
async def help(ctx: Context):
    # TODO: использовать встроенный help
    await ctx.send(help_message)



@bot.command()
@commands.check(is_private_chat)
async def pools(ctx: Context):
    user = get_user(ctx.author)
    if not user.pools:
        await ctx.send("У вас нет в данный момент опросов.")
        return

    output = ""
    for i in user.pools:
        output += pools_pool_message.format(
            i.title if i.title else no,
            i.start_date.strftime(TIME_FORMAT) if i.start_date else no,
            i.end_date.strftime(TIME_FORMAT) if i.end_date else no,
            f"<#{i.pool_channel_id}>" if i.pool_channel_id else no,
            i.reactions if i.reactions else no,
        )

    await ctx.send(output)


@bot.command()
@commands.check(is_private_chat)
async def exit_(ctx: Context, *args):
    user = get_user(ctx.author)
    if user.editing_pool_id:
        user.editing_pool_id = None
    user.update(True)
    await ctx.send('Готово. Можете создавать новый опрос!', )


@bot.command()
@commands.check(is_private_chat)
async def new_pool(ctx: Context, *args):
    user = get_user(ctx.author)
    if user.editing_pool_id:
        await ctx.send("Вы не можете начать создавать новый опрос, "
                       "пока не завершили старый. Чтобы завершить старый опрос,"
                       " введите команду /exit_", delete_after=5)
    else:
        pool = Pool()
        user.pools.append(pool)
        user.update()

        user.editing_pool_id = pool.id
        message_ = await ctx.send(format_pool(pool), suppress_embeds=True)
        pool.edit_message_id = message_.id
        pool.edit_channel_id = message_.channel.id
        channels_messages.append(f"{pool.edit_channel_id}_{pool.edit_message_id}")
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
async def end_date(ctx, *args):
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    pool = user.get_editing_pool()
    pool.end_date = format_time(args)

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
    channel = await bot.fetch_channel(channel_id)
    if channel is None or channel.type.name != "text":
        await ctx.send("Данный канал не является текстовым.", delete_after=5)
    else:
        pool.pool_channel_id = channel_id

    await update_chat__creating_pool(ctx, pool)
    pool.update()
    user.close_session()
    pool.close_session()


@bot.command()
@commands.check(is_private_chat)
async def start(ctx: Context, index: int = -1):
    """Отправить опрос по индексу в чат"""
    user = get_user(ctx.author)

    pool = user.get_editing_pool()
    if not pool:
        await ctx.send("Сейчас нет редактируемого опроса. Создайте или выберите опрос, после чего повторите команду.")
        user.close_session()
        return
    if pool.pool_channel_id:
        channel = bot.get_channel(pool.pool_channel_id)
        message = await channel.send(
            content=pool.publish_format(),
            mention_author=True,
            allowed_mentions=AllowedMentions(everyone=True)
        )
        pool.pool_message_id = message.id
        pool.status = PoolStatus.PUBLISHED
        for reaction in pool.reactions:
            await message.add_reaction(reaction)
    else:
        await ctx.send("Прежде чем отправлять опрос, укажите канал для отправки (команда /where)", suppress_embeds=True)

    pool.status = PoolStatus.PUBLISHED
    pool.update(True)
    user.close_session()


@bot.command()
@commands.check(is_private_chat)
async def delete_all(ctx: Context):
    """Удалить все опросы"""
    user = get_user(ctx.author)
    user.pools.clear()
    user.update()
    await ctx.send("Успешно удалены все опросы.")
    user.close_session()


@bot.command()
@commands.check(is_private_chat)
async def run(ctx: Context, ):
    """После завершения редактирования опроса, нужно утвердить его на запуск(планирование)."""
    user = get_user(ctx.author)
    if not await check_editing_pool(ctx, user):
        return

    await schedule_start_pool(user.get_editing_pool(), send_pool_to_channel)
    schedule_end_pool(user.get_editing_pool(), get_pool_results)


@bot.command()
@commands.check(is_private_chat)
async def test(ctx: Context, index: int = -1):
    """Отправить опрос по индексу в чат"""
    user = get_user(ctx.author)

    pool = Pool()
    pool.text = "Кто вам больше нравится: Эмма Уотсон(🥺) или Эмили Кларк(😎)?"
    pool.reactions = "🥺😎"
    pool.title = "Тестовый опрос"
    pool.start_date = datetime.datetime.utcnow()
    pool.end_date = datetime.datetime.utcnow() + datetime.timedelta(minutes=1)
    pool.pool_channel_id = 1180512989590327296
    pool.status = PoolStatus.PUBLISHED

    user.pools.append(pool)
    user.update()  # сохраняем pool в бд и связываем его с user


    channel = bot.get_channel(pool.pool_channel_id)
    message = await channel.send(content=pool.publish_format())
    pool.pool_message_id = message.id
    channels_messages.append(f"{pool.pool_channel_id}_{pool.pool_message_id}")
    for reaction in pool.reactions:
        await message.add_reaction(reaction)

    user.update(True)


async def send_pool_to_channel(pool_id):
    pool = Pool.get_pool(pool_id)
    embed = Embed(title=pool.title, description=pool.text, color=Colour(2))
    message = await bot.get_channel(pool.pool_channel_id).send(embed=embed)
    for reaction in pool.reactions:
        await message.add_reaction(reaction)


async def get_pool_results(pool_id):
    pool = Pool.get_pool(pool_id)
    admin_channel = await bot.fetch_channel(pool.edit_channel_id)
    await admin_channel.send("Опрос завершился! Вот результаты!")
    pool_channel = await bot.fetch_channel(pool.pool_channel_id)
    message = await pool_channel.fetch_message(pool.pool_message_id)
    result = pool.reactions
    await admin_channel.send()


@new_pool.error
@exit_.error
@title.error
@text.error
@start_date.error
@end_date.error
@where.error
@pools.error
@run.error
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
        utils.convert_datetime_to_formatted_timestamp(pool.start_date) if pool.start_date else "*сейчас*",
        utils.convert_datetime_to_formatted_timestamp(pool.end_date) if pool.end_date else no,
        pool.reactions if pool.reactions else no,
        f"<#{pool.pool_channel_id}>" if pool.pool_channel_id else no,
    )


if __name__ == '__main__':
    bot.run(BOT_TOKEN, log_level=logging.INFO, log_handler=handler, root_logger=True)
