from models import User, get_password_hash,SessionLocal

db = SessionLocal()

admin_user = User(
    username="admin",
    hashed_password=get_password_hash("StrongAdminPass123"),
    is_admin=True   # or role="admin"
)
db.add(admin_user)
db.commit()
print("✅ Admin user created successfully")