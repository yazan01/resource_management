# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now, today, getdate, date_diff, flt, add_days
from frappe.model.document import Document

@frappe.whitelist()
def approve_request(name):
    """
    Approve a resource allocation request
    
    Args:
        name (str): The name of the resource allocation
        
    Returns:
        bool: True if successful
    """
    if not frappe.has_permission("Resource Allocation", "write"):
        frappe.throw("You do not have permission to approve resource allocations")
    
    allocation = frappe.get_doc("Resource Allocation", name)
    
    if allocation.status != "Requested":
        frappe.throw("Only requested allocations can be approved")
    
    # Check if the employee is available for the requested period
    validate_employee_availability(
        allocation.employee, 
        allocation.start_date, 
        allocation.end_date, 
        allocation.allocation_percentage,
        allocation.name
    )
    
    # Update status to Approved
    allocation.status = "Approved"
    allocation.save()
    
    # Submit the document if not submitted
    if not allocation.docstatus == 1:
        allocation.submit()
    
    # Create Project Assignment
    create_project_assignment(allocation)
    
    # Send notification
    send_approval_notification(allocation)
    
    return True

@frappe.whitelist()
def reject_request(name, rejection_reason):
    """
    Reject a resource allocation request
    
    Args:
        name (str): The name of the resource allocation
        rejection_reason (str): Reason for rejection
        
    Returns:
        bool: True if successful
    """
    if not frappe.has_permission("Resource Allocation", "write"):
        frappe.throw("You do not have permission to reject resource allocations")
    
    allocation = frappe.get_doc("Resource Allocation", name)
    
    if allocation.status != "Requested":
        frappe.throw("Only requested allocations can be rejected")
    
    # Update status to Rejected
    allocation.status = "Rejected"
    allocation.notes = f"Rejection Reason: {rejection_reason}\n\n{allocation.notes or ''}"
    allocation.save()
    
    # Send notification
    send_rejection_notification(allocation, rejection_reason)
    
    return True

@frappe.whitelist()
def get_employee_allocations(employee, start_date, end_date, allocation_percentage=None, current_allocation=""):
    """
    Get all allocations for an employee in a given period
    
    Args:
        employee (str): The employee ID
        start_date (str): Start date
        end_date (str): End date
        allocation_percentage (float, optional): New allocation percentage
        current_allocation (str, optional): Current allocation ID to exclude
        
    Returns:
        dict: Dict with allocations and availability info
    """
    # Convert dates to date objects if they are strings
    if isinstance(start_date, str):
        start_date = getdate(start_date)
    if isinstance(end_date, str):
        end_date = getdate(end_date)
    
    # Get all approved allocations for this employee in this period
    allocations = frappe.db.sql("""
        SELECT name, project, allocation_percentage, start_date, end_date
        FROM `tabResource Allocation`
        WHERE employee = %s AND status = 'Approved'
        AND ((start_date BETWEEN %s AND %s) OR (end_date BETWEEN %s AND %s) 
            OR (start_date <= %s AND end_date >= %s))
        AND name != %s
    """, (employee, start_date, end_date, start_date, end_date, 
          start_date, end_date, current_allocation), as_dict=1)
    
    # Calculate total allocation for each day in the period
    date_allocation_map = {}
    total_allocation = 0
    
    if allocations:
        period_days = date_diff(end_date, start_date) + 1
        
        # Initialize allocation for each day
        for i in range(period_days):
            check_date = add_days(start_date, i)
            date_allocation_map[str(check_date)] = 0
            
            # Add allocation percentage for each day
            for allocation in allocations:
                alloc_start = getdate(allocation.start_date)
                alloc_end = getdate(allocation.end_date)
                
                if alloc_start <= check_date <= alloc_end:
                    date_allocation_map[str(check_date)] += flt(allocation.allocation_percentage)
        
        # Calculate average allocation across the period
        total = 0
        for date, alloc in date_allocation_map.items():
            total += alloc
        
        if period_days > 0:
            total_allocation = total / period_days
    
    # Calculate available allocation
    available_allocation = 100 - total_allocation
    
    return {
        "allocations": allocations,
        "total_allocation": total_allocation,
        "available_allocation": available_allocation,
        "date_allocation_map": date_allocation_map
    }

def create_project_assignment(allocation):
    """
    Create a project assignment from an approved allocation
    
    Args:
        allocation (Document): Resource Allocation document
    
    Returns:
        Document: The created Project Assignment
    """
    # Check if project assignment already exists
    existing = frappe.db.exists("Project Assignment", {
        "allocation_reference": allocation.name
    })
    
    if existing:
        return frappe.get_doc("Project Assignment", existing)
    
    # Create new project assignment
    assignment = frappe.new_doc("Project Assignment")
    assignment.project = allocation.project
    assignment.employee = allocation.employee
    assignment.allocation_reference = allocation.name
    assignment.start_date = allocation.start_date
    assignment.end_date = allocation.end_date
    assignment.allocation_percentage = allocation.allocation_percentage
    assignment.hourly_cost_rate = allocation.hourly_cost_rate
    assignment.estimated_total_cost = allocation.estimated_total_cost
    assignment.status = "Active" 
    
    assignment.insert()
    assignment.submit()
    
    # Update employee and project records
    update_employee_allocations(allocation.employee)
    update_project_allocations(allocation.project)
    
    return assignment

def validate_employee_availability(employee, start_date, end_date, allocation_percentage, current_allocation=""):
    """
    Validate if an employee is available for the given allocation
    
    Args:
        employee (str): Employee ID
        start_date (str): Start date
        end_date (str): End date
        allocation_percentage (float): Allocation percentage
        current_allocation (str, optional): Current allocation ID to exclude
    
    Raises:
        frappe.ValidationError: If employee is over-allocated
    """
    # Get employee allocations
    employee_allocations = get_employee_allocations(
        employee, start_date, end_date, allocation_percentage, current_allocation
    )
    
    # Check if any day exceeds 100% allocation
    for date, alloc in employee_allocations.get("date_allocation_map", {}).items():
        if alloc + flt(allocation_percentage) > 100:
            frappe.throw(f"Employee is already allocated {alloc}% on {date}. " 
                         f"Adding {allocation_percentage}% would exceed 100%.")

def update_employee_allocations(employee):
    """Update employee's current allocations"""
    if not frappe.db.exists("Employee", employee):
        return
    
    employee_doc = frappe.get_doc("Employee", employee)
    
    # Get current active project assignments
    assignments = frappe.get_all("Project Assignment", 
        filters={
            "employee": employee,
            "status": "Active",
            "docstatus": 1
        },
        fields=["name", "project", "start_date", "end_date", 
                "allocation_percentage", "estimated_total_cost"]
    )
    
    # Update the employee document
    if hasattr(employee_doc, "current_allocations"):
        # Clear existing allocations
        employee_doc.current_allocations = []
        
        # Add current assignments
        for assignment in assignments:
            employee_doc.append("current_allocations", {
                "project": assignment.project,
                "start_date": assignment.start_date,
                "end_date": assignment.end_date,
                "allocation_percentage": assignment.allocation_percentage,
                "estimated_total_cost": assignment.estimated_total_cost,
                "allocation_reference": assignment.name
            })
        
        employee_doc.save()

def update_project_allocations(project):
    """Update project's resource allocations"""
    if not frappe.db.exists("Project", project):
        return
    
    project_doc = frappe.get_doc("Project", project)
    
    # Get current active project assignments
    assignments = frappe.get_all("Project Assignment", 
        filters={
            "project": project,
            "status": "Active",
            "docstatus": 1
        },
        fields=["name", "employee", "start_date", "end_date", 
                "allocation_percentage", "estimated_total_cost"]
    )
    
    # Update the project document
    if hasattr(project_doc, "project_assignments"):
        # Clear existing assignments
        project_doc.project_assignments = []
        
        # Add current assignments
        for assignment in assignments:
            project_doc.append("project_assignments", {
                "employee": assignment.employee,
                "start_date": assignment.start_date,
                "end_date": assignment.end_date,
                "allocation_percentage": assignment.allocation_percentage,
                "estimated_total_cost": assignment.estimated_total_cost,
                "allocation_reference": assignment.name
            })
        
        # Recalculate total resource cost
        total_cost = sum([flt(assignment.estimated_total_cost) for assignment in assignments])
        if hasattr(project_doc, "estimated_resource_cost"):
            project_doc.estimated_resource_cost = total_cost
        
        project_doc.save()

def send_approval_notification(allocation):
    """Send notification when allocation is approved"""
    try:
        frappe.sendmail(
            recipients=[frappe.db.get_value("User", allocation.requested_by, "email")],
            subject=f"Resource Allocation Approved: {allocation.name}",
            message=f"""
                <p>Hello {frappe.db.get_value("User", allocation.requested_by, "full_name")},</p>
                <p>Your resource allocation request for {allocation.employee_name} 
                on project {allocation.project_name} has been approved.</p>
                <p>Details:</p>
                <ul>
                    <li>Employee: {allocation.employee_name}</li>
                    <li>Project: {allocation.project_name}</li>
                    <li>Period: {allocation.start_date} to {allocation.end_date}</li>
                    <li>Allocation: {allocation.allocation_percentage}%</li>
                </ul>
                <p>Regards,<br>
                Resource Management System</p>
            """,
            delayed=False
        )
    except Exception as e:
        frappe.log_error(f"Failed to send approval notification: {str(e)}")

def send_rejection_notification(allocation, rejection_reason):
    """Send notification when allocation is rejected"""
    try:
        frappe.sendmail(
            recipients=[frappe.db.get_value("User", allocation.requested_by, "email")],
            subject=f"Resource Allocation Rejected: {allocation.name}",
            message=f"""
                <p>Hello {frappe.db.get_value("User", allocation.requested_by, "full_name")},</p>
                <p>Your resource allocation request for {allocation.employee_name} 
                on project {allocation.project_name} has been rejected.</p>
                <p>Reason: {rejection_reason}</p>
                <p>Details:</p>
                <ul>
                    <li>Employee: {allocation.employee_name}</li>
                    <li>Project: {allocation.project_name}</li>
                    <li>Period: {allocation.start_date} to {allocation.end_date}</li>
                    <li>Allocation: {allocation.allocation_percentage}%</li>
                </ul>
                <p>Regards,<br>
                Resource Management System</p>
            """,
            delayed=False
        )
    except Exception as e:
        frappe.log_error(f"Failed to send rejection notification: {str(e)}")