from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from networking_crews.tools.perplexity_search import PerplexitySearchTool
from networking_crews.tools.transport_cost import TransportCostTool
from networking_crews.tools.google_calendar import GoogleCalendarTool
from networking_crews.tools.methodology_db import MethodologyDBTool
from networking_crews.tools.currency import CurrencyTool
from networking_crews.tools.user_profile import UserProfileTool

from networking_crews.models.scout_output import ScoutOutput
from networking_crews.models.analyst_output import AnalystOutput
from networking_crews.models.booking_output import BookingCoordinationResult
from networking_crews.models.coach_output import CoachOutput
from networking_crews.models.finance_output import ROIReport, AggregatedStats
from networking_crews.models.onboarding_output import OnboardingResult


@CrewBase
class NetworkingCrews:
    """Networking AI Agent - all crews."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # -- Agents --

    @agent
    def scout_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["scout_agent"],
            tools=[PerplexitySearchTool()],
        )

    @agent
    def analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["analyst_agent"],
            tools=[TransportCostTool(), GoogleCalendarTool()],
        )

    @agent
    def coach_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["coach_agent"],
            tools=[MethodologyDBTool()],
        )

    @agent
    def booker_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["booker_agent"],
            tools=[UserProfileTool(), GoogleCalendarTool()],
        )

    @agent
    def finance_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["finance_agent"],
            tools=[TransportCostTool(), CurrencyTool()],
        )

    @agent
    def onboarding_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["onboarding_agent"],
        )

    # -- Tasks --

    @task
    def filter_events(self) -> Task:
        return Task(
            config=self.tasks_config["filter_events"],
            output_pydantic=ScoutOutput,
        )

    @task
    def score_events(self) -> Task:
        return Task(
            config=self.tasks_config["score_events"],
            output_pydantic=AnalystOutput,
        )

    @task
    def coordinate_booking(self) -> Task:
        return Task(
            config=self.tasks_config["coordinate_booking"],
            output_pydantic=BookingCoordinationResult,
        )

    @task
    def generate_challenge(self) -> Task:
        return Task(
            config=self.tasks_config["generate_challenge"],
            output_pydantic=CoachOutput,
        )

    @task
    def calculate_roi(self) -> Task:
        return Task(
            config=self.tasks_config["calculate_roi"],
            output_pydantic=ROIReport,
        )

    @task
    def evaluate_challenge(self) -> Task:
        return Task(config=self.tasks_config["evaluate_challenge"])

    @task
    def collect_profile(self) -> Task:
        return Task(
            config=self.tasks_config["collect_profile"],
            output_pydantic=OnboardingResult,
        )

    @task
    def weekly_summary(self) -> Task:
        return Task(
            config=self.tasks_config["weekly_summary"],
            output_pydantic=AggregatedStats,
        )

    # -- Crews --

    @crew
    def discovery_crew(self) -> Crew:
        return Crew(
            agents=[self.scout_agent(), self.analyst_agent()],
            tasks=[self.filter_events(), self.score_events()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def booking_crew(self) -> Crew:
        return Crew(
            agents=[self.booker_agent(), self.coach_agent()],
            tasks=[self.coordinate_booking(), self.generate_challenge()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def debrief_crew(self) -> Crew:
        return Crew(
            agents=[self.finance_agent(), self.coach_agent()],
            tasks=[self.calculate_roi(), self.evaluate_challenge()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def onboarding_crew(self) -> Crew:
        return Crew(
            agents=[self.onboarding_agent()],
            tasks=[self.collect_profile()],
            process=Process.sequential,
            verbose=True,
        )

    @crew
    def weekly_report_crew(self) -> Crew:
        return Crew(
            agents=[self.finance_agent()],
            tasks=[self.weekly_summary()],
            process=Process.sequential,
            verbose=True,
        )
