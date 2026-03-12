#!/usr/bin/env python
"""Entry point for CrewAI Platform."""

from networking_crews.crew import NetworkingCrews


def run():
    """Entry point for CrewAI Platform."""
    inputs = {
        "raw_events": [],
        "context": {},
    }
    NetworkingCrews().discovery_crew().kickoff(inputs=inputs)


def train():
    """Train the crew for better results."""
    inputs = {"raw_events": [], "context": {}}
    try:
        NetworkingCrews().discovery_crew().train(
            n_iterations=int(input("Iterations: ")),
            filename=input("Training data file: "),
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"Training error: {e}")


if __name__ == "__main__":
    run()
