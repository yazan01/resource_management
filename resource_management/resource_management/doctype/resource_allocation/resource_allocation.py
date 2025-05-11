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

    def update_project_allocations(project):
    """Update project's resource allocations"""
    if not frappe.db.exists("Project", project):
        return
    
    project_doc = frappe.get_doc("Project", project)
    
    # Get current active project assignments
    assignments = frappe.get_all("Project Assignment", 
        filters={
            "project": project,
            "status": "Active",
            "docstatus": 1
        },
        fields=["name", "employee", "start_date", "end_date", 
                "allocation_percentage", "estimated_total_cost"]
    )
    
    # Update the project document
    if hasattr(project_doc, "project_assignments"):
        # Clear existing assignments
        project_doc.project_assignments = []
        
        # Add current assignments - for Table MultiSelect, we only need the name of the linked document
        for assignment in assignments:
            project_doc.append("project_assignments", {
                "project_assignment": assignment.name  # This is the link field for Table MultiSelect
            })
        
        # Recalculate total resource cost
        total_cost = sum([flt(assignment.estimated_total_cost) for assignment in assignments])
        if hasattr(project_doc, "estimated_resource_cost"):
            project_doc.estimated_resource_cost = total_cost
        
        project_doc.save()

    def update_employee_allocations(employee):
    """Update employee's current allocations"""
    if not frappe.db.exists("Employee", employee):
        return
    
    employee_doc = frappe.get_doc("Employee", employee)
    
    # Get current active project assignments
    assignments = frappe.get_all("Project Assignment", 
        filters={
            "employee": employee,
            "status": "Active",
            "docstatus": 1
        },
        fields=["name", "project", "start_date", "end_date", 
                "allocation_percentage", "estimated_total_cost"]
    )
    
    # Update the employee document
    if hasattr(employee_doc, "current_allocations"):
        # Clear existing allocations
        employee_doc.current_allocations = []
        
        # Add current assignments - for Table MultiSelect, we only need the name of the linked document
        for assignment in assignments:
            employee_doc.append("current_allocations", {
                "project_assignment": assignment.name  # This is the link field for Table MultiSelect
            })
        
        employee_doc.save()
