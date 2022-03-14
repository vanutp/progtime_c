import sqlite3
from enum import Enum, auto

import jose.exceptions
import uvicorn
from fastapi import FastAPI, Body, Depends, Header
from fastapi.exceptions import HTTPException
from jose import jwt

import config

app = FastAPI()


class DBAction(Enum):
    fetchone = auto()
    fetchall = auto()
    commit = auto()


def db_action(sql: str, args: tuple, action: DBAction):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()

    cursor.execute(sql, args)
    if action == DBAction.fetchone:
        result = cursor.fetchone()
    elif action == DBAction.fetchall:
        result = cursor.fetchall()
    elif action == DBAction.commit:
        conn.commit()
        result = None

    cursor.close()
    conn.close()

    return result


@app.on_event('startup')
def create_db():
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()

    cursor.execute('''
        create table if not exists users (
            id integer primary key,
            username varchar not null,
            password varchar not null
        );
    ''')

    cursor.close()
    conn.close()


def get_user(authorization: str = Header(...)):
    try:
        user_id = jwt.decode(authorization, config.SECRET, algorithms=['HS256'])['id']
    except jose.exceptions.JWTError:
        raise HTTPException(
            status_code=400,
            detail='Неверный токен'
        )

    user = db_action(
        '''
            select * from users where id = ?
        ''',
        (user_id,),
        DBAction.fetchone,
    )
    return user


@app.get('/')
def index(user: list = Depends(get_user)):
    return user[1]


@app.post('/login')
def login(username: str = Body(...), password: str = Body(...)):
    user = db_action(
        '''
            select * from users where username = ? and password = ?
        ''',
        (username, password),
        DBAction.fetchone,
    )
    if not user:
        raise HTTPException(
            status_code=404,
            detail='Пользователь не найден'
        )

    token = jwt.encode({'id': user[0]}, config.SECRET, algorithm='HS256')
    return {
        'token': token
    }


@app.post('/register')
def register(username: str = Body(...), password: str = Body(...)):
    user = db_action(
        '''
            select * from users where username = ?
        ''',
        (username,),
        DBAction.fetchone,
    )
    if user:
        raise HTTPException(
            status_code=400,
            detail='Пользователь уже существует'
        )

    return db_action(
        '''
            insert into users (username, password) values (?, ?)
        ''',
        (username, password),
        DBAction.commit,
    )


if __name__ == '__main__':
    uvicorn.run('main:app', reload=True)
