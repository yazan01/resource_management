# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, flt, getdate, today
from frappe import _

@frappe.whitelist()
def get_permission_query_conditions(user):
    """
    Permission query conditions for Resource Allocation List View
    """
    try:
        if not user:
            user = frappe.session.user or "Guest"
        
        if user == "Guest":
            return "1=0"  # No access for guests
        
        # Get user roles safely
        user_roles = frappe.get_roles(user) if user != "Guest" else []
        
        # System Manager sees all
        if "System Manager" in user_roles:
            return ""
        
        # CGO sees all documents
        if "CGO" in user_roles:
            return ""
        
        # Regular employees see only their own requests
        return f"(`tabResource Allocation`.`requested_by` = '{frappe.db.escape(user)}')"
        
    except Exception as e:
        frappe.log_error(f"Permission Query Error: {str(e)}", "Resource Allocation Permissions")
        return "1=0"  # Deny access on error

@frappe.whitelist()
def has_permission(doc, user=None, permission_type=None):
    """
    Custom permission logic for Resource Allocation documents
    """
    try:
        if not user:
            user = frappe.session.user or "Guest"
        
        if user == "Guest":
            return False
        
        # Get user roles safely
        user_roles = frappe.get_roles(user)
        
        # System Manager has all permissions
        if "System Manager" in user_roles:
            return True
        
        # Handle new documents (not saved yet)
        if not doc or not hasattr(doc, 'name') or not doc.name:
            return True  # Allow creation
        
        # Get document status
        status = getattr(doc, 'status', 'Draft')
        requested_by = getattr(doc, 'requested_by', None)
        
        # Permission logic based on status and user role
        if status == "Draft":
            return handle_draft_permissions(doc, user, permission_type, requested_by, user_roles)
        elif status == "Requested":
            return handle_requested_permissions(doc, user, permission_type, requested_by, user_roles)
        elif status in ["Approved", "Rejected"]:
            return handle_final_permissions(doc, user, permission_type, requested_by, user_roles)
        
        # Default: allow read access
        return permission_type == 'read'
        
    except Exception as e:
        frappe.log_error(f"Has Permission Error: {str(e)}", "Resource Allocation Permissions")
        return permission_type == 'read'  # Allow read on error

def handle_draft_permissions(doc, user, permission_type, requested_by, user_roles):
    """Handle permissions for Draft status documents"""
    
    # CGO can read but not edit draft documents
    if "CGO" in user_roles:
        return permission_type == 'read'
    
    # Owner/requester can edit and delete draft documents
    if requested_by == user:
        return permission_type in ['read', 'write', 'delete']
    
    # Others can only read
    return permission_type == 'read'

def handle_requested_permissions(doc, user, permission_type, requested_by, user_roles):
    """Handle permissions for Requested status documents"""
    
    # CGO can approve/reject and read
    if "CGO" in user_roles:
        return permission_type in ['read', 'write']  # Allow write for status change
    
    # Owner/requester can only read
    if requested_by == user:
        return permission_type == 'read'
    
    # Others can only read
    return permission_type == 'read'

def handle_final_permissions(doc, user, permission_type, requested_by, user_roles):
    """Handle permissions for Approved/Rejected status documents"""
    
    # CGO can still read and write (for notes)
    if "CGO" in user_roles:
        return permission_type in ['read', 'write']
    
    # Everyone else can only read
    return permission_type == 'read'

@frappe.whitelist()
def get_available_employees(project, start_date, end_date, allocation_percentage, current_allocation=""):
    """Get list of available and unavailable employees for the given period"""
    
    try:
        # Get all active employees
        employees = frappe.get_all("Employee", 
            filters={"status": "Active"},
            fields=["name", "employee_name", "department", "hourly_cost_rate"]
        )
        
        available_employees = []
        unavailable_employees = []
        
        for emp in employees:
            # Get current allocations for this employee in the period
            overlapping_allocations = frappe.db.sql("""
                SELECT SUM(pa.allocation_percentage) as total_allocation
                FROM `tabProject Assignment` pa
                WHERE pa.employee = %s AND pa.status = 'Active'
                AND pa.docstatus = 1
                AND ((pa.start_date BETWEEN %s AND %s) OR (pa.end_date BETWEEN %s AND %s) 
                    OR (pa.start_date <= %s AND pa.end_date >= %s))
                AND pa.allocation_reference != %s
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
    
    except Exception as e:
        frappe.log_error(f"Get Available Employees Error: {str(e)}", "Resource Allocation API")
        frappe.throw(_("Error loading available employees. Please try again."))

@frappe.whitelist()
def request_allocation(name, selected_employee):
    """Submit allocation request"""
    try:
        doc = frappe.get_doc("Resource Allocation", name)
        
        # Validate permissions
        if not has_permission(doc, frappe.session.user, "write"):
            frappe.throw(_("You don't have permission to modify this document"))
        
        # Validate document status
        if doc.status != "Draft":
            frappe.throw(_("Only draft allocations can be requested"))
        
        # Set the selected employee in the table
        employee_found = False
        for row in doc.available_employees_table:
            if row.employee == selected_employee:
                row.select_employee = 1
                employee_found = True
            else:
                row.select_employee = 0
        
        if not employee_found:
            frappe.throw(_("Selected employee not found in available employees list"))
        
        # Update status to Requested
        doc.status = "Requested"
        doc.save()
        
        # Send notification to CGO
        send_notification_to_cgo(doc)
        
        return {"status": "success", "message": "Request submitted successfully"}
    
    except Exception as e:
        frappe.log_error(f"Request Allocation Error: {str(e)}", "Resource Allocation API")
        frappe.throw(_("Error submitting request: {0}").format(str(e)))

@frappe.whitelist()
def approve_request(name):
    """Approve allocation request - CGO only"""
    try:
        if not frappe.user.has_role('CGO'):
            frappe.throw(_("Only CGO can approve resource allocations"))
        
        doc = frappe.get_doc("Resource Allocation", name)
        
        # Validate document status
        if doc.status != "Requested":
            frappe.throw(_("Only requested allocations can be approved"))
        
        # Validate that exactly one employee is selected
        selected_employees = [row for row in doc.available_employees_table if row.select_employee]
        if len(selected_employees) != 1:
            frappe.throw(_("Please ensure exactly one employee is selected"))
        
        # Check employee availability again
        emp_availability = get_available_employees(
            doc.project, doc.start_date, doc.end_date, 
            doc.allocation_percentage, doc.name
        )
        
        selected_emp_id = selected_employees[0].employee
        available_emp_ids = [emp["employee"] for emp in emp_availability["available_employees"]]
        
        if selected_emp_id not in available_emp_ids:
            frappe.throw(_("Selected employee is no longer available for this allocation"))
        
        # Update status
        doc.status = "Approved"
        doc.save()
        
        # Submit the document to create project assignment
        doc.submit()
        
        # Send notification to requester
        send_approval_notification(doc)
        
        return {"status": "success", "message": "Request approved successfully"}
    
    except Exception as e:
        frappe.log_error(f"Approve Request Error: {str(e)}", "Resource Allocation API")
        frappe.throw(_("Error approving request: {0}").format(str(e)))

@frappe.whitelist()
def reject_request(name, rejection_reason):
    """Reject allocation request - CGO only"""
    try:
        if not frappe.user.has_role('CGO'):
            frappe.throw(_("Only CGO can reject resource allocations"))
        
        doc = frappe.get_doc("Resource Allocation", name)
        
        # Validate document status
        if doc.status != "Requested":
            frappe.throw(_("Only requested allocations can be rejected"))
        
        # Update status and add rejection reason to notes
        doc.status = "Rejected"
        existing_notes = doc.notes or ""
        doc.notes = f"{existing_notes}\n\nRejection Reason ({today()}): {rejection_reason}"
        doc.save()
        
        # Send notification to requester
        send_rejection_notification(doc, rejection_reason)
        
        return {"status": "success", "message": "Request rejected"}
    
    except Exception as e:
        frappe.log_error(f"Reject Request Error: {str(e)}", "Resource Allocation API")
        frappe.throw(_("Error rejecting request: {0}").format(str(e)))

def send_notification_to_cgo(doc):
    """Send notification to CGO when new request is submitted"""
    try:
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
                    Requested By: {frappe.get_value('User', doc.requested_by, 'full_name')}
                    Period: {doc.start_date} to {doc.end_date}
                    Allocation: {doc.allocation_percentage}%
                    
                    Please review and approve/reject the request.
                """
            }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"CGO Notification Error: {str(e)}", "Resource Allocation Notifications")

def send_approval_notification(doc):
    """Send notification when request is approved"""
    try:
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
                Employee: {getattr(doc, 'employee_name', 'Selected Employee')}
                Period: {doc.start_date} to {doc.end_date}
                Allocation: {doc.allocation_percentage}%
                
                A project assignment has been created automatically.
            """
        }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Approval Notification Error: {str(e)}", "Resource Allocation Notifications")

def send_rejection_notification(doc, rejection_reason):
    """Send notification when request is rejected"""
    try:
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
    except Exception as e:
        frappe.log_error(f"Rejection Notification Error: {str(e)}", "Resource Allocation Notifications")

# Document event handlers

def validate_resource_allocation_status_change(doc, method):
    """Validate status changes in Resource Allocation"""
    if not doc.is_new():
        old_doc = doc.get_doc_before_save()
        if old_doc and old_doc.status != doc.status:
            
            # Validate Draft → Requested transition
            if old_doc.status == "Draft" and doc.status == "Requested":
                validate_draft_to_requested(doc)
            
            # Validate Requested → Approved/Rejected transition
            elif old_doc.status == "Requested" and doc.status in ["Approved", "Rejected"]:
                validate_requested_to_final(doc)
            
            # Prevent invalid status changes
            else:
                frappe.throw(_("Invalid status change from {0} to {1}").format(
                    old_doc.status, doc.status))

def validate_draft_to_requested(doc):
    """Validate Draft to Requested status change"""
    
    # Only the requester can request
    if doc.requested_by != frappe.session.user:
        frappe.throw(_("Only the requester can submit this allocation request"))
    
    # Validate that an employee is selected
    if not hasattr(doc, 'available_employees_table') or not doc.available_employees_table:
        frappe.throw(_("Please refresh the form to load available employees"))
    
    selected_employees = [row for row in doc.available_employees_table if row.select_employee]
    if len(selected_employees) != 1:
        frappe.throw(_("Please select exactly one employee before requesting"))
    
    # Validate selected employee is available
    selected_emp = selected_employees[0]
    if not selected_emp.is_available:
        frappe.throw(_("Selected employee {0} is not available for this allocation").format(
            selected_emp.employee_name))

def validate_requested_to_final(doc):
    """Validate Requested to Approved/Rejected status change"""
    
    # Only CGO can approve/reject
    if not frappe.user.has_role('CGO'):
        frappe.throw(_("Only CGO can approve or reject resource allocation requests"))
    
    # For approval, re-validate employee availability
    if doc.status == "Approved":
        selected_employees = [row for row in doc.available_employees_table if row.select_employee]
        if len(selected_employees) != 1:
            frappe.throw(_("Please ensure exactly one employee is selected"))

def before_save_resource_allocation(doc, method):
    """Before save hook for Resource Allocation"""
    
    # Set requested_by to current user for new documents
    if doc.is_new() and not doc.requested_by:
        doc.requested_by = frappe.session.user
    
    # Set request_date for new documents
    if doc.is_new() and not doc.request_date:
        doc.request_date = today()
    
    # Prevent modification of final status documents
    if not doc.is_new() and doc.status in ["Approved", "Rejected"]:
        if not frappe.user.has_role('System Manager'):
            old_doc = doc.get_doc_before_save()
            if old_doc and old_doc.status in ["Approved", "Rejected"]:
                frappe.throw(_("Cannot modify {0} resource allocations").format(
                    doc.status.lower()))

def on_submit_resource_allocation(doc, method):
    """On submit hook for Resource Allocation"""
    
    # Only allow submission of approved documents
    if doc.status != "Approved":
        frappe.throw(_("Only approved resource allocations can be submitted"))
    
    # Only CGO can submit
    if not frappe.user.has_role('CGO') and not frappe.user.has_role('System Manager'):
        frappe.throw(_("Only CGO can submit resource allocations"))
    
    # Create Project Assignment automatically
    create_project_assignment_on_submit(doc)

def create_project_assignment_on_submit(doc):
    """Create Project Assignment when Resource Allocation is submitted"""
    
    # Check if Project Assignment already exists
    existing_assignment = frappe.db.get_value("Project Assignment", {
        "allocation_reference": doc.name
    })
    
    if existing_assignment:
        frappe.msgprint(_("Project Assignment {0} already exists for this allocation").format(
            existing_assignment))
        return
    
    # Get selected employee
    selected_employees = [row for row in doc.available_employees_table if row.select_employee]
    if not selected_employees:
        frappe.throw(_("No employee selected for assignment"))
    
    selected_emp = selected_employees[0]
    
    # Create new Project Assignment
    try:
        project_assignment = frappe.new_doc("Project Assignment")
        project_assignment.project = doc.project
        project_assignment.employee = selected_emp.employee
        project_assignment.allocation_reference = doc.name
        project_assignment.start_date = doc.start_date
        project_assignment.end_date = doc.end_date
        project_assignment.allocation_percentage = doc.allocation_percentage
        project_assignment.estimated_total_cost = selected_emp.estimated_cost
        project_assignment.save()
        
        frappe.msgprint(_("Project Assignment {0} created successfully").format(
            project_assignment.name))
        
    except Exception as e:
        frappe.log_error(f"Failed to create Project Assignment: {str(e)}", 
                        "Resource Allocation Submit")
        frappe.throw(_("Failed to create Project Assignment. Please contact administrator."))
