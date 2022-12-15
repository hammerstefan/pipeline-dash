from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional

JobName = str
ServerUrl = str


class JobStatus(Enum):
    FAILURE = "FAILURE"
    UNSTABLE = "UNSTABLE"
    SUCCESS = "SUCCESS"
    NOT_RUN = "NOT RUN"
    IN_PROGRESS = "In Progress"
    ABORTED = "ABORTED"
    UNDEFINED: None = None


@dataclass
class JobData:
    name: str
    status: JobStatus
    build_num: Optional[int] = None
    timestamp: Optional[datetime] = None
    serial: Optional[str] = None
    url: Optional[str] = None
    human_url: Optional[str] = None
    downstream: dict[JobName, ServerUrl] = field(default_factory=dict)

    @classmethod
    def _undefined(cls) -> JobData:
        return JobData("UNDEFINED", JobStatus.UNDEFINED)

    UNDEFINED: ClassVar


# noinspection PyProtectedMember
JobData.UNDEFINED = JobData._undefined()

JobDataDict = dict[JobName, JobData]
