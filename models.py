from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Mapped, mapped_column
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel
from fastapi import HTTPException, status, Cookie, Depends
import httpx

# Import configuration
from config import settings

# Database setup
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    api_key = Column(String)
    user_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str

class AccountCreate(BaseModel):
    name: str
    api_key: str

class DomainOperation(BaseModel):
    domains: List[str]

class DNSRecordCreate(BaseModel):
    record_type: str  # A, TXT, MX, SPF
    name: str  # Node name/hostname
    value: str  # IP address, text value, etc.
    priority: Optional[int] = 10  # For MX records
    ttl: Optional[int] = 120  # Time to live (2 minutes)

class BulkDNSRecordCreate(BaseModel):
    domain_ids: List[int]  # List of domain IDs to add records to
    records: List[DNSRecordCreate]  # List of DNS records to add

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user_from_cookie_impl(access_token: Optional[str], db: Session):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Remove 'Bearer ' prefix if present
    if access_token.startswith('Bearer '):
        access_token = access_token[7:]
    
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

# FastAPI dependency function
def get_current_user_from_cookie(access_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    return get_current_user_from_cookie_impl(access_token, db)

# Dynu API integration
class DynuAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.dynu.com/v2"
        self.headers = {
            "API-Key": api_key,
            "Content-Type": "application/json"
        }
    
    async def get_domains(self, page: int = 1, per_page: int = 10, search: str = None):
        async with httpx.AsyncClient() as client:
            # First, get all domains (Dynu API might not support pagination)
            response = await client.get(f"{self.base_url}/dns", headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                # Handle different response formats
                if isinstance(data, dict) and "domains" in data:
                    all_domains = data["domains"]
                elif isinstance(data, list):
                    all_domains = data
                else:
                    all_domains = []
                
                
                # Client-side search filtering
                if search and all_domains:
                    filtered_domains = []
                    search_lower = search.lower()
                    for domain in all_domains:
                        domain_name = domain.get("name", "") if isinstance(domain, dict) else str(domain)
                        if search_lower in domain_name.lower():
                            filtered_domains.append(domain)
                    all_domains = filtered_domains
                
                # Calculate pagination
                total = len(all_domains)
                total_pages = (total + per_page - 1) // per_page if total > 0 else 1
                
                # Client-side pagination
                start = (page - 1) * per_page
                end = start + per_page
                paginated_domains = all_domains[start:end]
                
                return {
                    "domains": paginated_domains,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "pages": total_pages
                    }
                }
            
            return {"domains": [], "pagination": {"page": 1, "per_page": per_page, "total": 0, "pages": 0}}
    
    async def add_domain(self, domain_name: str):
        async with httpx.AsyncClient() as client:
            data = {"name": domain_name}
            response = await client.post(f"{self.base_url}/dns", headers=self.headers, json=data)
            return response.status_code == 200
    
    async def delete_domain(self, domain_id: int):
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/dns/{domain_id}", headers=self.headers)
            return response.status_code == 200
    
    async def get_domain_records(self, domain_id: int):
        """Get all DNS records for a specific domain"""
        async with httpx.AsyncClient() as client:
            try:
                print(f"DEBUG: Fetching DNS records for domain ID: {domain_id}")
                response = await client.get(f"{self.base_url}/dns/{domain_id}/record", headers=self.headers)
                print(f"DEBUG: Response status code: {response.status_code}")
                print(f"DEBUG: Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"DEBUG: Response data type: {type(data)}")
                        print(f"DEBUG: Response data: {data}")
                        
                        if isinstance(data, dict):
                            records = data.get("dnsRecords", [])
                            print(f"DEBUG: Found {len(records)} records in 'dnsRecords' key")
                            return records
                        elif isinstance(data, list):
                            print(f"DEBUG: Response is a list with {len(data)} records")
                            return data
                        else:
                            print(f"DEBUG: Unexpected data format: {data}")
                            return []
                    except Exception as json_error:
                        print(f"DEBUG: JSON parsing error: {json_error}")
                        print(f"DEBUG: Raw response text: {response.text}")
                        return []
                else:
                    print(f"DEBUG: Non-200 status code: {response.status_code}")
                    print(f"DEBUG: Response text: {response.text}")
                    return []
                    
            except Exception as e:
                print(f"DEBUG: Exception in get_domain_records: {type(e).__name__}: {e}")
                import traceback
                print(f"DEBUG: Traceback: {traceback.format_exc()}")
                return []
    
    async def add_dns_record(self, domain_id: int, record_type: str, name: str, value: str, priority: int = 10, ttl: int = 120, state: bool = True):
        """Add a DNS record to a domain"""
        async with httpx.AsyncClient() as client:
            # Normalize node name based on record type and Dynu API requirements
            normalized_name = self._normalize_node_name(name, record_type.upper())
            
            record_data = {
                "recordType": record_type.upper(),
                "nodeName": normalized_name,
                "ttl": ttl,
                "state": state
            }
            
            # Handle different record types
            if record_type.upper() == "A":
                record_data["ipv4Address"] = value
            elif record_type.upper() == "TXT":
                record_data["textData"] = value
            elif record_type.upper() == "MX":
                record_data["host"] = value
                record_data["priority"] = priority
            elif record_type.upper() == "SPF":
                record_data["textData"] = value
                record_data["recordType"] = "TXT"  # SPF records are stored as TXT records
            
            print(f"DEBUG: Adding {record_type} record with data: {record_data}")
            response = await client.post(f"{self.base_url}/dns/{domain_id}/record", headers=self.headers, json=record_data)
            
            if response.status_code != 200:
                print(f"DEBUG: Failed to add record. Status: {response.status_code}, Response: {response.text}")
            
            return response.status_code == 200, response.json() if response.status_code != 200 else None
    
    def _normalize_node_name(self, name: str, record_type: str) -> str:
        """Normalize node name based on Dynu API requirements for different record types"""
        # Handle root domain cases
        if name in ["@", "", "root"]:
            # For root domain, different record types may need different formats
            if record_type in ["A", "MX"]:
                return ""  # Empty string for root domain A and MX records
            elif record_type in ["TXT", "SPF"]:
                return ""  # Empty string for root domain TXT records
            else:
                return ""
        
        # For subdomains, ensure proper format
        name = name.strip()
        
        # Remove any trailing dots
        if name.endswith('.'):
            name = name[:-1]
        
        # Validate node name format
        if record_type == "A":
            # A records: allow alphanumeric, hyphens, but not starting/ending with hyphen
            if name and not name.replace('-', '').replace('_', '').isalnum():
                print(f"DEBUG: Invalid A record node name format: '{name}', using empty string")
                return ""
        elif record_type == "MX":
            # MX records: similar validation
            if name and not name.replace('-', '').replace('_', '').isalnum():
                print(f"DEBUG: Invalid MX record node name format: '{name}', using empty string")
                return ""
        
        return name
    
    async def delete_dns_record(self, domain_id: int, record_id: int):
        """Delete a DNS record"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/dns/{domain_id}/record/{record_id}", headers=self.headers)
            return response.status_code == 200