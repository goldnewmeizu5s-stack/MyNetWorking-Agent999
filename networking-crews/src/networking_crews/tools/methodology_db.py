from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import psycopg2
import os
import json


class MethodologySearchInput(BaseModel):
    event_description: str = Field(
        description="Event description for semantic search"
    )
    event_type: str = Field(
        description="Event type: conference, meetup, workshop, networking_dinner"
    )
    user_level: str = Field(
        description="User level: beginner, intermediate, advanced"
    )
    excluded_ids: str = Field(
        default="[]",
        description="JSON array of methodology IDs to exclude",
    )


class MethodologyDBTool(BaseTool):
    name: str = "methodology_db"
    description: str = (
        "Search networking methodologies in vector database (pgvector). "
        "Finds 2-3 suitable methodologies by semantic similarity to the event, "
        "with filters by event type, user level, and excluding already used ones."
    )
    args_schema: type[BaseModel] = MethodologySearchInput

    def _run(
        self,
        event_description: str,
        event_type: str,
        user_level: str,
        excluded_ids: str = "[]",
    ) -> str:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()

        excluded = json.loads(excluded_ids) if excluded_ids else []
        excluded_clause = ""
        if excluded:
            placeholders = ",".join(["%s"] * len(excluded))
            excluded_clause = f"AND methodology_id NOT IN ({placeholders})"

        query = f"""
            SELECT methodology_id, name, description, category,
                   event_types, difficulty, skills
            FROM methodologies
            WHERE (event_types @> %s::jsonb OR event_types @> '"any"'::jsonb)
              AND difficulty = %s
              {excluded_clause}
            ORDER BY embedding <=> (
                SELECT embedding FROM methodology_query_cache
                WHERE query_hash = md5(%s)
                LIMIT 1
            )
            LIMIT 3
        """

        params: list = [json.dumps([event_type]), user_level]
        if excluded:
            params.extend(excluded)
        params.append(event_description)

        cur.execute(query, params)
        results = cur.fetchall()
        conn.close()

        if not results:
            return "No matching methodologies found"

        methodologies = []
        for r in results:
            methodologies.append(
                {
                    "id": r[0],
                    "name": r[1],
                    "description": r[2],
                    "category": r[3],
                    "event_types": r[4],
                    "difficulty": r[5],
                    "skills": r[6],
                }
            )

        return json.dumps(methodologies, ensure_ascii=False)
