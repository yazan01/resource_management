# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import today, getdate
from frappe.permissions import has_permission
from datetime import timedelta

@frappe.whitelist()
def approve_request(name):
    """Approve a resource allocation request"""
    if not has_permission("Resource Allocation", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    allocation = frappe.get_doc("Resource Allocation", name)
    
    if allocation.status != "Requested":
        frappe.throw(_("Can only approve requested allocations"))
    
    # Check if the employee is available for the requested period and allocation percentage
    validate_employee_availability(
        allocation.employee, 
        allocation.start_date, 
        allocation.end_date, 
        allocation.allocation_percentage,
        allocation.name
    )
    
    # Update the allocation status
    allocation.status = "Approved"
    allocation.save()
    
    # Submit the document to create project assignment
    allocation.submit()
    
    frappe.msgprint(_("Resource Allocation {0} approved successfully").format(allocation.name))
    
    return allocation

@frappe.whitelist()
def reject_request(name):
    """Reject a resource allocation request"""
    if not has_permission("Resource Allocation", "write"):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    allocation = frappe.get_doc("Resource Allocation", name)
    
    if allocation.status != "Requested":
        frappe.throw(_("Can only reject requested allocations"))
    
    # Update the allocation status
    allocation.status = "Rejected"
    allocation.save()
    
    frappe.msgprint(_("Resource Allocation {0} rejected").format(allocation.name))
    
    return allocation

@frappe.whitelist()
def get_employee_allocations(employee, date=None):
    """Get all allocations for an employee on a specific date or today"""
    if not date:
        date = today()
    
    date = getdate(date)
    
    # Get all active assignments for the employee on the specified date
    allocations = frappe.get_all(
        "Project Assignment",
        filters={
            "employee": employee,
            "status": "Active",
            "docstatus": 1,
            "start_date": ["<=", date],
            "end_date": [">=", date]
        },
        fields=["name", "project", "allocation_percentage", "start_date", "end_date"]
    )
    
    # Calculate total allocation
    total_allocation = sum(allocation.allocation_percentage for allocation in allocations)
    
    return {
        "allocations": allocations,
        "total_allocation": total_allocation,
        "available_allocation": 100 - total_allocation
    }

def validate_employee_availability(employee, start_date, end_date, required_percentage, current_allocation=None):
    """Validate if employee is available for the requested period and allocation percentage"""
    # Get overlapping allocations
    filters = {
        "employee": employee,
        "status": "Active",
        "docstatus": 1,
    }
    
    # Add date filter conditions for overlap checking
    date_conditions = """
        ((start_date BETWEEN %s AND %s) OR 
         (end_date BETWEEN %s AND %s) OR 
         (start_date <= %s AND end_date >= %s))
    """
    
    if current_allocation:
        # Exclude current allocation when validating
        exclude_condition = " AND name != %s"
        overlapping_allocations = frappe.db.sql(f"""
            SELECT name, allocation_percentage, project, start_date, end_date
            FROM `tabProject Assignment`
            WHERE employee = %s 
            AND status = 'Active'
            AND docstatus = 1
            AND {date_conditions}
            {exclude_condition}
        """, (
            employee, 
            start_date, end_date, 
            start_date, end_date, 
            start_date, end_date,
            current_allocation
        ), as_dict=1)
    else:
        overlapping_allocations = frappe.db.sql(f"""
            SELECT name, allocation_percentage, project, start_date, end_date
            FROM `tabProject Assignment`
            WHERE employee = %s 
            AND status = 'Active'
            AND docstatus = 1
            AND {date_conditions}
        """, (
            employee, 
            start_date, end_date, 
            start_date, end_date, 
            start_date, end_date
        ), as_dict=1)
    
    # Calculate allocation for each day in the requested period
    start = getdate(start_date)
    end = getdate(end_date)
    
    # Create a daily allocation map
    current_date = start
    while current_date <= end:
        # Calculate total allocation for this day
        day_allocation = 0
        
        for allocation in overlapping_allocations:
            # Check if this allocation is active on current_date
            if getdate(allocation.start_date) <= current_date <= getdate(allocation.end_date):
                day_allocation += allocation.allocation_percentage
        
        # Check if adding the required percentage would exceed 100%
        if day_allocation + required_percentage > 100:
            frappe.throw(_(
                "Employee is already allocated {0}% on {1}. Cannot allocate more than 100%"
            ).format(day_allocation, current_date))
        
        current_date += timedelta(days=1)
        
    return True