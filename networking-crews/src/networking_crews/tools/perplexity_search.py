from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import httpx
import os


class PerplexitySearchInput(BaseModel):
    query: str = Field(description="Search query")


class PerplexitySearchTool(BaseTool):
    name: str = "perplexity_search"
    description: str = (
        "Search information on the internet via Perplexity Sonar API. "
        "Use for searching information about event organizers, "
        "reviews, speakers, additional venues."
    )
    args_schema: type[BaseModel] = PerplexitySearchInput

    def _run(self, query: str) -> str:
        response = httpx.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
            },
            timeout=30,
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]
