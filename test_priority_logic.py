#!/usr/bin/env python3

import django
import sys
import os

# Setup Django
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'firefighter.firefighter.settings')
django.setup()

from firefighter.incidents.factories import IncidentFactory, PriorityFactory, EnvironmentFactory
from firefighter.incidents.enums import IncidentStatus

# Test P1 incident creation
print("=== Test P1 Incident ===")
priority_p1 = PriorityFactory.create(value=1, needs_postmortem=True)
env_prd = EnvironmentFactory.create(value="PRD")

incident_p1 = IncidentFactory.create(
    _status=IncidentStatus.MITIGATED, 
    priority=priority_p1,
    environment=env_prd
)

print(f'Priority: {incident_p1.priority}')
print(f'Priority.value: {incident_p1.priority.value}')
print(f'Priority.needs_postmortem: {incident_p1.priority.needs_postmortem}')
print(f'Environment: {incident_p1.environment}')
print(f'Environment.value: {incident_p1.environment.value}')

requires_postmortem = bool(
    incident_p1.priority
    and incident_p1.environment
    and incident_p1.priority.needs_postmortem
    and incident_p1.environment.value == "PRD"
)
print(f'requires_postmortem: {requires_postmortem}')

# Test P3 incident creation  
print("\n=== Test P3 Incident ===")
priority_p3 = PriorityFactory.create(value=3, needs_postmortem=False)
incident_p3 = IncidentFactory.create(
    _status=IncidentStatus.MITIGATED, 
    priority=priority_p3,
    environment=env_prd
)

print(f'Priority: {incident_p3.priority}')
print(f'Priority.value: {incident_p3.priority.value}')
print(f'Priority.needs_postmortem: {incident_p3.priority.needs_postmortem}')
print(f'Environment: {incident_p3.environment}')
print(f'Environment.value: {incident_p3.environment.value}')

requires_postmortem_p3 = bool(
    incident_p3.priority
    and incident_p3.environment
    and incident_p3.priority.needs_postmortem
    and incident_p3.environment.value == "PRD"
)
print(f'requires_postmortem: {requires_postmortem_p3}')