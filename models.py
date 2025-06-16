from sqlalchemy import Column, String, Boolean, Integer, PickleType
from database import Base

class DBRunner(Base):
    __tablename__ = "runners"

    id = Column(String, primary_key=True, index=True)
    task_excel = Column(String)
    conversation_path = Column(String)
    # We will store the agent runner object itself, or a reference to it.
    # For simplicity, and because AgentRunner is not easily serializable to JSON directly
    # without significant changes, we'll explore how to manage its state or reference.
    # Storing the full object might be complex with SQLite if it contains non-serializable parts.
    # A common approach is to store IDs or reconstructable state.
    # For now, let's assume we might store a pickled version or a placeholder.
    # agent_runner_instance = Column(PickleType, nullable=True) # Example if pickling
    is_done = Column(Boolean, default=False)

    # Add other relevant fields from AgentRunner if needed for querying or state, e.g.:
    # current_status = Column(String)
