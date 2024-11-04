from enum import Enum
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime
import json
import uuid

class Operation(Enum):
    CREATE_USER = "create_user"
    DELETE_USER = "delete_user"
    EDIT_USER = "edit_user"
    VIEW_REPORTS = "view_reports"
    GENERATE_REPORTS = "generate_reports"
    MANAGE_UNIT = "manage_unit"

@dataclass
class Unit:
    id: str
    name: str

@dataclass
class OperationLog:
    id: str
    operator_code: str
    operator_role: str
    operation: Operation
    unit_id: Optional[str]
    timestamp: datetime
    status: str
    details: Optional[str] = None

    def to_dict(self):
        return {
            'id': self.id,
            'operator_code': self.operator_code,
            'operator_role': self.operator_role,
            'operation': self.operation.value,
            'unit_id': self.unit_id,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status,
            'details': self.details
        }

class LogManager:
    def __init__(self, log_file_path: str = "operation_logs.json"):
        self.log_file_path = log_file_path
        self.logs: List[OperationLog] = []
        self.load_logs()

    def load_logs(self):
        try:
            with open(self.log_file_path, 'r') as f:
                logs_data = json.load(f)
                self.logs = [
                    OperationLog(
                        id=log['id'],
                        operator_code=log['operator_code'],
                        operator_role=log['operator_role'],
                        operation=Operation(log['operation']),
                        unit_id=log['unit_id'],
                        timestamp=datetime.fromisoformat(log['timestamp']),
                        status=log['status'],
                        details=log['details']
                    )
                    for log in logs_data
                ]
        except FileNotFoundError:
            self.logs = []

    def save_logs(self):
        with open(self.log_file_path, 'w') as f:
            json.dump([log.to_dict() for log in self.logs], f, indent=2)

    def add_log(self, log: OperationLog):
        self.logs.append(log)
        self.save_logs()

    def get_logs_by_operator(self, operator_code: str) -> List[OperationLog]:
        return [log for log in self.logs if log.operator_code == operator_code]

    def get_logs_by_unit(self, unit_id: str) -> List[OperationLog]:
        return [log for log in self.logs if log.unit_id == unit_id]

    def get_logs_by_timerange(self, start: datetime, end: datetime) -> List[OperationLog]:
        return [
            log for log in self.logs 
            if start <= log.timestamp <= end
        ]

class Profile:
    def __init__(self, name: str, base_role: str, operator_code: str):
        self.name = name
        self.base_role = base_role
        self.operator_code = operator_code
        self.unit_permissions: Dict[str, Set[Operation]] = {}
        self.global_permissions: Set[Operation] = set()
    
    def add_unit_permission(self, unit_id: str, operation: Operation):
        if unit_id not in self.unit_permissions:
            self.unit_permissions[unit_id] = set()
        self.unit_permissions[unit_id].add(operation)
    
    def add_global_permission(self, operation: Operation):
        self.global_permissions.add(operation)
    
    def can_perform(self, operation: Operation, unit_id: str = None) -> bool:
        if operation in self.global_permissions:
            return True
        
        if unit_id and unit_id in self.unit_permissions:
            return operation in self.unit_permissions[unit_id]
        
        return False

class ProfileManager:
    def __init__(self, log_manager: LogManager):
        self.profiles: Dict[str, Profile] = {}
        self.units: Dict[str, Unit] = {}
        self.log_manager = log_manager
    
    def create_profile(self, name: str, base_role: str, operator_code: str) -> Profile:
        profile = Profile(name, base_role, operator_code)
        self.profiles[name] = profile
        return profile
    
    def add_unit(self, unit_id: str, name: str) -> Unit:
        unit = Unit(unit_id, name)
        self.units[unit_id] = unit
        return unit
    
    def get_profile(self, name: str) -> Profile:
        return self.profiles.get(name)

class PermissionedAction(ABC):
    def __init__(self, log_manager: LogManager):
        self.log_manager = log_manager

    @abstractmethod
    def required_operation(self) -> Operation:
        pass
    
    @abstractmethod
    def execute(self, profile: Profile, unit_id: str = None):
        pass
    
    def can_execute(self, profile: Profile, unit_id: str = None) -> bool:
        return profile.can_perform(self.required_operation(), unit_id)

    def log_operation(self, profile: Profile, unit_id: str, status: str, details: str = None):
        log = OperationLog(
            id=str(uuid.uuid4()),
            operator_code=profile.operator_code,
            operator_role=profile.base_role,
            operation=self.required_operation(),
            unit_id=unit_id,
            timestamp=datetime.now(),
            status=status,
            details=details
        )
        self.log_manager.add_log(log)

class GenerateReportAction(PermissionedAction):
    def required_operation(self) -> Operation:
        return Operation.GENERATE_REPORTS
    
    def execute(self, profile: Profile, unit_id: str = None):
        try:
            if not self.can_execute(profile, unit_id):
                self.log_operation(profile, unit_id, "FAILED", "Insufficient permissions")
                raise PermissionError("Profile does not have permission to generate reports")
            
            print(f"Generating report for unit {unit_id}")
            self.log_operation(profile, unit_id, "SUCCESS", "Report generated successfully")
            
        except Exception as e:
            self.log_operation(profile, unit_id, "ERROR", str(e))
            raise

def main():
    log_manager = LogManager("operation_logs.json")
    profile_manager = ProfileManager(log_manager)

    unit1 = profile_manager.add_unit("UNIT1", "Marketing")
    unit2 = profile_manager.add_unit("UNIT2", "Sales")
    
    admin1 = profile_manager.create_profile("admin1", "administrator", "ADM001")
    admin1.add_unit_permission("UNIT1", Operation.GENERATE_REPORTS)
    admin1.add_unit_permission("UNIT1", Operation.VIEW_REPORTS)
    
    admin2 = profile_manager.create_profile("admin2", "administrator", "ADM002")
    admin2.add_unit_permission("UNIT1", Operation.VIEW_REPORTS)

    report_action = GenerateReportAction(log_manager)
    
    try:
        report_action.execute(admin1, "UNIT1")
        
        report_action.execute(admin2, "UNIT1")
    except PermissionError as e:
        print(f"Permission denied: {e}")

    print("\nRecent Operations:")
    for log in log_manager.logs[-5:]:
        print(f"""
Operation: {log.operation.value}
Operator: {log.operator_code} ({log.operator_role})
Unit: {log.unit_id}
Time: {log.timestamp}
Status: {log.status}
Details: {log.details}
        """)

if __name__ == "__main__":
    main()