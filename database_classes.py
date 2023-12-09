import datetime
import json
import logging
import os.path
from copy import copy
from enum import Enum as PythonEnum
from typing import List

import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, Integer, String, \
    DateTime, ForeignKey, Numeric, select, PickleType, TypeDecorator, Date, ARRAY, Time, Boolean, TEXT, Tuple, Enum
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import declarative_base

from sqlalchemy.orm import sessionmaker, relationship, Session, Mapped, mapped_column, make_transient

os.makedirs("data", exist_ok=True)
db_path = os.path.join("data", "db.db")

# Создание экземпляра Engine
engine = create_engine(f"sqlite:///{db_path}", echo=False)

# Создание экземпляра declarative_base
Base = declarative_base()
Session = sessionmaker(bind=engine)


class TupleString(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            return ','.join(str(x) for x in value)

    def process_result_value(self, value, dialect):
        if value is not None:
            return tuple(map(int, value.split(',')))

class ListString(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if value:
            return ','.join(str(x) for x in value)
        else:
            return ""

    def process_result_value(self, value, dialect):
        if value:
            return list(map(int, value.split(',')))
        else:
            return []


class DictString(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            logging.info(f"Сохраняю данные ||{value}|| в базе данных")
            return json.dumps(value, ensure_ascii=False)
        else:
            return "{}"

    def process_result_value(self, value, dialect):
        if value is not None:
            logging.info(f"Получаю данные ||{value}|| из базы данных")
            return json.loads(value)
        else:
            return {}

class PoolStatus(PythonEnum):
    COMPLETED = "завершённый"
    NOT_STARTED = "не начатый"
    PUBLISHED = "сейчас в публикации"


class Pool(Base):
    __tablename__ = "poll"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(ForeignKey("users.id"))

    title = mapped_column(String)
    text = mapped_column(String)
    start_date = mapped_column(DateTime)
    end_date = mapped_column(DateTime)
    reactions = mapped_column(String)
    vote_users = mapped_column(DictString, default={})
    pool_channel_id = mapped_column(Integer)
    pool_message_id = mapped_column(Integer)

    edit_channel_id = mapped_column(Integer)
    edit_message_id = mapped_column(Integer)

    status = mapped_column(Enum(PoolStatus))

    # def get_status(self):
    #     now = datetime.datetime.utcnow()
    #     if now >= self.end_date:
    #         return PoolStatus.COMPLETED
    #     elif now < self.start_date:
    #         return PoolStatus.NOT_STARTED
    #     return

    @staticmethod
    def get_pool(pool_id):
        session = Session()
        pool = session.get(Pool, pool_id)
        pool.session = session
        return pool

    def update(self, need_close_session=False):
        if hasattr(self, "session"):
            self.session.commit()
            if need_close_session:
                self.session.close()

    def close_session(self):
        if hasattr(self, "session"):
            self.session.close()

    def publish_format(self):
        return f"{self.text}\n\nАвтор: <@{self.user_id}>"

    @staticmethod
    def get_all():
        session = Session()
        stmt = select(Pool)
        pools = session.scalars(stmt).fetchall()
        session.close()
        return pools
    # def __del__(self, *args):
    #     print("Вызван del")
    # вызывает "SAWarning: __del__() method on class <class 'database_classes.Pool'>
    # will cause unreachable cycles and memory leaks, as SQLAlchemy instrumentation often
    # creates reference cycles.  Please remove this method."

class User(Base):
    # Определяем имя таблицы
    __tablename__ = 'users'

    # Определяем столбцы таблицы
    id = mapped_column(Integer, primary_key=True)
    registration_date = mapped_column(DateTime, default=datetime.datetime.utcnow())
    name = mapped_column(String)
    global_name = mapped_column(String)
    pools: Mapped[List["Pool"]] = relationship(cascade="all, delete-orphan")
    editing_pool_id = mapped_column(Integer)

    def get_pools(self):
        return self.pools

    def get_editing_pool(self):
        return Pool.get_pool(self.editing_pool_id)

    def get_pool(self, channel_id, message_id):
        for pool in self.pools:
            if pool.pool_message_id == message_id and pool.pool_channel_id == channel_id:
                return Pool.get_pool(pool.id)



    @staticmethod
    def add_new_user(id, name, global_name):
        session = Session()
        user = User(id=id, name=name, global_name=global_name)
        session.add(user)
        session.commit()
        session.close()

    @staticmethod
    def get_user(user_id: int):
        session = Session()
        user = session.get(User, user_id)
        if user is None:
            return None
        user.session = session
        return user

    @staticmethod
    def get_all_users():
        session = Session()
        stmt = select(User)
        users = session.scalars(stmt).fetchall()
        session.close()
        return users


    def update(self, need_close_session=False):
        if hasattr(self, "session"):
            self.session.commit()
            if need_close_session:
                self.session.close()

    def close_session(self):
        if hasattr(self, "session"):
            self.session.close()


Base.metadata.create_all(engine)
