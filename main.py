import asyncio
import json
from typing import Annotated
from datetime import datetime
from authlib.integrations.starlette_client import OAuth, OAuthError
from contextlib import asynccontextmanager
from starlette.config import Config
from fastapi import Depends, FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import BackgroundTasks
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware.sessions import SessionMiddleware
# from fastapi.security import OAuth2AuthorizationCodeBearer
from starlette.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, Column, Integer, String, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func


class Settings(BaseSettings):
    client_id: str
    client_secret: str
    session_secret: str
    database_url: str
    voucher: str
    total_tickets: int
    # File '.env' will be read
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()


templates = Jinja2Templates(directory="templates")
config = Config('.oauth_env')  # read config from .env file
oauth = OAuth(config)

# print(f"client_id: {config.get('client_id', None)}")
oauth.register(
    name='cbase',
    server_metadata_url='https://c-base.org/oauth/.well-known/openid-configuration/',
    client_id=settings.client_id,
    client_secret=settings.client_secret,
    client_kwargs={
        'scope': 'membership openid',
    }
)

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Load the ML model
#     runner = MQTTRunner()
#     loop = asyncio.get_event_loop()
#     loop.create_task(runner.run_main())
#     yield
#     # Clean up the ML models and release the resources
#     runner.stop()

#app = FastAPI(lifespan=lifespan)
app = FastAPI()

# oauth2_scheme = OAuth2AuthorizationCodeBearer(scopes={"openid": "openid"}, authorizationUrl="https://c-base.org/oauth/authorize/", tokenUrl="https://c-base.org/oauth/token/")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String, unique=True, index=True)
    num_bought = Column(String)
    num_tickets = Column(Integer)

# create sql tables
Base.metadata.create_all(engine)


# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get('/')
async def homepage(request: Request):
    user = request.session.get('user')
    if user:
        with Session(engine) as db:
            users = list(db.query(User).filter(User.num_tickets != 0))
            sum_tickets = db.query(func.sum(User.num_tickets).label("total_score"))[0][0]
            if sum_tickets is None:
                sum_tickets = 0
            tickets_left = settings.total_tickets - sum_tickets

            sum_bought = db.query(func.sum(User.num_bought).label("total_score"))[0][0]
            if sum_tickets is None:
                sum_bought = 0

            my_val = 0
            my_bought = 0
            query = list(db.query(User).filter(User.nickname == user['nickname']))
            if len(query) > 0:
               my_val = query[0].num_tickets
               my_bought = query[0].num_bought
            
            context = {
                "data": json.dumps(user),
                "user": user,
                "users": users,
                "request": request,
                "sum_tickets": sum_tickets,
                "sum_bought": sum_bought,
                "tickets_left": tickets_left,
                "total_tickets": settings.total_tickets,
                "my_val": my_val,
                "my_bought": my_bought,
            }
            return templates.TemplateResponse("index.html", context)
    return templates.TemplateResponse("index_login_required.html", {"request": request})


@app.post('/giveme/')
async def update_ticket(request: Request, 
                        num_tickets: Annotated[int, Form()], 
                        agree1: Annotated[bool, Form()]=False,
                        agree2: Annotated[bool, Form()]=False):
    user = request.session.get('user')
    if user:
        if agree1 is False or agree2 is False:
            return templates.TemplateResponse("givemeno.html", {"request": request, "user": user})

        with Session(engine) as db:
            query = list(db.query(User).filter(User.nickname == user['nickname']))
            if len(query) == 0:
                new_entry = User(
                    nickname=user['nickname'],
                    num_tickets=num_tickets,
                )
                db.add(new_entry)
                db.commit()
            else:
                my_nick = query[0]
                my_nick.num_tickets = num_tickets
                db.add(my_nick)
                db.commit()
                pass
            return templates.TemplateResponse("giveme.html", {"request": request, "user": user, "voucher": settings.voucher})

    return templates.TemplateResponse("index_login_required.html", {"request": request})


@app.post('/bought/')
async def update_ticket(request: Request, 
                        num_bought: Annotated[int, Form()]):
    user = request.session.get('user')
    if user:
        with Session(engine) as db:
            query = list(db.query(User).filter(User.nickname == user['nickname']))
            if len(query) == 0:
                new_entry = User(
                    nickname=user['nickname'],
                    num_tickets=0,
                    num_bought=num_bought,
                )
                db.add(new_entry)
                db.commit()
            else:
                my_nick = query[0]
                my_nick.num_bought = num_bought
                db.add(my_nick)
                db.commit()
                pass
            return templates.TemplateResponse("bought.html", {"request": request, "user": user, "voucher": settings.voucher})

    return templates.TemplateResponse("index_login_required.html", {"request": request})


@app.get('/logout')
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/')


@app.route('/login')
async def login(request: Request):
    user = request.session.get('user')
    if user:
        return RedirectResponse(url='/')
    # absolute url for callback
    # we will define it below
    redirect_uri = request.url_for('auth')
    print(redirect_uri)
    return await oauth.cbase.authorize_redirect(request, redirect_uri)


@app.route('/auth')
async def auth(request: Request):
    token = await oauth.cbase.authorize_access_token(request)
    user = token.get('userinfo')
    if user:
        request.session['user'] = dict(user)
    return RedirectResponse(url='/')



# @app.get("/items/")
#async def read_items(token: Annotated[str, Depends(oauth)]):
#    return {"token": token}
