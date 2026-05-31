import os
import sys

from sqlalchemy.orm import Session

sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models.user import User


if len(sys.argv) < 2:
    print("Cach dung: python set_admin.py <username>")
    print("Vi du: python set_admin.py quanganh")
    sys.exit(1)

target_username = sys.argv[1]
db: Session = SessionLocal()

try:
    user = db.query(User).filter(User.username == target_username).first()

    if user:
        user.role = "admin"
        db.commit()
        print("--- THANH CONG ---")
        print(f"User '{user.username}' da duoc nang cap len ADMIN.")
    else:
        print("--- THAT BAI ---")
        print(f"Khong tim thay tai khoan nao ten la '{target_username}' trong database.")
finally:
    db.close()
