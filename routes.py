from fastapi import APIRouter, Depends, HTTPException, Request, Form, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import (
    get_db, User, Account, DynuAPI, UserCreate, AccountCreate, DomainOperation,
    verify_password, get_password_hash, create_access_token, get_current_user_from_cookie
)
from subdomain_generator import SubdomainGenerator
from datetime import timedelta
from typing import List, Optional
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Authentication routes
@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Username already exists"
        })
    
    # Create new user
    hashed_password = get_password_hash(password)
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

# Dashboard routes
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "accounts": accounts
    })

# Account management routes
@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "user": current_user,
        "accounts": accounts
    })

@router.post("/accounts")
async def create_account(
    request: Request,
    name: str = Form(...),
    api_key: str = Form(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = Account(name=name, api_key=api_key, user_id=current_user.id)
    db.add(account)
    db.commit()
    return RedirectResponse(url="/accounts", status_code=status.HTTP_302_FOUND)

@router.get("/accounts/{account_id}/delete")
async def delete_account(account_id: int, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if account:
        db.delete(account)
        db.commit()
    return RedirectResponse(url="/accounts", status_code=status.HTTP_302_FOUND)

# Domain management routes
@router.get("/domains/{account_id}", response_class=HTMLResponse)
async def domains_page(
    request: Request,
    account_id: int,
    page: int = 1,
    per_page: str = "10",
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Ensure page is at least 1
    page = max(1, page)
    
    # Handle "all" option for per_page
    if per_page == "all":
        per_page_int = 999999  # Large number to get all domains
        show_all = True
    else:
        try:
            per_page_int = int(per_page)
            per_page_int = max(1, min(50, per_page_int))  # Limit per_page between 1 and 50
            show_all = False
        except ValueError:
            per_page_int = 10  # Default fallback
            per_page = "10"
            show_all = False
    
    dynu_api = DynuAPI(account.api_key)
    domains_data = await dynu_api.get_domains(page=page, per_page=per_page_int, search=search)
    
    # Initialize subdomain generator
    subdomain_gen = SubdomainGenerator()
    main_domains = subdomain_gen.get_main_domains()
    suggestions = subdomain_gen.get_random_suggestions(5)
    
    print(f"DEBUG: main_domains count: {len(main_domains)}")
    print(f"DEBUG: suggestions count: {len(suggestions)}")
    
    return templates.TemplateResponse("domains.html", {
        "request": request,
        "user": current_user,
        "account": account,
        "domains": domains_data.get("domains", []),
        "pagination": domains_data.get("pagination", {}),
        "search": search or "",
        "per_page": per_page,
        "show_all": show_all,
        "main_domains": main_domains,
        "suggestions": suggestions
    })

@router.post("/domains/{account_id}/add")
async def add_domains(
    account_id: int,
    domains: str = Form(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    dynu_api = DynuAPI(account.api_key)
    domain_list = [domain.strip() for domain in domains.split('\n') if domain.strip()]
    
    for domain in domain_list:
        await dynu_api.add_domain(domain)
    
    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/delete")
async def delete_domains(
    account_id: int,
    domain_ids: List[int] = Form(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    dynu_api = DynuAPI(account.api_key)
    
    for domain_id in domain_ids:
        await dynu_api.delete_domain(domain_id)
    
    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/generate")
async def generate_subdomains(
    account_id: int,
    main_domain: str = Form(...),
    count: int = Form(10),
    use_prefix: bool = Form(False),
    use_suffix: bool = Form(False),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        subdomain_gen = SubdomainGenerator()
        generated_subdomains = subdomain_gen.generate_subdomains(
            main_domain=main_domain,
            count=min(count, 50),  # Limit to 50 subdomains max
            use_prefix=use_prefix,
            use_suffix=use_suffix
        )
        
        dynu_api = DynuAPI(account.api_key)
        success_count = 0
        
        for subdomain in generated_subdomains:
            if await dynu_api.add_domain(subdomain):
                success_count += 1
        
        # You might want to add flash messages here for user feedback
        print(f"Successfully added {success_count} out of {len(generated_subdomains)} subdomains")
        
    except ValueError as e:
        print(f"Error generating subdomains: {e}")
        # Handle error - you might want to add flash messages
    
    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/add-custom")
async def add_custom_subdomain(
    account_id: int,
    subdomain_name: str = Form(...),
    main_domain: str = Form(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        subdomain_gen = SubdomainGenerator()
        full_subdomain = subdomain_gen.create_custom_subdomain(subdomain_name, main_domain)
        
        dynu_api = DynuAPI(account.api_key)
        success = await dynu_api.add_domain(full_subdomain)
        
        if success:
            print(f"Successfully added custom subdomain: {full_subdomain}")
        else:
            print(f"Failed to add custom subdomain: {full_subdomain}")
            
    except ValueError as e:
        print(f"Error creating custom subdomain: {e}")
        # Handle error - you might want to add flash messages
    
    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)
