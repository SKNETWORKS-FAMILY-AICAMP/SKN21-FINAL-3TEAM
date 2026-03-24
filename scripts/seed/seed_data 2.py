"""
테스트용 시드 데이터 (팀원 D 관리)
팀원 전체 계정 생성 스크립트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password


# 팀원 정보
TEAM_MEMBERS = [
    {
        "email": "jiyong@example.com",
        "password": "test1234",
        "name": "신지용 (PM)",
        "is_admin": True,  # PM은 관리자 권한
    },
    {
        "email": "kyungeun@example.com",
        "password": "test1234",
        "name": "윤경은 (AI서브)",
        "is_admin": False,
    },
    {
        "email": "seungeon@example.com",
        "password": "test1234",
        "name": "진승언 (AI리드)",
        "is_admin": False,
    },
    {
        "email": "hyebin@example.com",
        "password": "test1234",
        "name": "안혜빈 (Backend)",
        "is_admin": False,
    },
    {
        "email": "jiyoung@example.com",
        "password": "test1234",
        "name": "문지영 (Frontend)",
        "is_admin": False,
    },
    # 추가 테스트 계정
    {
        "email": "test@example.com",
        "password": "test1234",
        "name": "테스트 사용자",
        "is_admin": False,
    },
]


async def seed_users():
    """팀원 계정 생성"""
    async with AsyncSessionLocal() as db:
        created_count = 0
        existing_count = 0

        for member in TEAM_MEMBERS:
            # 이미 존재하는지 확인
            result = await db.execute(select(User).where(User.email == member["email"]))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"⏭️  이미 존재: {member['name']} ({member['email']})")
                existing_count += 1
                continue

            # 새 사용자 생성
            user = User(
                email=member["email"],
                hashed_password=hash_password(member["password"]),
                name=member["name"],
                is_admin=member.get("is_admin", False),
                is_active=True,
            )
            db.add(user)
            created_count += 1
            print(f"✅ 생성 완료: {member['name']} ({member['email']})")

        await db.commit()

        print(f"\n{'='*60}")
        print(f"시드 완료: {created_count}명 생성, {existing_count}명 기존 존재")
        print(f"{'='*60}")
        print(f"\n🔑 로그인 정보:")
        print(f"   이메일: [팀원이름]@example.com (예: hyebin@example.com)")
        print(f"   비밀번호: test1234 (공통)")
        print(f"{'='*60}\n")


async def main():
    print("🌱 시드 데이터 삽입 시작...\n")
    await seed_users()
    print("✨ 시드 완료!")


if __name__ == "__main__":
    asyncio.run(main())
