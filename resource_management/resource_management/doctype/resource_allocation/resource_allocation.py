# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, add_days, today, flt, get_datetime

class ResourceAllocation(Document):
    def validate(self):
        self.validate_dates()
        self.validate_allocation_percentage()
        self.validate_employee_selection()
        
    def validate_dates(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            frappe.throw("End Date cannot be before Start Date")
            
    def validate_allocation_percentage(self):
        # Check if allocation percentage is between 0 and 100
        if self.allocation_percentage < 0 or self.allocation_percentage > 100:
            frappe.throw("Allocation Percentage must be between 0 and 100")
    
    def validate_employee_selection(self):
        if self.status != "Draft":
            # Validate that exactly one employee is selected
            selected_employees = [row for row in self.available_employees_table if row.select_employee]
            
            if len(selected_employees) == 0:
                frappe.throw("Please select an employee from the available employees table")
            elif len(selected_employees) > 1:
                frappe.throw("Please select only one employee")
            
            # Set the selected employee data
            selected_emp = selected_employees[0]
            self.employee = selected_emp.employee
            self.employee_name = selected_emp.employee_name
            self.employee_department = selected_emp.department
            self.hourly_cost_rate = selected_emp.hourly_cost_rate
            self.estimated_total_cost = selected_emp.estimated_cost
    
    def before_save(self):
        # Set requested_by to current user if not set
        if not self.requested_by:
            self.requested_by = frappe.session.user
    
    def on_submit(self):
        if self.status == "Approved":
            # Create Project Assignment
            self.create_project_assignment()
            
    def create_project_assignment(self):
        # Check if project assignment already exists
        existing_assignment = frappe.db.get_value("Project Assignment", {
            "allocation_reference": self.name
        })
        
        if not existing_assignment:
            # Create new Project Assignment
            project_assignment = frappe.new_doc("Project Assignment")
            project_assignment.project = self.project
            project_assignment.employee = self.employee
            project_assignment.allocation_reference = self.name
            project_assignment.start_date = self.start_date
            project_assignment.end_date = self.end_date
            project_assignment.allocation_percentage = self.allocation_percentage
            project_assignment.estimated_total_cost = self.estimated_total_cost
            project_assignment.save()
            
            frappe.msgprint(f"Project Assignment {project_assignment.name} created successfully")

@frappe.whitelist()
def get_available_employees(project, start_date, end_date, allocation_percentage, current_allocation=""):
    """Get list of available and unavailable employees for the given period"""
    
    # Get all employees
    employees = frappe.get_all("Employee", 
        filters={"status": "Active"},
        fields=["name", "employee_name", "department", "hourly_cost_rate"]
    )
    
    available_employees = []
    unavailable_employees = []
    
    for emp in employees:
        # Get current allocations for this employee in the period
        overlapping_allocations = frappe.db.sql("""
            SELECT SUM(allocation_percentage) as total_allocation
            FROM `tabResource Allocation`
            WHERE employee = %s AND status = 'Approved'
            AND ((start_date BETWEEN %s AND %s) OR (end_date BETWEEN %s AND %s) 
                OR (start_date <= %s AND end_date >= %s))
            AND name != %s
        """, (emp.name, start_date, end_date, start_date, end_date, 
              start_date, end_date, current_allocation or ""), as_dict=1)
        
        current_allocation_pct = overlapping_allocations[0].total_allocation or 0
        available_allocation_pct = 100 - current_allocation_pct
        
        # Calculate estimated cost
        working_days = date_diff(end_date, start_date) + 1
        working_hours = working_days * 8
        allocated_hours = working_hours * (float(allocation_percentage) / 100)
        estimated_cost = allocated_hours * (emp.hourly_cost_rate or 0)
        
        emp_data = {
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "department": emp.department,
            "current_allocation": current_allocation_pct,
            "available_allocation": available_allocation_pct,
            "hourly_cost_rate": emp.hourly_cost_rate or 0,
            "estimated_cost": estimated_cost
        }
        
        # Check if employee is available for the requested allocation
        if available_allocation_pct >= float(allocation_percentage):
            available_employees.append(emp_data)
        else:
            unavailable_employees.append(emp_data)
    
    # Sort available employees by available allocation (descending)
    available_employees.sort(key=lambda x: x["available_allocation"], reverse=True)
    
    # Sort unavailable employees by current allocation (ascending)
    unavailable_employees.sort(key=lambda x: x["current_allocation"])
    
    return {
        "available_employees": available_employees,
        "unavailable_employees": unavailable_employees
    }

@frappe.whitelist()
def request_allocation(name, selected_employee):
    """Submit allocation request"""
    doc = frappe.get_doc("Resource Allocation", name)
    
    # Validate permissions
    if not doc.has_permission("write"):
        frappe.throw("You don't have permission to modify this document")
    
    # Set the selected employee
    for row in doc.available_employees_table:
        if row.employee == selected_employee:
            row.select_employee = 1
        else:
            row.select_employee = 0
    
    # Update status to Requested
    doc.status = "Requested"
    doc.save()
    
    # Send notification to CGO
    send_notification_to_cgo(doc)
    
    return {"status": "success", "message": "Request submitted successfully"}

@frappe.whitelist()
def approve_request(name):
    """Approve allocation request - CGO only"""
    if not frappe.user.has_role('CGO'):
        frappe.throw("Only CGO can approve resource allocations")
    
    doc = frappe.get_doc("Resource Allocation", name)
    
    # Validate that exactly one employee is selected
    selected_employees = [row for row in doc.available_employees_table if row.select_employee]
    if len(selected_employees) != 1:
        frappe.throw("Please ensure exactly one employee is selected")
    
    # Check employee availability again
    emp_availability = get_available_employees(
        doc.project, doc.start_date, doc.end_date, 
        doc.allocation_percentage, doc.name
    )
    
    selected_emp_id = selected_employees[0].employee
    available_emp_ids = [emp["employee"] for emp in emp_availability["available_employees"]]
    
    if selected_emp_id not in available_emp_ids:
        frappe.throw("Selected employee is no longer available for this allocation")
    
    # Update status
    doc.status = "Approved"
    doc.save()
    
    # Submit the document to create project assignment
    doc.submit()
    
    # Send notification to requester
    send_approval_notification(doc)
    
    return {"status": "success", "message": "Request approved successfully"}

@frappe.whitelist()
def reject_request(name, rejection_reason):
    """Reject allocation request - CGO only"""
    if not frappe.user.has_role('CGO'):
        frappe.throw("Only CGO can reject resource allocations")
    
    doc = frappe.get_doc("Resource Allocation", name)
    
    # Update status and add rejection reason to notes
    doc.status = "Rejected"
    doc.notes = f"{doc.notes or ''}\n\nRejection Reason: {rejection_reason}"
    doc.save()
    
    # Send notification to requester
    send_rejection_notification(doc, rejection_reason)
    
    return {"status": "success", "message": "Request rejected"}

def send_notification_to_cgo(doc):
    """Send notification to CGO when new request is submitted"""
    cgo_users = frappe.get_all("Has Role", 
        filters={"role": "CGO"}, 
        fields=["parent"]
    )
    
    for user in cgo_users:
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"New Resource Allocation Request: {doc.name}",
            "for_user": user.parent,
            "type": "Alert",
            "document_type": "Resource Allocation",
            "document_name": doc.name,
            "email_content": f"""
                A new resource allocation request has been submitted:
                
                Request: {doc.name}
                Project: {doc.project_name}
                Requested By: {doc.requested_by}
                Period: {doc.start_date} to {doc.end_date}
                Allocation: {doc.allocation_percentage}%
                
                Please review and approve/reject the request.
            """
        }).insert(ignore_permissions=True)

def send_approval_notification(doc):
    """Send notification when request is approved"""
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": f"Resource Allocation Approved: {doc.name}",
        "for_user": doc.requested_by,
        "type": "Success",
        "document_type": "Resource Allocation",
        "document_name": doc.name,
        "email_content": f"""
            Your resource allocation request has been approved:
            
            Request: {doc.name}
            Project: {doc.project_name}
            Employee: {doc.employee_name}
            Period: {doc.start_date} to {doc.end_date}
            Allocation: {doc.allocation_percentage}%
            
            A project assignment has been created automatically.
        """
    }).insert(ignore_permissions=True)

def send_rejection_notification(doc, rejection_reason):
    """Send notification when request is rejected"""
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": f"Resource Allocation Rejected: {doc.name}",
        "for_user": doc.requested_by,
        "type": "Error",
        "document_type": "Resource Allocation",
        "document_name": doc.name,
        "email_content": f"""
            Your resource allocation request has been rejected:
            
            Request: {doc.name}
            Project: {doc.project_name}
            Period: {doc.start_date} to {doc.end_date}
            Allocation: {doc.allocation_percentage}%
            
            Reason: {rejection_reason}
            
            Please contact your manager for more details.
        """
    }).insert(ignore_permissions=True)
