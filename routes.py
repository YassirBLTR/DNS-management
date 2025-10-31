from fastapi import APIRouter, Depends, HTTPException, Request, Form, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import (
    get_db, User, Account, DynuAPI, UserCreate, AccountCreate, DomainOperation, DNSRecordCreate, BulkDNSRecordCreate,
    verify_password, get_password_hash, create_access_token, get_current_user_from_cookie
)
from subdomain_generator import SubdomainGenerator
from datetime import timedelta
from typing import List, Optional
import json

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Flash message utilities
def set_flash(request: Request, message: str, category: str = "info"):
    """Set a flash message in the session"""
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})

def get_flashed_messages(request: Request):
    """Get and clear flash messages from the session"""
    messages = request.session.pop("flash_messages", [])
    return messages

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
async def disabled_register():
    raise HTTPException(status_code=403, detail="Registration disabled.")

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response
@router.get("/admin/create_user", response_class=HTMLResponse)
async def show_create_user_form(request: Request, current_user = Depends(get_current_user_from_cookie)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access forbidden")
    
    return templates.TemplateResponse("admin_create_user.html", {"request": request})
@router.post("/admin/create_user")
async def create_user_admin(
    username: str, 
    password: str, 
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user_from_cookie)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Access forbidden")

    hashed_password = get_password_hash(password)
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": f"User '{username}' created successfully."}
# Dashboard routes
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": current_user,
        "accounts": accounts,
        "messages": get_flashed_messages(request)
    })

# Account management routes
@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, current_user: User = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "user": current_user,
        "accounts": accounts,
        "messages": get_flashed_messages(request)
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
            per_page_int = max(1, per_page_int)  # Limit per_page between 1 and 100
            show_all = False
        except ValueError:
            per_page_int = 10  # Default fallback
            per_page = "10"
            show_all = False
    
    dynu_api = DynuAPI(account.api_key)
    domains_data = await dynu_api.get_domains(page=page, per_page=per_page_int, search=search)
    print(f"DEBUG: per_page param received = {per_page}")
    print(f"DEBUG: per_page_int after parsing = {per_page_int}")
    # Debug: Print domain data to see the structure
    print(f"DEBUG: Domains data structure: {domains_data}")
    for i, domain in enumerate(domains_data.get("domains", [])[:3]):  # Print first 3 domains
        print(f"DEBUG: Domain {i}: {domain}")
    
    # Initialize subdomain generator
    subdomain_gen = SubdomainGenerator()
    main_domains = subdomain_gen.get_main_domains()
    suggestions = subdomain_gen.get_random_suggestions(5)
    
    print(f"DEBUG: main_domains count: {len(main_domains)}")
    print(f"DEBUG: suggestions count: {len(suggestions)}")
    print(f"DEBUG: per_page param received = {per_page}")
    print(f"DEBUG: per_page_int after parsing = {per_page_int}")
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
        "suggestions": suggestions,
        "bulk_record_errors": request.session.pop("bulk_record_errors", []),
        "messages": get_flashed_messages(request)
    })

@router.post("/domains/{account_id}/add")
async def add_domains(
    request: Request,
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

    success_count = 0
    for domain in domain_list:
        if await dynu_api.add_domain(domain):
            success_count += 1

    if success_count > 0:
        set_flash(request, f"Successfully added {success_count} domain(s)", "success")
    if success_count < len(domain_list):
        set_flash(request, f"Failed to add {len(domain_list) - success_count} domain(s)", "error")

    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/delete")
async def delete_domains(
    request: Request,
    account_id: int,
    domain_ids: List[int] = Form(...),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    dynu_api = DynuAPI(account.api_key)

    success_count = 0
    for domain_id in domain_ids:
        if await dynu_api.delete_domain(domain_id):
            success_count += 1

    if success_count > 0:
        set_flash(request, f"Successfully deleted {success_count} domain(s)", "success")
    if success_count < len(domain_ids):
        set_flash(request, f"Failed to delete {len(domain_ids) - success_count} domain(s)", "error")

    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/generate")
async def generate_subdomains(
    request: Request,
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
            count=min(count, 50),
            use_prefix=use_prefix,
            use_suffix=use_suffix
        )

        dynu_api = DynuAPI(account.api_key)
        success_count = 0

        for subdomain in generated_subdomains:
            if await dynu_api.add_domain(subdomain):
                success_count += 1

        if success_count > 0:
            set_flash(request, f"Successfully added {success_count} out of {len(generated_subdomains)} subdomains", "success")
        if success_count < len(generated_subdomains):
            set_flash(request, f"Failed to add {len(generated_subdomains) - success_count} subdomains", "error")

    except ValueError as e:
        set_flash(request, f"Error: {str(e)}", "error")

    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/add-custom")
async def add_custom_subdomain(
    request: Request,
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
            set_flash(request, f"Successfully added subdomain: {full_subdomain}", "success")
        else:
            set_flash(request, f"Failed to add subdomain: {full_subdomain}", "error")

    except ValueError as e:
        set_flash(request, f"Error: {str(e)}", "error")

    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)

# Debug route to find domain ID by name
@router.get("/debug/find-domain/{account_id}")
async def find_domain_by_name(
    account_id: int,
    domain_name: str,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    dynu_api = DynuAPI(account.api_key)
    domains_data = await dynu_api.get_domains()
    
    for domain in domains_data.get("domains", []):
        if domain.get("name") == domain_name:
            return {"found": True, "domain": domain}
    
    return {"found": False, "searched_for": domain_name, "available_domains": [d.get("name") for d in domains_data.get("domains", [])]}

# DNS Record management routes
@router.get("/domains/{account_id}/{domain_id}/records", response_class=HTMLResponse)
async def domain_records_page(
    request: Request,
    account_id: int,
    domain_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    try:
        print(f"DEBUG: Accessing records for account_id={account_id}, domain_id={domain_id}")
        
        account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
        if not account:
            print(f"DEBUG: Account not found for account_id={account_id}, user_id={current_user.id}")
            raise HTTPException(status_code=404, detail="Account not found")
        
        print(f"DEBUG: Found account: {account.name}")
        dynu_api = DynuAPI(account.api_key)
        
        # Get domain details - fetch ALL domains without pagination limits
        print(f"DEBUG: Fetching all domains list to find domain_id={domain_id}")
        domains_data = await dynu_api.get_domains(page=1, per_page=1000)  # Set high per_page to get all domains
        ids = [d["id"] for d in domains_data["domains"]]
        print(f"DEBUG: Got domains ids: {ids}")
        
        domain = None
        for d in domains_data.get("domains", []):
            print(f"DEBUG: Checking domain: {d}")
            if d.get("id") == domain_id:
                domain = d
                break
        
        if not domain:
            print(f"DEBUG: Domain not found with ID {domain_id}")
            print(f"DEBUG: Available domains: {[d.get('id') for d in domains_data.get('domains', [])]}")
            raise HTTPException(status_code=404, detail="Domain not found")
        
        print(f"DEBUG: Found domain: {domain}")
        
        # Get DNS records for the domain
        print(f"DEBUG: Fetching DNS records for domain {domain.get('name')} (ID: {domain_id})")
        records = await dynu_api.get_domain_records(domain_id)
        print(f"DEBUG: Retrieved {len(records)} records")
        
        return templates.TemplateResponse("domain_records.html", {
            "request": request,
            "user": current_user,
            "account": account,
            "domain": domain,
            "records": records,
            "domain_id": domain_id,
            "account_id": account_id,
            "messages": get_flashed_messages(request)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Unexpected error in domain_records_page: {type(e).__name__}: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching DNS records: {str(e)}")

@router.post("/domains/{account_id}/{domain_id}/records/add")
async def add_dns_record(
    request: Request,
    account_id: int,
    domain_id: int,
    record_type: str = Form(...),
    name: str = Form(...),
    value: str = Form(...),
    priority: int = Form(10),
    ttl: int = Form(120),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    dynu_api = DynuAPI(account.api_key)
    success, error = await dynu_api.add_dns_record(domain_id, record_type, name, value, priority, ttl)

    if success:
        set_flash(request, f"Successfully added {record_type} record", "success")
    else:
        set_flash(request, f"Failed to add DNS record: {error}", "error")

    return RedirectResponse(url=f"/domains/{account_id}/{domain_id}/records", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/{domain_id}/records/{record_id}/delete")
async def delete_dns_record(
    request: Request,
    account_id: int,
    domain_id: int,
    record_id: int,
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    dynu_api = DynuAPI(account.api_key)
    success = await dynu_api.delete_dns_record(domain_id, record_id)

    if success:
        set_flash(request, "DNS record deleted successfully", "success")
    else:
        set_flash(request, f"Failed to delete DNS record", "error")

    return RedirectResponse(url=f"/domains/{account_id}/{domain_id}/records", status_code=status.HTTP_302_FOUND)

@router.post("/domains/{account_id}/bulk-add-records")
async def bulk_add_dns_records(
    request: Request,
    account_id: int,
    domain_ids: List[int] = Form(...),
    record_type: str = Form(...),
    name: str = Form(...),
    value: str = Form(...),
    priority: int = Form(10),
    ttl: int = Form(3600),
    state: bool = Form(True),
    current_user: User = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db)
):
    """Add DNS records to multiple domains at once"""
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    dynu_api = DynuAPI(account.api_key)
    success_count = 0
    error_count = 0
    errors = []

    # Get domain names for logging
    domains_data = await dynu_api.get_domains()
    domain_names = {d.get("id"): d.get("name") for d in domains_data.get("domains", [])}

    for domain_id in domain_ids:
        try:
            success, error = await dynu_api.add_dns_record(domain_id, record_type, name, value, priority, ttl, state=state)
            if success:
                success_count += 1
                print(f"Successfully added {record_type} record to domain {domain_names.get(domain_id, domain_id)}")
            else:
                error_count += 1
                domain_name = domain_names.get(domain_id, f"ID:{domain_id}")
                error_msg = f"Failed to add record to {domain_name}: {error}"
                errors.append(error_msg)
                print(error_msg)
        except Exception as e:
            error_count += 1
            domain_name = domain_names.get(domain_id, f"ID:{domain_id}")
            error_msg = f"Exception adding record to {domain_name}: {str(e)}"
            errors.append(error_msg)
            print(error_msg)

    if success_count > 0:
        set_flash(request, f"Successfully added {record_type} records to {success_count} domain(s)", "success")
    if error_count > 0:
        set_flash(request, f"Failed to add records to {error_count} domain(s)", "error")
        request.session["bulk_record_errors"] = errors

    return RedirectResponse(url=f"/domains/{account_id}", status_code=status.HTTP_302_FOUND)