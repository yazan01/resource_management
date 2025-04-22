# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, add_days, today, flt, get_datetime

class ResourceAllocation(Document):
    def validate(self):
        self.validate_dates()
        self.validate_allocation_percentage()
        self.calculate_estimated_cost()
        
    def validate_dates(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            frappe.throw("End Date cannot be before Start Date")
            
    def validate_allocation_percentage(self):
        # Check if allocation percentage is between 0 and 100
        if self.allocation_percentage < 0 or self.allocation_percentage > 100:
            frappe.throw("Allocation Percentage must be between 0 and 100")
            
        # Check if employee is available for the requested period
        overlapping_allocations = frappe.db.sql("""
            SELECT name, allocation_percentage, project, start_date, end_date
            FROM `tabResource Allocation`
            WHERE employee = %s AND status = 'Approved'
            AND ((start_date BETWEEN %s AND %s) OR (end_date BETWEEN %s AND %s) 
                OR (start_date <= %s AND end_date >= %s))
            AND name != %s
        """, (self.employee, self.start_date, self.end_date, self.start_date, self.end_date, 
              self.start_date, self.end_date, self.name or ""), as_dict=1)
        
        # Calculate total allocation for each day in the period
        if overlapping_allocations:
            date_allocation_map = {}
            period_days = date_diff(self.end_date, self.start_date) + 1
            
            for i in range(period_days):
                check_date = add_days(self.start_date, i)
                date_allocation_map[check_date] = 0
                
                for allocation in overlapping_allocations:
                    if allocation.start_date <= check_date <= allocation.end_date:
                        date_allocation_map[check_date] += allocation.allocation_percentage
                        
                # Check if adding this allocation would exceed 100%
                if date_allocation_map[check_date] + self.allocation_percentage > 100:
                    frappe.throw(f"Employee {self.employee_name} is already allocated {date_allocation_map[check_date]}% on {check_date}. Cannot allocate more than 100%.")
    
    def calculate_estimated_cost(self):
        if not self.hourly_cost_rate:
            # Get hourly cost rate from employee
            employee_doc = frappe.get_doc("Employee", self.employee)
            self.hourly_cost_rate = employee_doc.get_hourly_rate()
        
        if self.hourly_cost_rate:
            # Calculate working days between start and end date
            # Assuming 8 working hours per day
            working_days = date_diff(self.end_date, self.start_date) + 1
            working_hours = working_days * 8
            
            # Calculate cost based on allocation percentage
            allocated_hours = working_hours * (self.allocation_percentage / 100)
            self.estimated_total_cost = flt(allocated_hours * self.hourly_cost_rate, 2)
    
    def on_submit(self):
        if self.status == "Approved":
            # Create Project Assignment
            self.create_project_assignment()
            
    def create_project_assignment(self):
        # Link this allocation to the project
        project_assignment = frappe.new_doc("Project Assignment")
        project_assignment.project = self.project
        project_assignment.employee = self.employee
        project_assignment.allocation_reference = self.name
        project_assignment.start_date = self.start_date
        project_assignment.end_date = self.end_date
        project_assignment.allocation_percentage = self.allocation_percentage
        project_assignment.save()