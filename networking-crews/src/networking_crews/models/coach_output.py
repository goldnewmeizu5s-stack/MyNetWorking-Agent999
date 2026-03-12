from pydantic import BaseModel


class GeneratedChallenge(BaseModel):
    methodology_id: str
    methodology_name: str
    description: str
    success_metrics: list[str]
    tips: list[str]
    difficulty: str                # "beginner" | "intermediate" | "advanced"


class CoachOutput(BaseModel):
    challenge: GeneratedChallenge
    progress_note: str             # e.g. "This is your 12th challenge. Level: intermediate."
