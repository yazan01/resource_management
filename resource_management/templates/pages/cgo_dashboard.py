# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate, flt

def get_context(context):
    context.no_cache = 1
    context.show_sidebar = True
    
    # Get filter values
    department = frappe.form_dict.get("department")
    project = frappe.form_dict.get("project")
    status = frappe.form_dict.get("status")
    
    # Set default date filters - next 30 days
    today_date = getdate(today())
    end_date = add_days(today_date, 30)
    
    context.dashboard_data = {
        "ending_soon": get_assignments_ending_soon(today_date, end_date, department, project),
        "unallocated": get_unallocated_employees(department),
        "allocation_requests": get_resource_allocation_requests(status),
        "current_allocations": get_current_allocations(department, project)
    }
    
    context.allocation_summary = get_allocation_summary()
    context.filters = {
        "departments": frappe.get_all("Department", fields=["name"]),
        "projects": frappe.get_all("Project", fields=["name"]),
        "current_department": department or "",
        "current_project": project or "",
        "current_status": status or ""
    }
    
    return context