from app.db.base import Base
from app.db.session import engine
from app.models import document, document_chunk, study_plan, study_plan_section, user, learning_session, session_message, tool_call, section_progress, upload

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
