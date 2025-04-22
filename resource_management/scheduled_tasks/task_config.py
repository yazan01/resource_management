# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, today, getdate, flt

def all():
    """Daily scheduled tasks that run every 5 minutes"""
    pass

def daily():
    """Daily scheduled tasks that run once per day"""
    # Update completed assignments
    update_completed_assignments()
    
    # Check for assignments ending soon
    check_ending_assignments()
    
    # Update project costing
    update_project_costing()
    
    # Send daily resource allocation summary to CGO
    send_daily_allocation_summary()

def hourly():
    """Hourly scheduled tasks"""
    # Process pending resource allocation requests
    process_pending_allocation_requests()

def weekly():
    """Weekly scheduled tasks"""
    # Generate resource utilization report
    generate_resource_utilization_report()
    
    # Check for employees with low utilization
    check_low_utilization_employees()

def monthly():
    """Monthly scheduled tasks"""
    # Generate monthly project cost reports
    generate_monthly_project_cost_reports()
    
    # Archive completed assignments older than 3 months
    archive_old_completed_assignments()

def update_completed_assignments():
    """Update assignments that have ended to Completed status"""
    today_date = getdate(today())
    
    # Get assignments that have ended
    completed_assignments = frappe.get_all(
        "Project Assignment",
        filters={
            "end_date": ["<", today_date],
            "status": "Active",
            "docstatus": 1
        },
        fields=["name", "employee", "employee_name", "project", "project_name"]
    )
    
    for assignment in completed_assignments:
        frappe.db.set_value("Project Assignment", assignment.name, "status", "Completed")
        
        # Create a notification for the CGO
        create_assignment_completion_notification(assignment)
        
        frappe.db.commit()