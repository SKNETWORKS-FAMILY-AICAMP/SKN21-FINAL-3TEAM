import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import sys
import os

# Add backend directory to path so we can import app modules if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.user import User

# Using the SSH tunnel connection string
DATABASE_URL = "postgresql+asyncpg://postgre:dudu123!@localhost:5433/workflow_agent?ssl=require"

async def update_existing_users():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Fetch existing users that might have empty fields
        result = await session.execute(select(User))
        existing_users = result.scalars().all()
        
        users_to_update = [u for u in existing_users if not u.phone or not u.address or not u.avatar]
        
        if not users_to_update:
            print("No existing users need to be updated.")
            return
            
        print(f"Found {len(users_to_update)} users to update. Fetching data from randomuser.me...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://randomuser.me/api/?results={len(users_to_update)}")
            if response.status_code != 200:
                print("Failed to fetch random users")
                return
            random_data = response.json()["results"]
            
        for i, user in enumerate(users_to_update):
            r_user = random_data[i]
            if not user.phone:
                user.phone = r_user['phone']
            if not user.address:
                user.address = f"{r_user['location']['city']}, {r_user['location']['country']}"
            if not user.avatar:
                user.avatar = r_user['picture']['large']
            
            # Optionally assign a default role if empty, based on their team if they have one
            if not user.role:
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
                user.role = role_map.get(user.team, 'Staff') if user.team else 'Staff'
                
            session.add(user)
            
        await session.commit()
        print(f"Successfully updated {len(users_to_update)} existing users with random data!")

if __name__ == "__main__":
    asyncio.run(update_existing_users())
