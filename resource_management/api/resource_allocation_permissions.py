# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe import _

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
    """
    Validate status changes in Resource Allocation
    Called from hooks.py on document validate
    """
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
    """
    Before save hook for Resource Allocation
    Called from hooks.py before document save
    """
    
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
    """
    On submit hook for Resource Allocation
    Called from hooks.py when document is submitted
    """
    
    # Only allow submission of approved documents
    if doc.status != "Approved":
        frappe.throw(_("Only approved resource allocations can be submitted"))
    
    # Only CGO can submit
    if not frappe.user.has_role('CGO') and not frappe.user.has_role('System Manager'):
        frappe.throw(_("Only CGO can submit resource allocations"))
    
    # Create Project Assignment automatically
    create_project_assignment_on_submit(doc)

def on_update_after_submit_resource_allocation(doc, method):
    """Handle updates after document submission"""
    
    # Log the submission
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Resource Allocation",
        "reference_name": doc.name,
        "content": f"Resource Allocation submitted and Project Assignment created"
    }).insert(ignore_permissions=True)

def on_cancel_resource_allocation(doc, method):
    """Handle document cancellation"""
    
    # Only System Manager and CGO can cancel
    if not (frappe.user.has_role('System Manager') or frappe.user.has_role('CGO')):
        frappe.throw(_("Only System Manager or CGO can cancel resource allocations"))
    
    # Cancel related Project Assignment
    project_assignments = frappe.get_all("Project Assignment", 
        filters={"allocation_reference": doc.name})
    
    for pa in project_assignments:
        pa_doc = frappe.get_doc("Project Assignment", pa.name)
        if pa_doc.docstatus == 1:  # If submitted
            pa_doc.cancel()

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

# Scheduled task functions (called from hooks.py scheduler_events)

def send_pending_approval_reminders():
    """Send reminders for pending approvals (daily task)"""
    
    # Get requests pending for more than 24 hours
    pending_requests = frappe.get_all("Resource Allocation", 
        filters={
            "status": "Requested",
            "modified": ["<", frappe.utils.add_hours(frappe.utils.now(), -24)]
        },
        fields=["name", "project", "requested_by", "creation"]
    )
    
    if not pending_requests:
        return
    
    # Get CGO users
    cgo_users = frappe.get_all("Has Role", 
        filters={"role": "CGO"}, 
        fields=["parent"]
    )
    
    # Send reminder notifications
    for request in pending_requests:
        for cgo in cgo_users:
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Reminder: Pending Resource Allocation - {request.name}",
                "for_user": cgo.parent,
                "type": "Alert",
                "document_type": "Resource Allocation",
                "document_name": request.name,
                "email_content": f"""
                    This resource allocation request has been pending approval for more than 24 hours:
                    
                    Request: {request.name}
                    Submitted: {request.creation}
                    Requested by: {frappe.get_value('User', request.requested_by, 'full_name')}
                    
                    Please review and take action.
                """
            }).insert(ignore_permissions=True)

def send_allocation_ending_notifications():
    """Send notifications for allocations ending soon (daily task)"""
    
    # Get allocations ending in 3 days
    ending_soon = frappe.get_all("Resource Allocation",
        filters={
            "status": "Approved",
            "docstatus": 1,
            "end_date": frappe.utils.add_days(frappe.utils.today(), 3)
        },
        fields=["name", "project", "employee", "requested_by", "end_date"]
    )
    
    # Send notifications
    for allocation in ending_soon:
        # Notify requester
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"Resource Allocation Ending Soon - {allocation.name}",
            "for_user": allocation.requested_by,
            "type": "Alert",
            "document_type": "Resource Allocation",
            "document_name": allocation.name,
            "email_content": f"""
                Your resource allocation is ending in 3 days:
                
                Allocation: {allocation.name}
                Project: {allocation.project}
                Employee: {frappe.get_value('Employee', allocation.employee, 'employee_name')}
                End Date: {allocation.end_date}
                
                Please plan accordingly or request an extension if needed.
            """
        }).insert(ignore_permissions=True)

def generate_weekly_reports():
    """Generate weekly resource allocation reports (weekly task)"""
    # Implementation for weekly reporting
    pass

def archive_old_allocations():
    """Archive old completed allocations (monthly task)"""
    # Implementation for archiving old records
    pass