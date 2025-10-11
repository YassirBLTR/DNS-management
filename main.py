from fastapi import FastAPI, Depends, HTTPException, Request, Form, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.sessions import SessionMiddleware

# Import shared components
from models import (
    get_db, User, Account, DynuAPI, UserCreate, AccountCreate, DomainOperation,
    verify_password, get_password_hash, create_access_token,
    SECRET_KEY, ALGORITHM
)
from config import settings

security = HTTPBearer()

app = FastAPI(title="DNS Management System", description="Manage domains with Dynu.com")

# Add session middleware for flash messages
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# Include routes
from routes import router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level=settings.LOG_LEVEL.lower())
