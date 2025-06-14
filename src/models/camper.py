from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class Camper:
    camper_id: str
    name: str
    preferences: Dict[str, List[str]] = None  # {period: [activity1, activity2, ...]}
    assigned_activities: Dict[str, str] = None  # {period: activity}
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    last_week_first_choice: bool = False

    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {}
        if self.assigned_activities is None:
            self.assigned_activities = {}

    def add_preference(self, period: str, activity: str) -> None:
        """Add a preference for a specific period"""
        if period not in self.preferences:
            self.preferences[period] = []
        self.preferences[period].append(activity)
        self.updated_at = datetime.now()

    def assign_activity(self, period: str, activity: str) -> None:
        """Assign an activity to a specific period"""
        self.assigned_activities[period] = activity
        self.updated_at = datetime.now()

    def remove_activity_assignment(self, period: str) -> None:
        """Remove activity assignment for a specific period"""
        if period in self.assigned_activities:
            del self.assigned_activities[period]
            self.updated_at = datetime.now()
