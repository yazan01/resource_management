# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ResourceAllocationEmployee(Document):
    def validate(self):
        # Validate that only available employees can be selected
        if self.select_employee and not self.is_available:
            frappe.throw(f"Employee {self.employee_name} is not available for the requested allocation percentage")
    
    def before_save(self):
        # Calculate estimated cost when employee is selected
        if self.select_employee and self.hourly_cost_rate:
            parent = frappe.get_doc("Resource Allocation", self.parent)
            if parent.start_date and parent.end_date and parent.allocation_percentage:
                self.calculate_estimated_cost(parent)
    
    def calculate_estimated_cost(self, parent_doc):
        """Calculate estimated cost for this employee allocation"""
        from frappe.utils import date_diff, flt
        
        working_days = date_diff(parent_doc.end_date, parent_doc.start_date) + 1
        working_hours = working_days * 8  # 8 hours per day
        allocated_hours = working_hours * (flt(parent_doc.allocation_percentage) / 100)
        self.estimated_cost = flt(allocated_hours * flt(self.hourly_cost_rate), 2)