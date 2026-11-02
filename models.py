"""Validated output contracts shared by the AI service and interface."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Evidence(StrictModel):
    qualification: str
    resume_evidence: str
    job_evidence: str


class Gap(StrictModel):
    qualification: str
    status: Literal['Not documented', 'Partially demonstrated', 'Student-reported gap']
    explanation: str
    next_step: str


class Rewrite(StrictModel):
    original: str
    suggested: str
    reason: str


class ResumeAnalysis(StrictModel):
    alignment: Literal['Strong', 'Moderate', 'Limited']
    summary: str
    strengths: list[Evidence]
    gaps: list[Gap]
    rewrites: list[Rewrite]
    appropriate_keywords: list[str]
    priorities: list[str]
    limitations: str


class Skill(StrictModel):
    skill: str
    priority: Literal['High', 'Medium', 'Low']
    rationale: str
    activity: str
    success_measure: str


class Milestone(StrictModel):
    period: Literal['Days 1–30', 'Days 31–60', 'Days 61–90']
    goal: str
    actions: list[str]
    deliverable: str


class Roadmap(StrictModel):
    objective: str
    basis: Literal['Specific job description', 'General role expectations']
    relevant_skills: list[str]
    skills_to_develop: list[Skill]
    projects_and_learning: list[str]
    milestones: list[Milestone] = Field(min_length=3, max_length=3)
    assumptions: list[str]


class Question(StrictModel):
    question: str
    kind: Literal['Behavioral', 'Technical']


class Feedback(StrictModel):
    relevance: str
    clarity: str
    specificity: str
    structure: str
    completeness: str
    conceptual_correctness: str
    strengths: list[str]
    improvements: list[str]
    stronger_response: str


class InterviewSummary(StrictModel):
    overview: str
    strengths: list[str]
    recurring_gaps: list[str]
    practice_plan: list[str]
