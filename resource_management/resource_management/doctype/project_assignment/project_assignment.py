# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, flt, getdate, today, add_days

class ProjectAssignment(Document):
    def validate(self):
        self.validate_dates()
        self.update_project_costs()
        
    def validate_dates(self):
        # Check if end date is after start date
        if self.end_date and self.start_date and self.end_date < self.start_date:
            frappe.throw("End Date cannot be before Start Date")
    
    def update_project_costs(self):
        if self.allocation_reference:
            # Get the allocation reference
            allocation = frappe.get_doc("Resource Allocation", self.allocation_reference)
            self.hourly_cost_rate = allocation.hourly_cost_rate
            self.estimated_total_cost = allocation.estimated_total_cost
    
    def on_update_after_submit(self):
        # Update any changes to the project costs
        self.update_project_costs()
    
    def on_submit(self):
        # Add this assignment's cost to the project
        project = frappe.get_doc("Project", self.project)
        if hasattr(project, "estimated_resource_cost"):
            project.estimated_resource_cost = flt(project.estimated_resource_cost) + flt(self.estimated_total_cost)
            project.save()
            
    def on_cancel(self):
        # Remove this assignment's cost from the project
        project = frappe.get_doc("Project", self.project)
        if hasattr(project, "estimated_resource_cost"):
            project.estimated_resource_cost = flt(project.estimated_resource_cost) - flt(self.estimated_total_cost)
            project.save()
    
    def is_active(self):
        """Check if this assignment is currently active"""
        today_date = getdate(today())
        return (getdate(self.start_date) <= today_date <= getdate(self.end_date))
    
    def get_remaining_days(self):
        """Get remaining days in this assignment"""
        today_date = getdate(today())
        if today_date > getdate(self.end_date):
            return 0
        elif today_date < getdate(self.start_date):
            return date_diff(self.end_date, self.start_date) + 1
        else:
            return date_diff(self.end_date, today_date)