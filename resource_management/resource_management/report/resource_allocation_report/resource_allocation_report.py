# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, add_months, get_first_day, get_last_day, flt, add_days

def execute(filters=None):
    if not filters:
        filters = {}
    
    # Set default dates if not provided
    if not filters.get("from_date"):
        filters["from_date"] = get_first_day(getdate())
    if not filters.get("to_date"):
        filters["to_date"] = get_last_day(getdate())
    
    # Get columns and data
    columns = get_columns(filters)
    data = get_data(filters)
    
    # Add chart and other report summary
    chart = get_chart(data, filters)
    report_summary = get_report_summary(data)
    
    return columns, data, None, chart, report_summary

def get_columns(filters):
    """Define columns for the report"""
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
            "fieldtype": "Link",
            "options": "Department",
            "width": 120
        },
        {
            "fieldname": "total_allocation",
            "label": _("Total Allocation %"),
            "fieldtype": "Percent",
            "width": 120
        }
    ]
    
    # Add date range columns
    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    
    # If date range is more than 31 days, group by month
    if (to_date - from_date).days > 31:
        # Add month columns
        current_date = get_first_day(from_date)
        while current_date <= to_date:
            month_last_day = get_last_day(current_date)
            month_name = current_date.strftime("%b %Y")
            columns.append({
                "fieldname": f"month_{current_date.strftime('%Y%m')}",
                "label": month_name,
                "fieldtype": "Percent",
                "width": 100
            })
            current_date = add_days(month_last_day, 1)
    else:
        # Add daily columns
        current_date = from_date
        while current_date <= to_date:
            date_str = current_date.strftime("%Y%m%d")
            date_label = current_date.strftime("%d-%b")
            columns.append({
                "fieldname": f"date_{date_str}",
                "label": date_label,
                "fieldtype": "Percent",
                "width": 80
            })
            current_date = add_days(current_date, 1)
    
    # Add project columns
    if filters.get("show_projects"):
        columns.append({
            "fieldname": "project_details",
            "label": _("Project Details"),
            "fieldtype": "Data",
            "width": 300
        })
    
    return columns