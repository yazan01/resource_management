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

# Rest of the file remains the same...
