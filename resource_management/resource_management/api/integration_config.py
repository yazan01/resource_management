# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, today, add_days

def employee_hourly_rate_hook(employee, args):
    """Hook to calculate employee hourly rate for salary calculations"""
    # Check if salary components already include this
    if not args.get("include_resource_allocation", 0):
        return args
    
    # Get employee hourly rate from employee doctype
    hourly_rate = frappe.db.get_value("Employee", employee, "hourly_cost_rate")
    
    if not hourly_rate:
        return args
    
    # Return for salary calculation
    args["hourly_rate"] = flt(hourly_rate)
    return args

def project_costing_hook(project, args):
    """Hook to include resource allocation costs in project costing"""
    if not project:
        return args
    
    # Get total resource costs from project assignments
    resource_costs = frappe.db.sql("""
        SELECT SUM(estimated_total_cost) as total_cost
        FROM `tabProject Assignment`
        WHERE project = %s
        AND docstatus = 1
        AND status = 'Active'
    """, project, as_dict=1)
    
    if resource_costs and resource_costs[0].total_cost:
        args["resource_costs"] = flt(resource_costs[0].total_cost)
    else:
        args["resource_costs"] = 0
    
    return args

def update_project_costing():
    """Scheduled job to update project costing based on resource allocations"""
    # Get all active projects
    projects = frappe.get_all("Project", filters={"status": "Open"})
    
    for project_info in projects:
        project = project_info.name
        
        # Get total resource costs for this project
        resource_costs = frappe.db.sql("""
            SELECT SUM(estimated_total_cost) as total_cost
            FROM `tabProject Assignment`
            WHERE project = %s
            AND docstatus = 1
            AND status = 'Active'
        """, project, as_dict=1)
        
        if resource_costs and resource_costs[0].total_cost:
            # Update project with calculated resource costs
            frappe.db.set_value("Project", project, "estimated_resource_cost", 
                                flt(resource_costs[0].total_cost))
            
            # Update total cost
            current_costing = frappe.db.get_value("Project", project, "estimated_costing") or 0
            total_cost = flt(current_costing) + flt(resource_costs[0].total_cost)
            frappe.db.set_value("Project", project, "total_costing", total_cost)