from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class Activity:
    hug_name: str
    capacity: int
    minimum: int
    periods: List[str]  # e.g., ['Aleph', 'Beth', 'Gimmel']
    enrolled_campers: List[str] = None  # List of camper IDs
    is_active: bool = True
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

    def __post_init__(self):
        if self.enrolled_campers is None:
            self.enrolled_campers = []

    @property
    def available_spots(self) -> int:
        return self.capacity - len(self.enrolled_campers)

    @property
    def is_full(self) -> bool:
        return len(self.enrolled_campers) >= self.capacity

    @property
    def meets_minimum(self) -> bool:
        return len(self.enrolled_campers) >= self.minimum

    def add_camper(self, camper_id: str) -> bool:
        """Add a camper to the activity if there's space"""
        if not self.is_full and camper_id not in self.enrolled_campers:
            self.enrolled_campers.append(camper_id)
            self.updated_at = datetime.now()
            return True
        return False

    def remove_camper(self, camper_id: str) -> bool:
        """Remove a camper from the activity"""
        if camper_id in self.enrolled_campers:
            self.enrolled_campers.remove(camper_id)
            self.updated_at = datetime.now()
            return True
        return False

@dataclass
class ActivityPeriod:
    name: str  # e.g., 'Aleph', 'Beth', 'Gimmel'
    activities: List[str]  # List of activity names
    start_time: Optional[str] = None
    end_time: Optional[str] = None

@dataclass
class CampSchedule:
    periods: List[ActivityPeriod]
    activities: Dict[str, Activity]
    
    def get_activities_by_period(self, period_name: str) -> List[Activity]:
        """Get all activities for a specific period"""
        period = next((p for p in self.periods if p.name == period_name), None)
        if period:
            return [self.activities[act_name] for act_name in period.activities]
        return []

    def get_available_activities(self, period_name: str) -> List[Activity]:
        """Get available activities for a specific period"""
        activities = self.get_activities_by_period(period_name)
        return [act for act in activities if not act.is_full and act.is_active]
