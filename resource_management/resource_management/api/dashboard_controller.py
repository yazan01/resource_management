# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today, add_days, getdate
from frappe import _

@frappe.whitelist()
def get_dashboard_data():
    """Get data for the CGO Dashboard"""
    department = frappe.form_dict.get("department")
    project = frappe.form_dict.get("project")
    
    # Set default date filters - next 30 days
    today_date = getdate(today())
    end_date = add_days(today_date, 30)
    
    # Get assignments ending soon
    ending_soon = get_assignments_ending_soon(today_date, end_date, department, project)
    
    # Get unallocated employees
    unallocated = get_unallocated_employees(department)
    
    # Get allocation requests
    allocation_requests = get_resource_allocation_requests()
    
    # Get current allocations
    current_allocations = get_current_allocations(department, project)
    
    # Allocation summary by department
    allocation_summary = get_allocation_summary()
    
    return {
        "ending_soon": ending_soon,
        "unallocated": unallocated,
        "allocation_requests": allocation_requests,
        "current_allocations": current_allocations,
        "allocation_summary": allocation_summary
    }

def get_assignments_ending_soon(start_date, end_date, department=None, project=None):
    """Get assignments ending in the next specified days"""
    filters = {
        "end_date": ["between", [start_date, end_date]],
        "status": "Active",
        "docstatus": 1
    }
    
    if project:
        filters["project"] = project
    
    assignments = frappe.get_all(
        "Project Assignment",
        filters=filters,
        fields=["name", "employee", "employee_name", "project", "project_name", 
                "start_date", "end_date", "allocation_percentage", "status"]
    )
    
    if department:
        # Filter by department if specified
        filtered_assignments = []
        for assignment in assignments:
            # Get employee department
            emp_dept = frappe.db.get_value("Employee", assignment.employee, "department")
            if emp_dept == department:
                filtered_assignments.append(assignment)
        
        assignments = filtered_assignments
    
    # Add remaining days to each assignment
    for assignment in assignments:
        assignment["remaining_days"] = (getdate(assignment.end_date) - getdate(today())).days
    
    return assignments

def get_unallocated_employees(department=None):
    """Get employees who are not allocated to any project"""
    # Get all employees who are active
    filters = {"status": "Active"}
    if department:
        filters["department"] = department
        
    all_employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "department", "reports_to", "designation"]
    )
    
    # Get employees who have active project assignments
    today_date = getdate(today())
    allocated_employees = frappe.db.sql("""
        SELECT DISTINCT employee 
        FROM `tabProject Assignment`
        WHERE docstatus = 1
        AND status = 'Active'
        AND start_date <= %s
        AND end_date >= %s
    """, (today_date, today_date), as_dict=1)
    
    allocated_employee_ids = [emp.employee for emp in allocated_employees]
    
    # Filter employees who are not allocated
    unallocated_employees = [
        emp for emp in all_employees
        if emp.name not in allocated_employee_ids
    ]
    
    return unallocated_employees

def get_resource_allocation_requests():
    """Get pending resource allocation requests"""
    allocation_requests = frappe.get_all(
        "Resource Allocation",
        filters={"status": "Requested", "docstatus": 0},
        fields=["name", "employee", "employee_name", "project", "project_name", 
                "start_date", "end_date", "allocation_percentage", "status",
                "requested_by", "request_date"]
    )
    
    return allocation_requests

def get_current_allocations(department=None, project=None):
    """Get current active allocations"""
    today_date = getdate(today())
    filters = {
        "status": "Active",
        "docstatus": 1,
        "start_date": ["<=", today_date],
        "end_date": [">=", today_date]
    }
    
    if project:
        filters["project"] = project
        
    current_allocations = frappe.get_all(
        "Project Assignment",
        filters=filters,
        fields=["name", "employee", "employee_name", "project", "project_name", 
                "start_date", "end_date", "allocation_percentage", "status"]
    )
    
    if department:
        # Filter by department if specified
        filtered_allocations = []
        for allocation in current_allocations:
            # Get employee department
            emp_dept = frappe.db.get_value("Employee", allocation.employee, "department")
            if emp_dept == department:
                filtered_allocations.append(allocation)
        
        current_allocations = filtered_allocations
    
    # Add remaining days to each allocation
    for allocation in current_allocations:
        allocation["remaining_days"] = (getdate(allocation.end_date) - today_date).days
    
    return current_allocations

def get_allocation_summary():
    """Get summary of employee allocations by department"""
    departments = frappe.get_all("Department", fields=["name"])
    today_date = getdate(today())
    
    summary = []
    
    for dept in departments:
        department = dept.name
        # Get all employees in this department
        total_employees = frappe.db.count("Employee", {"department": department, "status": "Active"})
        
        # Get allocated employees in this department
        allocated_employee_query = """
            SELECT COUNT(DISTINCT e.name) as count
            FROM `tabEmployee` e
            INNER JOIN `tabProject Assignment` pa
            ON e.name = pa.employee
            WHERE e.department = %s
            AND e.status = 'Active'
            AND pa.docstatus = 1
            AND pa.status = 'Active'
            AND pa.start_date <= %s
            AND pa.end_date >= %s
        """
        
        allocated_result = frappe.db.sql(allocated_employee_query, 
                                         (department, today_date, today_date), as_dict=1)
        allocated_employees = allocated_result[0].count if allocated_result else 0
        
        # Calculate percentages
        unallocated_employees = total_employees - allocated_employees
        allocation_percentage = (allocated_employees / total_employees * 100) if total_employees > 0 else 0
        
        summary.append({
            "department": department,
            "total_employees": total_employees,
            "allocated_employees": allocated_employees,
            "unallocated_employees": unallocated_employees,
            "allocation_percentage": allocation_percentage
        })
    
    return summary