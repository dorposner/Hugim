from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from .activity import Activity

@dataclass
class Period:
    """Represents a time period in the camp schedule."""
    name: str
    activities: Dict[str, Activity] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_activity(self, activity: Activity) -> None:
        """Add an activity to this period.
        
        Args:
            activity: The Activity to add to this period
        """
        self.activities[activity.hug_name] = activity
        self.updated_at = datetime.now()

    def get_activity(self, activity_name: str) -> Optional[Activity]:
        """Get an activity by name.
        
        Args:
            activity_name: Name of the activity to retrieve
            
        Returns:
            The Activity object if found, None otherwise
        """
        return self.activities.get(activity_name)

    def remove_activity(self, activity_name: str) -> bool:
        """Remove an activity from this period.
        
        Args:
            activity_name: Name of the activity to remove
            
        Returns:
            True if the activity was removed, False if it wasn't found
        """
        if activity_name in self.activities:
            del self.activities[activity_name]
            self.updated_at = datetime.now()
            return True
        return False
