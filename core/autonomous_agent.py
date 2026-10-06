
"""
Autonomous Agent for VICTOR
- Self-decision making
- Follow-up task execution
- Goal-oriented behavior
- Adaptive planning
"""
import time
import threading
from dataclasses import dataclass
from enum import Enum


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    FOLLOWING_UP = "following_up"
    WAITING_FOR_INPUT = "waiting_for_input"


@dataclass
class Goal:
    id: str
    description: str
    priority: int
    steps: list
    current_step: int = 0
    completed: bool = False
    created_at: float = 0.0


class AutonomousAgent:
    def __init__(self, victor_core):
        self.victor = victor_core
        self.state = AgentState.IDLE
        self.current_goal = None
        self.goal_queue = []
        self.follow_up_tasks = []
        self.is_running = False
        self.agent_thread = None

        self.on_goal_complete = None
        self.on_follow_up = None

    def start(self):
        self.is_running = True
        self.agent_thread = threading.Thread(target=self._agent_loop, daemon=True)
        self.agent_thread.start()
        print("[Autonomous Agent] Started")

    def stop(self):
        self.is_running = False
        if self.agent_thread:
            self.agent_thread.join(timeout=2.0)
        print("[Autonomous Agent] Stopped")

    def set_goal(self, description, steps, priority=5):
        goal = Goal(
            id=f"goal_{int(time.time())}",
            description=description,
            priority=priority,
            steps=steps,
            created_at=time.time()
        )
        self.goal_queue.append(goal)
        self.goal_queue.sort(key=lambda g: g.priority)
        print(f"[Autonomous Agent] New goal set: {description}")
        return goal

    def add_follow_up(self, task, delay=0.0):
        task['execute_at'] = time.time() + delay
        self.follow_up_tasks.append(task)
        print(f"[Autonomous Agent] Follow-up task added: {task.get('description', 'Unknown')}")

    def _agent_loop(self):
        while self.is_running:
            try:
                self._process_follow_ups()

                if not self.current_goal and self.goal_queue:
                    self.current_goal = self.goal_queue.pop(0)
                    self.state = AgentState.PLANNING
                    print(f"[Autonomous Agent] Starting goal: {self.current_goal.description}")

                if self.current_goal and not self.current_goal.completed:
                    self._execute_goal_step()

                if not self.current_goal and not self.follow_up_tasks:
                    self.state = AgentState.IDLE

                time.sleep(0.5)

            except Exception as e:
                print(f"[Autonomous Agent] Error in loop: {e}")
                time.sleep(1.0)

    def _process_follow_ups(self):
        now = time.time()
        to_execute = [t for t in self.follow_up_tasks if t.get('execute_at', 0) <= now]

        for task in to_execute:
            self.state = AgentState.FOLLOWING_UP
            print(f"[Autonomous Agent] Executing follow-up: {task.get('description', 'Unknown')}")

            try:
                if 'command' in task and self.victor:
                    response = self.victor.process_command(task['command'])
                    if self.on_follow_up:
                        self.on_follow_up(task, response)
            except Exception as e:
                print(f"[Autonomous Agent] Follow-up failed: {e}")

            self.follow_up_tasks.remove(task)

    def _execute_goal_step(self):
        if not self.current_goal:
            return

        self.state = AgentState.EXECUTING
        goal = self.current_goal

        if goal.current_step < len(goal.steps):
            step = goal.steps[goal.current_step]
            print(f"[Autonomous Agent] Step {goal.current_step + 1}/{len(goal.steps)}: {step}")

            if self.victor:
                try:
                    self.victor.process_command(step)
                except Exception as e:
                    print(f"[Autonomous Agent] Step failed: {e}")

            goal.current_step += 1
        else:
            goal.completed = True
            self.state = AgentState.IDLE
            print(f"[Autonomous Agent] Goal completed: {goal.description}")
            if self.on_goal_complete:
                self.on_goal_complete(goal)
            self.current_goal = None

    def get_status(self):
        return {
            'state': self.state.value,
            'current_goal': self.current_goal.description if self.current_goal else None,
            'goals_queued': len(self.goal_queue),
            'follow_ups_pending': len(self.follow_up_tasks)
        }

    def clear_goals(self):
        self.current_goal = None
        self.goal_queue = []
        self.follow_up_tasks = []
        self.state = AgentState.IDLE
        print("[Autonomous Agent] All goals and follow-ups cleared")

