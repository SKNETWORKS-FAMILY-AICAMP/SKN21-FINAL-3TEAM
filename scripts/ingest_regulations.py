"""
Regulation Ingestion Script

Ingests regulation PDF data into:
1. Qdrant (Vector Store) for RAG
2. PostgreSQL (Relational DB) for structured queries

Usage:
    python -m scripts.ingest_regulations
"""
import asyncio
import os
import sys
import sys
print("Script started...", flush=True)

from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

print("Imports starting...", flush=True)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

print("SQLAlchemy imported...", flush=True)

from backend.app.models.regulation import Regulation
from backend.app.config import get_settings
from ai.rag.qdrant_pipeline import get_qdrant_pipeline, reset_qdrant_pipeline
from ai.document_parser.regulation_parser import parse_regulation_pdf

print("All imports done.", flush=True)

settings = get_settings()

async def ingest_to_postgres(articles_data):
    """Ingest structured articles into PostgreSQL."""
    print(f"[DB] Ingesting {len(articles_data)} articles into PostgreSQL...")
    
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Optional: Clear existing regulations for a clean slate or specific version
            # For now, we'll just append or maybe clear all if it's a full re-ingestion
            # await session.execute(delete(Regulation)) 
            
            for data in articles_data:
                # Check if exists (simple check by article_number and version)
                stmt = select(Regulation).where(
                    Regulation.article_number == data["article_number"],
                    Regulation.version == data["version"]
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update
                    existing.title = data["title"]
                    existing.content = data["content"]
                    existing.category = data["category"]
                else:
                    # Insert
                    new_reg = Regulation(
                        article_number=data["article_number"],
                        title=data["title"],
                        content=data["content"],
                        category=data["category"],
                        version=data["version"]
                    )
                    session.add(new_reg)
            
            await session.commit()
            print("[DB] Ingestion complete.")
            
        except Exception as e:
            print(f"[DB] Error: {e}")
            await session.rollback()
        finally:
            await session.close()
            await engine.dispose()

def ingest_to_qdrant(chunks, metas):
    """Ingest chunks into Qdrant."""
    print(f"[RAG] Ingesting {len(chunks)} chunks into Qdrant...")
    try:
        # Reset pipeline to clear old data if needed (optional, depends on policy)
        # reset_qdrant_pipeline() 
        
        pipeline = get_qdrant_pipeline()
        pipeline.add_documents(
            documents=chunks,
            metadatas=metas,
            batch_size=50
        )
        print("[RAG] Ingestion complete.")
    except Exception as e:
        print(f"[RAG] Error: {e}")

async def main():
    pdf_path = ROOT / "data" / "regulations" / "dudu_tech_regulations.pdf"
    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}")
        return

    print(f"Processing {pdf_path}...")
    
    # 1. Parse PDF
    chunks, chunk_metas, articles = parse_regulation_pdf(str(pdf_path))
    print(f"Parsed {len(articles)} articles and {len(chunks)} RAG chunks.")

    # 2. Ingest to Postgres
    await ingest_to_postgres(articles)

    # 3. Ingest to Qdrant
    ingest_to_qdrant(chunks, chunk_metas)

    print("\nAll tasks finished.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
