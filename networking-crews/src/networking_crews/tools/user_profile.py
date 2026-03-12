from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import psycopg2
import os
import json


class UserProfileInput(BaseModel):
    user_id: int = Field(description="Telegram user ID")


class UserProfileTool(BaseTool):
    name: str = "user_profile"
    description: str = (
        "Get user profile from database. "
        "Returns all data: name, email, company, role, LinkedIn, "
        "and all additional fields for event registration."
    )
    args_schema: type[BaseModel] = UserProfileInput

    def _run(self, user_id: int) -> str:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()

        cur.execute(
            """
            SELECT name, email, phone, company, role, linkedin_url,
                   registration_data
            FROM users
            WHERE user_id = %s
        """,
            (user_id,),
        )

        row = cur.fetchone()
        conn.close()

        if not row:
            return "ERROR: User not found"

        profile = {
            "name": row[0],
            "email": row[1],
            "phone": row[2],
            "company": row[3],
            "role": row[4],
            "linkedin_url": row[5],
            "registration_data": row[6] or {},
        }
        return json.dumps(profile, ensure_ascii=False)
