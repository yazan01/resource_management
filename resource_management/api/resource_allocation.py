# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, flt

@frappe.whitelist()
def get_permission_query_conditions(user):
    """
    Permission query conditions for Resource Allocation List View
    Controls which documents appear in the list based on user role
    """
    if not user:
        user = frappe.session.user
    
    # System Manager sees all
    if frappe.user.has_role('System Manager', user):
        return ""
    
    # CGO sees all documents
    if frappe.user.has_role('CGO', user):
        return ""
    
    # Regular employees see only their own requests
    return f"(`tabResource Allocation`.`requested_by` = '{user}')"

@frappe.whitelist()
def has_permission(doc, user=None, permission_type=None):
    """
    Custom permission logic for Resource Allocation documents
    Controls read, write, create, delete, submit permissions
    """
    if not user:
        user = frappe.session.user
    
    # System Manager has all permissions
    if frappe.user.has_role('System Manager', user):
        return True
    
    # Handle new documents (not saved yet)
    if not doc or not hasattr(doc, 'name') or not doc.name:
        # Anyone can create new documents
        if permission_type == 'create':
            return True
        return True
    
    # Get document status
    status = getattr(doc, 'status', None)
    requested_by = getattr(doc, 'requested_by', None)
    
    # Permission logic based on status and user role
    if status == "Draft":
        return handle_draft_permissions(doc, user, permission_type, requested_by)
    elif status == "Requested":
        return handle_requested_permissions(doc, user, permission_type, requested_by)
    elif status in ["Approved", "Rejected"]:
        return handle_final_permissions(doc, user, permission_type, requested_by)
    
    # Default: allow read access
    return permission_type == 'read'

def handle_draft_permissions(doc, user, permission_type, requested_by):
    """Handle permissions for Draft status documents"""
    
    # CGO cannot edit draft documents (they shouldn't interfere at this stage)
    if frappe.user.has_role('CGO', user):
        if permission_type in ['write', 'delete']:
            return False
        return True  # Can read
    
    # Owner/requester can edit and delete draft documents
    if requested_by == user:
        if permission_type in ['read', 'write', 'delete']:
            return True
        if permission_type == 'submit':
            return False  # Draft documents don't get submitted, they get "requested"
    
    # Others can only read
    return permission_type == 'read'

def handle_requested_permissions(doc, user, permission_type, requested_by):
    """Handle permissions for Requested status documents"""
    
    # CGO can approve/reject (submit) and read
    if frappe.user.has_role('CGO', user):
        if permission_type in ['read', 'submit']:
            return True
        if permission_type in ['write', 'delete']:
            return False  # No editing allowed, only approve/reject
    
    # Owner/requester can only read (no editing after request)
    if requested_by == user:
        if permission_type == 'read':
            return True
        return False  # Cannot edit, delete, or submit
    
    # Others can only read
    return permission_type == 'read'

def handle_final_permissions(doc, user, permission_type, requested_by):
    """Handle permissions for Approved/Rejected status documents"""
    
    # No one can edit approved/rejected documents
    if permission_type in ['write', 'delete', 'submit']:
        return False
    
    # Everyone can read final documents
    return permission_type == 'read'

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
        doc.request_date = frappe.utils.today()
    
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

def on_update_after_submit_resource_allocation(doc, method):
    """Handle updates after document submission"""
    pass

def on_cancel_resource_allocation(doc, method):
    """Handle document cancellation"""
    
    # Only System Manager and CGO can cancel
    if not (frappe.user.has_role('System Manager') or frappe.user.has_role('CGO')):
        frappe.throw(_("Only System Manager or CGO can cancel resource allocations"))

def send_pending_approval_reminders():
    """Send reminders for pending approvals (daily task)"""
    pass

def send_allocation_ending_notifications():
    """Send notifications for allocations ending soon (daily task)"""
    pass

def generate_weekly_reports():
    """Generate weekly resource allocation reports (weekly task)"""
    pass

def archive_old_allocations():
    """Archive old completed allocations (monthly task)"""
    pass

@frappe.whitelist()
def get_available_employees(project, start_date, end_date, allocation_percentage, current_allocation=""):
    """Get list of available and unavailable employees for the given period"""
    
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
            SELECT SUM(allocation_percentage) as total_allocation
            FROM `tabResource Allocation`
            WHERE employee = %s AND status IN ('Approved', 'Requested')
            AND ((start_date BETWEEN %s AND %s) OR (end_date BETWEEN %s AND %s) 
                OR (start_date <= %s AND end_date >= %s))
            AND name != %s
        """, (emp.name, start_date, end_date, start_date, end_date, 
              start_date, end_date, current_allocation or ""), as_dict=1)
        
        current_allocation_pct = flt(overlapping_allocations[0].total_allocation or 0)
        available_allocation_pct = 100 - current_allocation_pct
        
        # Calculate estimated cost
        working_days = date_diff(end_date, start_date) + 1
        working_hours = working_days * 8  # 8 hours per day
        allocated_hours = working_hours * (flt(allocation_percentage) / 100)
        estimated_cost = allocated_hours * flt(emp.hourly_cost_rate or 0)
        
        emp_data = {
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "department": emp.department,
            "current_allocation": current_allocation_pct,
            "available_allocation": available_allocation_pct,
            "hourly_cost_rate": flt(emp.hourly_cost_rate or 0),
            "estimated_cost": flt(estimated_cost, 2)
        }
        
        # Check if employee is available for the requested allocation
        if available_allocation_pct >= flt(allocation_percentage):
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
    """Submit allocation request - Employee role"""
    doc = frappe.get_doc("Resource Allocation", name)
    
    # Validate permissions
    if not doc.has_permission("write"):
        frappe.throw("You don't have permission to modify this document")
    
    # Validate document is in Draft status
    if doc.status != "Draft":
        frappe.throw("Only draft allocations can be requested")
    
    # Set the selected employee in the table
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
    
    # Validate document is in Requested status
    if doc.status != "Requested":
        frappe.throw("Only requested allocations can be approved")
    
    # Validate that exactly one employee is selected
    selected_employees = [row for row in doc.available_employees_table if row.select_employee]
    if len(selected_employees) != 1:
        frappe.throw("Please ensure exactly one employee is selected")
    
    # Re-check employee availability
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
    
    return {"status": "success", "message": "Request approved and submitted successfully"}

@frappe.whitelist() 
def reject_request(name, rejection_reason):
    """Reject allocation request - CGO only"""
    if not frappe.user.has_role('CGO'):
        frappe.throw("Only CGO can reject resource allocations")
    
    doc = frappe.get_doc("Resource Allocation", name)
    
    # Validate document is in Requested status
    if doc.status != "Requested":
        frappe.throw("Only requested allocations can be rejected")
    
    # Update status and add rejection reason to notes
    doc.status = "Rejected"
    current_notes = doc.notes or ""
    rejection_note = f"\n\nRejected on {frappe.utils.today()} by {frappe.session.user}\nReason: {rejection_reason}"
    doc.notes = current_notes + rejection_note
    doc.save()
    
    # Send notification to requester
    send_rejection_notification(doc, rejection_reason)
    
    return {"status": "success", "message": "Request rejected successfully"}

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
                Project: {doc.project_name or doc.project}
                Requested By: {frappe.get_value('User', doc.requested_by, 'full_name')}
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
            Project: {doc.project_name or doc.project}
            Employee: {doc.employee_name or doc.employee}
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
            Project: {doc.project_name or doc.project}
            Period: {doc.start_date} to {doc.end_date}
            Allocation: {doc.allocation_percentage}%
            
            Reason: {rejection_reason}
            
            Please contact your manager for more details.
        """
    }).insert(ignore_permissions=True)
