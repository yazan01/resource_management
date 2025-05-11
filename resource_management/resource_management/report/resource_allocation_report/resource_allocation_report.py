# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_days, date_diff, flt

def execute(filters=None):
    if not filters:
        filters = {}
        
    columns = get_columns()
    data = get_data(filters)
    
    chart_data = get_chart_data(data)
    
    return columns, data, None, chart_data

def get_columns():
    """Return columns for the report"""
    columns = [
        {
            "fieldname": "employee",
            "label": _("Employee ID"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 120
        },
        {
            "fieldname": "employee_name",
            "label": _("Employee Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "department",
            "label": _("Department"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "project",
            "label": _("Project"),
            "fieldtype": "Link",
            "options": "Project",
            "width": 120
        },
        {
            "fieldname": "project_name",
            "label": _("Project Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "start_date",
            "label": _("Start Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "end_date",
            "label": _("End Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "allocation_percentage",
            "label": _("Allocation %"),
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "fieldname": "status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "remaining_days",
            "label": _("Remaining Days"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "estimated_cost",
            "label": _("Estimated Cost"),
            "fieldtype": "Currency",
            "width": 120
        }
    ]
    
    return columns

def get_data(filters):
    """Get data based on filters"""
    conditions = get_conditions(filters)
    
    # Query for Project Assignments
    data = frappe.db.sql("""
        SELECT 
            pa.employee,
            emp.employee_name,
            emp.department,
            pa.project,
            proj.project_name,
            pa.start_date,
            pa.end_date,
            pa.allocation_percentage,
            pa.status,
            pa.estimated_total_cost as estimated_cost,
            pa.name as assignment_id
        FROM 
            `tabProject Assignment` pa
        LEFT JOIN 
            `tabEmployee` emp ON pa.employee = emp.name
        LEFT JOIN 
            `tabProject` proj ON pa.project = proj.name
        WHERE 
            pa.docstatus = 1
            {conditions}
        ORDER BY 
            pa.start_date DESC
    """.format(conditions=conditions), as_dict=1)
    
    # Calculate remaining days for each assignment
    today = getdate(nowdate())
    for row in data:
        end_date = getdate(row.end_date)
        
        if today > end_date:
            row.remaining_days = 0
        else:
            row.remaining_days = date_diff(end_date, today)
    
    return data

def get_conditions(filters):
    """Build conditions for SQL query based on filters"""
    conditions = []
    
    if filters.get("employee"):
        conditions.append(" AND pa.employee = '{0}'".format(filters.get("employee")))
    
    if filters.get("project"):
        conditions.append(" AND pa.project = '{0}'".format(filters.get("project")))
    
    if filters.get("department"):
        conditions.append(" AND emp.department = '{0}'".format(filters.get("department")))
    
    if filters.get("status"):
        conditions.append(" AND pa.status = '{0}'".format(filters.get("status")))
    
    if filters.get("from_date"):
        conditions.append(" AND pa.start_date >= '{0}'".format(filters.get("from_date")))
    
    if filters.get("to_date"):
        conditions.append(" AND pa.end_date <= '{0}'".format(filters.get("to_date")))
    
    return " ".join(conditions)

def get_chart_data(data):
    """Generate chart data for the report"""
    if not data:
        return None
    
    # Prepare data for Project-wise allocation chart
    projects = {}
    for row in data:
        project = row.project_name or row.project
        if project in projects:
            projects[project] += flt(row.estimated_cost)
        else:
            projects[project] = flt(row.estimated_cost)
    
    project_labels = list(projects.keys())
    project_values = [projects[project] for project in project_labels]
    
    chart = {
        "type": "donut",
        "data": {
            "labels": project_labels,
            "datasets": [
                {
                    "values": project_values
                }
            ]
        },
        "colors": ["#5e64ff", "#7cd6fd", "#4caead", "#ff5858", "#ffa00a", "#26be8d", "#99cd9e", "#e6a9a9"],
        "height": 300,
    }
    
    return chart
