# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def before_install():
    """Setup tasks before app installation"""
    pass

def after_install():
    """Setup tasks after app installation"""
    # Create custom fields in Project doctype
    create_project_custom_fields()
    
    # Create custom fields in Employee doctype
    create_employee_custom_fields()
    
    # Create CGO Role if it doesn't exist
    create_cgo_role()
    
    # Create dashboard page
    create_cgo_dashboard_page()
    
    # Create notification configurations
    setup_notifications()

def create_project_custom_fields():
    """Create custom fields in Project doctype"""
    custom_fields = [
        {
            'fieldname': 'estimated_resource_cost',
            'label': 'Estimated Resource Cost',
            'fieldtype': 'Currency',
            'insert_after': 'estimated_costing',
            'read_only': 1,
            'description': 'Cost of allocated resources on this project',
        },
        {
            'fieldname': 'resource_allocation_sb',
            'label': 'Resource Allocation',
            'fieldtype': 'Section Break',
            'insert_after': 'estimated_resource_cost',
        },
        {
            'fieldname': 'project_assignments',
            'label': 'Project Assignments',
            'fieldtype': 'Table MultiSelect',  # Changed from 'Table' to 'Table MultiSelect'
            'options': 'Project Assignment',
            'insert_after': 'resource_allocation_sb',
            'read_only': 1,
        }
    ]
    
    for field in custom_fields:
        create_custom_field('Project', field)

def create_employee_custom_fields():
    """Create custom fields in Employee doctype"""
    custom_fields = [
        {
            'fieldname': 'hourly_cost_rate',
            'label': 'Hourly Cost Rate',
            'fieldtype': 'Currency',
            'insert_after': 'salary_mode',
            'description': 'Hourly cost rate for resource allocation',
        },
        {
            'fieldname': 'resource_allocation_sb',
            'label': 'Resource Allocation',
            'fieldtype': 'Section Break',
            'insert_after': 'attendance_device_id',
        },
        {
            'fieldname': 'current_allocations',
            'label': 'Current Allocations',
            'fieldtype': 'Table MultiSelect',  # Changed from 'Table' to 'Table MultiSelect'
            'options': 'Project Assignment',
            'insert_after': 'resource_allocation_sb',
            'read_only': 1,
        }
    ]
    
    for field in custom_fields:
        create_custom_field('Employee', field)

def create_cgo_role():
    """Create CGO Role if it doesn't exist"""
    if not frappe.db.exists("Role", "CGO"):
        role = frappe.new_doc("Role")
        role.role_name = "CGO"
        role.desk_access = 1
        role.disabled = 0
        role.description = "Chief Growth Officer - responsible for resource allocation"
        role.save()
        
        # Set permissions for CGO role
        setup_cgo_permissions()


# This is the implementation for the dashboard function in install.py

def create_cgo_dashboard_page():
    """Create a dashboard page for resource management"""
    if frappe.db.exists("Dashboard", "Resource Management"):
        # Dashboard already exists
        return
    
    # Create new dashboard
    dashboard = frappe.new_doc("Dashboard")
    dashboard.dashboard_name = "Resource Management"
    dashboard.dashboard_title = "Resource Management"
    dashboard.layout_type = "Grid"
    dashboard.is_default = 0
    dashboard.is_standard = 0
    
    # Add charts
    charts = [
        {
            "chart_name": "Resource Allocation by Project",
            "chart_type": "Donut",
            "data_source": "Resource Allocation by Project",
            "width": "Full",
            "height": "Medium" 
        },
        {
            "chart_name": "Resource Allocation Timeline",
            "chart_type": "Line",
            "data_source": "Resource Allocation Timeline",
            "width": "Half",
            "height": "Medium"
        },
        {
            "chart_name": "Employee Utilization",
            "chart_type": "Bar",
            "data_source": "Employee Utilization",
            "width": "Half", 
            "height": "Medium"
        }
    ]
    
    for chart_info in charts:
        # Create chart if it doesn't exist
        if not frappe.db.exists("Dashboard Chart", chart_info["chart_name"]):
            create_dashboard_chart(chart_info)
        
        # Add chart to dashboard
        dashboard.append("charts", {
            "chart": chart_info["chart_name"],
            "width": chart_info["width"],
            "height": chart_info["height"]
        })
    
    # Add shortcuts to relevant pages
    shortcuts = [
        {
            "type": "DocType",
            "doc_view": "List",
            "link_to": "Resource Allocation",
            "label": "Resource Allocations"
        },
        {
            "type": "DocType", 
            "doc_view": "List",
            "link_to": "Project Assignment",
            "label": "Project Assignments"
        },
        {
            "type": "DocType",
            "doc_view": "List", 
            "link_to": "Project",
            "label": "Projects"
        },
        {
            "type": "DocType",
            "doc_view": "Report",
            "link_to": "Resource Allocation",
            "label": "Allocation Reports"
        }
    ]
    
    for shortcut in shortcuts:
        dashboard.append("shortcuts", {
            "type": shortcut["type"],
            "document_type": shortcut["link_to"],
            "doc_view": shortcut["doc_view"],
            "label": shortcut["label"]
        })
    
    dashboard.save()
    
    # Set dashboard access for CGO and other relevant roles
    setup_dashboard_access(dashboard.name)
    
    return dashboard.name

def create_dashboard_chart(chart_info):
    """Create a dashboard chart for resource management"""
    chart = frappe.new_doc("Dashboard Chart")
    chart.chart_name = chart_info["chart_name"]
    chart.chart_type = chart_info["chart_type"]
    chart.is_standard = 0
    chart.timeseries = 1 if chart_info["chart_type"] == "Line" else 0
    
    # Configure data source based on chart type
    if chart_info["data_source"] == "Resource Allocation by Project":
        chart.based_on = "sum"
        chart.document_type = "Resource Allocation"
        chart.value_based_on = "estimated_total_cost"
        chart.group_by_type = "Count"
        chart.group_by_based_on = "project"
        chart.filters_json = '{"status": "Approved"}'
        chart.chart_type = "Donut"
        chart.timeseries = 0
        chart.time_interval = "Yearly"
        chart.timespan = "Last Year"
        chart.color = "#5e64ff"
        chart.custom_options = """{
            "legend": {"position": "bottom"},
            "title": {"text": "Resource Cost by Project"},
            "tooltip": {"format": "Currency"}
        }"""
    
    elif chart_info["data_source"] == "Resource Allocation Timeline":
        chart.based_on = "creation"
        chart.document_type = "Resource Allocation"
        chart.value_based_on = "allocation_percentage"
        chart.chart_type = "Line"
        chart.time_interval = "Weekly"
        chart.timespan = "Last Quarter"
        chart.color = "#7cd6fd"
        chart.custom_options = """{
            "title": {"text": "Resource Allocation Over Time"},
            "xAxis": {"title": {"text": "Date"}},
            "yAxis": {"title": {"text": "Allocation %"}}
        }"""
    
    elif chart_info["data_source"] == "Employee Utilization":
        chart.based_on = "sum"
        chart.document_type = "Project Assignment"
        chart.value_based_on = "allocation_percentage"
        chart.group_by_type = "AVG"
        chart.group_by_based_on = "employee"
        chart.filters_json = '{"status": "Active"}'
        chart.chart_type = "Bar"
        chart.timeseries = 0
        chart.color = "#4caead"
        chart.custom_options = """{
            "title": {"text": "Employee Utilization (%)"},
            "xAxis": {"title": {"text": "Employee"}},
            "yAxis": {"title": {"text": "Average Allocation %"}, "max": 100}
        }"""
    
    chart.save()
    return chart.name

def setup_dashboard_access(dashboard_name):
    """Set up access to the dashboard for relevant roles"""
    roles = ["CGO", "HR Manager", "Projects Manager", "System Manager"]
    
    for role in roles:
        if not frappe.db.exists("Role", role):
            continue
            
        if not frappe.db.exists("Dashboard Permission", 
                               {"dashboard": dashboard_name, "role": role}):
            perm = frappe.new_doc("Dashboard Permission")
            perm.dashboard = dashboard_name
            perm.role = role
            perm.save()

def setup_cgo_permissions():
    """Set up permissions for the CGO role"""
    # Permission for Resource Allocation
    add_permission("Resource Allocation", "CGO", {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 0,
        "submit": 1,
        "cancel": 1,
        "report": 1,
        "email": 1,
        "export": 1,
        "print": 1,
        "share": 1
    })
    
    # Permission for Project Assignment
    add_permission("Project Assignment", "CGO", {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 0,
        "submit": 1,
        "cancel": 1,
        "report": 1,
        "email": 1,
        "export": 1,
        "print": 1,
        "share": 1
    })
    
    # Permission for Project
    add_permission("Project", "CGO", {
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 0,
        "report": 1,
        "email": 1,
        "export": 1,
        "print": 1,
        "share": 1
    })
    
    # Permission for Employee
    add_permission("Employee", "CGO", {
        "read": 1,
        "write": 0,
        "create": 0,
        "delete": 0,
        "report": 1,
        "email": 1,
        "export": 1,
        "print": 1,
        "share": 0
    })

def add_permission(doctype, role, permissions):
    """Add role permission for a doctype"""
    for perm_type, value in permissions.items():
        if value:
            if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, perm_type: value}):
                # Check if permission exists
                existing_perms = frappe.db.get_all(
                    "Custom DocPerm", 
                    filters={"parent": doctype, "role": role},
                    fields=["name", perm_type]
                )
                
                if existing_perms:
                    # Update existing permission
                    frappe.db.set_value("Custom DocPerm", existing_perms[0].name, perm_type, value)
                else:
                    # Create new permission
                    perm = frappe.new_doc("Custom DocPerm")
                    perm.parent = doctype
                    perm.parenttype = "DocType"
                    perm.parentfield = "permissions"
                    perm.role = role
                    
                    # Set all permission flags from the permissions dict
                    for p_type, p_value in permissions.items():
                        setattr(perm, p_type, p_value)
                    
                    perm.save()

def setup_notifications():
    """Setup email notifications for resource management"""
    # Notification for new allocation request
    if not frappe.db.exists("Notification", "New Resource Allocation Request"):
        notification = frappe.new_doc("Notification")
        notification.name = "New Resource Allocation Request"
        notification.subject = "New Resource Allocation Request: {{ doc.name }}"
        notification.document_type = "Resource Allocation"
        notification.event = "New"
        notification.send_to_all_assignees = 0
        notification.set("recipients", [
            {"receiver_by_role": "HR Manager"},
            {"receiver_by_role": "CGO"}
        ])
        notification.message = """
        <p>A new resource allocation request has been submitted:</p>
        <ul>
            <li>Employee: {{ doc.employee_name }}</li>
            <li>Project: {{ doc.project_name }}</li>
            <li>Start Date: {{ doc.start_date }}</li>
            <li>End Date: {{ doc.end_date }}</li>
            <li>Allocation %: {{ doc.allocation_percentage }}</li>
            <li>Requested By: {{ doc.requested_by }}</li>
        </ul>
        <p>Please review and take action.</p>
        """
        notification.save()
    
    # Notification for allocation approval
    if not frappe.db.exists("Notification", "Resource Allocation Approved"):
        notification = frappe.new_doc("Notification")
        notification.name = "Resource Allocation Approved"
        notification.subject = "Resource Allocation Approved: {{ doc.name }}"
        notification.document_type = "Resource Allocation"
        notification.event = "Value Change"
        notification.value_changed = "status"
        notification.send_to_all_assignees = 0
        notification.set("recipients", [
            {"receiver_by_document_field": "requested_by"}
        ])
        notification.condition = "doc.status == 'Approved'"
        notification.message = """
        <p>Your resource allocation request has been approved:</p>
        <ul>
            <li>Employee: {{ doc.employee_name }}</li>
            <li>Project: {{ doc.project_name }}</li>
            <li>Start Date: {{ doc.start_date }}</li>
            <li>End Date: {{ doc.end_date }}</li>
            <li>Allocation %: {{ doc.allocation_percentage }}</li>
        </ul>
        """
        notification.save()
    
    # Notification for allocation rejection
    if not frappe.db.exists("Notification", "Resource Allocation Rejected"):
        notification = frappe.new_doc("Notification")
        notification.name = "Resource Allocation Rejected"
        notification.subject = "Resource Allocation Rejected: {{ doc.name }}"
        notification.document_type = "Resource Allocation"
        notification.event = "Value Change"
        notification.value_changed = "status"
        notification.send_to_all_assignees = 0
        notification.set("recipients", [
            {"receiver_by_document_field": "requested_by"}
        ])
        notification.condition = "doc.status == 'Rejected'"
        notification.message = """
        <p>Your resource allocation request has been rejected:</p>
        <ul>
            <li>Employee: {{ doc.employee_name }}</li>
            <li>Project: {{ doc.project_name }}</li>
            <li>Start Date: {{ doc.start_date }}</li>
            <li>End Date: {{ doc.end_date }}</li>
            <li>Allocation %: {{ doc.allocation_percentage }}</li>
        </ul>
        <p>Please check the notes field for the reason of rejection.</p>
        """
        notification.save()
