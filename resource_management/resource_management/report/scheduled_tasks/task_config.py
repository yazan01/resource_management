# Copyright (c) 2023, Yazan Hamdan and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today, getdate, add_days, date_diff

def all():
    """Jobs to run on every scheduler iteration"""
    pass

def daily():
    """Jobs to run daily"""
    update_completed_assignments()
    send_upcoming_end_notifications()
    update_employee_availability()

def hourly():
    """Jobs to run hourly"""
    pass

def weekly():
    """Jobs to run weekly"""
    send_allocation_summary()

def monthly():
    """Jobs to run monthly"""
    generate_monthly_resource_report()

def update_completed_assignments():
    """Update assignments that have passed their end date"""
    # Get all active assignments that have ended
    ended_assignments = frappe.get_all("Project Assignment", 
        filters={
            "status": "Active",
            "end_date": ["<", today()],
            "docstatus": 1
        },
        fields=["name", "project", "employee"]
    )
    
    # Update status to completed
    for assignment in ended_assignments:
        try:
            doc = frappe.get_doc("Project Assignment", assignment.name)
            doc.status = "Completed"
            doc.save()
            frappe.db.commit()
            
            # Log the completion
            frappe.log_error(
                f"Automatically completed assignment {doc.name} for employee {doc.employee} on project {doc.project}",
                "Resource Assignment Update"
            )
        except Exception as e:
            frappe.log_error(
                f"Failed to complete assignment {assignment.name}: {str(e)}",
                "Resource Assignment Update Error"
            )

def send_upcoming_end_notifications():
    """Send notifications for assignments ending soon"""
    # Get assignments ending in the next 7 days
    today_date = getdate(today())
    upcoming_end = frappe.get_all("Project Assignment",
        filters={
            "status": "Active",
            "end_date": ["between", (today(), add_days(today(), 7))],
            "docstatus": 1
        },
        fields=["name", "project", "project_name", "employee", "employee_name", "end_date"]
    )
    
    # Send notifications
    for assignment in upcoming_end:
        days_left = date_diff(assignment.end_date, today_date)
        
        # Get project manager
        project_manager_email = frappe.db.get_value("Project", assignment.project, "project_manager_email")
        
        if project_manager_email:
            try:
                frappe.sendmail(
                    recipients=[project_manager_email],
                    subject=f"Resource Assignment Ending Soon: {assignment.name}",
                    message=f"""
                        <p>Hello,</p>
                        <p>This is to notify you that the following resource assignment is ending in {days_left} days:</p>
                        <ul>
                            <li>Project: {assignment.project_name}</li>
                            <li>Employee: {assignment.employee_name}</li>
                            <li>End Date: {assignment.end_date}</li>
                        </ul>
                        <p>Please take necessary action if the assignment needs to be extended.</p>
                        <p>Regards,<br>Resource Management System</p>
                    """
                )
            except Exception as e:
                frappe.log_error(
                    f"Failed to send notification for assignment {assignment.name}: {str(e)}",
                    "Resource Assignment Notification Error"
                )

def update_employee_availability():
    """Update employee availability calculation"""
    # Get all employees with hourly cost rate
    employees = frappe.get_all("Employee", 
        filters={"hourly_cost_rate": [">", 0]},
        fields=["name"]
    )
    
    today_date = getdate(today())
    
    # Update availability for each employee
    for emp in employees:
        try:
            # Get active assignments
            active_assignments = frappe.get_all("Project Assignment",
                filters={
                    "employee": emp.name,
                    "status": "Active",
                    "start_date": ["<=", today()],
                    "end_date": [">=", today()],
                    "docstatus": 1
                },
                fields=["allocation_percentage"]
            )
            
            # Calculate total allocation
            total_allocation = sum([a.allocation_percentage for a in active_assignments])
            
            # Update employee document if it has the field
            if frappe.db.exists("Custom Field", {"dt": "Employee", "fieldname": "current_allocation_percentage"}):
                frappe.db.set_value("Employee", emp.name, "current_allocation_percentage", total_allocation)
        
        except Exception as e:
            frappe.log_error(
                f"Failed to update availability for employee {emp.name}: {str(e)}",
                "Employee Availability Update Error"
            )

def send_allocation_summary():
    """Send weekly allocation summary to CGO and HR Manager"""
    # Get list of employees and their allocations
    employees_data = frappe.db.sql("""
        SELECT 
            e.name as employee,
            e.employee_name,
            e.department,
            COUNT(pa.name) as assignment_count,
            SUM(pa.allocation_percentage) as total_allocation
        FROM 
            `tabEmployee` e
        LEFT JOIN 
            `tabProject Assignment` pa ON e.name = pa.employee AND pa.status = 'Active' 
                AND pa.start_date <= CURDATE() AND pa.end_date >= CURDATE() AND pa.docstatus = 1
        WHERE 
            e.status = 'Active'
        GROUP BY 
            e.name
        ORDER BY 
            total_allocation DESC
    """, as_dict=1)
    
    # Prepare HTML table
    table_rows = ""
    for emp in employees_data:
        allocation = emp.total_allocation or 0
        allocation_class = ""
        
        if allocation > 100:
            allocation_class = "color: red; font-weight: bold;"
        elif allocation > 80:
            allocation_class = "color: orange; font-weight: bold;"
        elif allocation < 50 and allocation > 0:
            allocation_class = "color: blue;"
        
        table_rows += f"""
            <tr>
                <td>{emp.employee_name}</td>
                <td>{emp.department or ''}</td>
                <td>{emp.assignment_count or 0}</td>
                <td style="{allocation_class}">{allocation}%</td>
            </tr>
        """
    
    html_content = f"""
        <h2>Weekly Resource Allocation Summary</h2>
        <p>Date: {today()}</p>
        
        <h3>Employee Allocation Summary</h3>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th>Employee</th>
                    <th>Department</th>
                    <th>Active Assignments</th>
                    <th>Total Allocation</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        
        <p>Please review the allocations and make necessary adjustments.</p>
        <p>This is an automated message from the Resource Management System.</p>
    """
    
    # Get recipients
    recipients = []
    cgo_emails = frappe.get_all("User", 
        filters={"role_profile_name": "CGO"},
        fields=["email"]
    )
    
    hr_manager_emails = frappe.get_all("User",
        filters={"role_profile_name": "HR Manager"},
        fields=["email"]
    )
    
    recipients = [u.email for u in cgo_emails + hr_manager_emails]
    
    # Send email
    if recipients:
        try:
            frappe.sendmail(
                recipients=recipients,
                subject="Weekly Resource Allocation Summary",
                message=html_content
            )
        except Exception as e:
            frappe.log_error(
                f"Failed to send weekly allocation summary: {str(e)}",
                "Resource Allocation Summary Error"
            )

def generate_monthly_resource_report():
    """Generate monthly resource allocation report"""
    # This will be scheduled to run automatically every month
    month_name = getdate(today()).strftime("%B %Y")
    
    try:
        # Generate report
        report = frappe.get_doc({
            "doctype": "Prepared Report",
            "report_name": f"Resource Allocation Status - {month_name}",
            "ref_report_doctype": "Resource Allocation Status",
            "report_type": "Script Report",
            "filters_json": f'{{"from_date":"{add_days(today(), -30)}", "to_date":"{today()}"}}',
        })
        
        report.insert()
        
        # Notify relevant users
        recipients = []
        cgo_emails = frappe.get_all("User", 
            filters={"role_profile_name": "CGO"},
            fields=["email"]
        )
        
        hr_manager_emails = frappe.get_all("User",
            filters={"role_profile_name": "HR Manager"},
            fields=["email"]
        )
        
        recipients = [u.email for u in cgo_emails + hr_manager_emails]
        
        if recipients:
            frappe.sendmail(
                recipients=recipients,
                subject=f"Monthly Resource Allocation Report - {month_name}",
                message=f"""
                    <p>Hello,</p>
                    <p>The monthly resource allocation report for {month_name} has been generated.</p>
                    <p>You can access the report by clicking on the following link:</p>
                    <p><a href="/app/prepared-report/{report.name}">{report.report_name}</a></p>
                    <p>Regards,<br>Resource Management System</p>
                """
            )
    
    except Exception as e:
        frappe.log_error(
            f"Failed to generate monthly resource report: {str(e)}",
            "Resource Report Generation Error"
        )
