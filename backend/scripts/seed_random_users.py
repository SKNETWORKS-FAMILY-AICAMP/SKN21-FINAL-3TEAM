import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
import sys
import os

# Add backend directory to path so we can import app modules if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.user import User
from app.core.security import hash_password

# Using the SSH tunnel connection string since RDS blocks direct external access
DATABASE_URL = "postgresql+asyncpg://postgre:dudu123!@localhost:5433/workflow_agent?ssl=require"

TEAMS = ['개발', 'QA기획', 'UI/UX', '영업', '마케팅', 'CS', 'HR', '경영']

# Since we don't have direct access to app modules easily if we run standalone via python, 
# we redefine hash_password if it fails, but we've appended sys.path so it should work.

async def seed_random_users():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    print("Fetching random users from API...")
    async with httpx.AsyncClient() as client:
        response = await client.get("https://randomuser.me/api/?results=40")
        if response.status_code != 200:
            print("Failed to fetch random users")
            return
        users_data = response.json()["results"]
        
    print(f"Fetched {len(users_data)} users. Distributing into teams and saving to DB...")
    
    async with async_session() as session:
        # Check existing users first to avoid filling up too much if already seeded
        result = await session.execute(select(User))
        existing_users = result.scalars().all()
        
        # We will also fill in the blanks for existing users if they want but for now just seed new users
        # 40 users divided by 8 teams = 5 per team
        
        new_users = []
        for idx, user_dict in enumerate(users_data):
            team_assigned = TEAMS[idx % len(TEAMS)]
            
            fullname = f"{user_dict['name']['first']} {user_dict['name']['last']}"
            email = user_dict['email']
            phone = user_dict['phone']
            address = f"{user_dict['location']['city']}, {user_dict['location']['country']}"
            avatar = user_dict['picture']['large']
            
            # Create dummy password
            hp = hash_password("password123!")
            
            # Roles based on team as a simple placeholder
            role_map = {
                '개발': 'Developer',
                'QA기획': 'QA Engineer',
                'UI/UX': 'Designer',
                '영업': 'Sales Executive',
                '마케팅': 'Marketer',
                'CS': 'Support Specialist',
                'HR': 'HR Manager',
                '경영': 'Executive'
            }
            
            # Check if email exists
            if any(u.email == email for u in existing_users):
                continue
                
            new_user = User(
                email=email,
                name=fullname,
                hashed_password=hp,
                team=team_assigned,
                phone=phone,
                address=address,
                avatar=avatar,
                role=role_map.get(team_assigned, 'Staff'),
                is_admin=False,
                is_active=True
            )
            new_users.append(new_user)
            session.add(new_user)
            
        await session.commit()
        print(f"Successfully seeded {len(new_users)} new users into the database!")

if __name__ == "__main__":
    asyncio.run(seed_random_users())
