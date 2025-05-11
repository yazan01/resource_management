// Copyright (c) 2023, Yazan Hamdan and contributors
// For license information, please see license.txt

frappe.query_reports["Resource Allocation Status"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 0
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), 3),
            "reqd": 0
        },
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee"
        },
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "Project"
        },
        {
            "fieldname": "department",
            "label": __("Department"),
            "fieldtype": "Link",
            "options": "Department"
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            "options": "\nActive\nCompleted\nCancelled"
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        // Add color to status field
        if (column.fieldname == "status") {
            if (data.status == "Active") {
                value = "<span style='color:green'>" + value + "</span>";
            } else if (data.status == "Completed") {
                value = "<span style='color:blue'>" + value + "</span>";
            } else if (data.status == "Cancelled") {
                value = "<span style='color:red'>" + value + "</span>";
            }
        }
        
        // Highlight rows with low remaining days
        if (column.fieldname == "remaining_days" && data.status == "Active") {
            if (data.remaining_days <= 7) {
                value = "<span style='color:red; font-weight:bold'>" + value + "</span>";
            } else if (data.remaining_days <= 14) {
                value = "<span style='color:orange; font-weight:bold'>" + value + "</span>";
            }
        }
        
        // Add progress bar for allocation percentage
        if (column.fieldname == "allocation_percentage") {
            let percentage = data.allocation_percentage || 0;
            let progressBar = `
                <div class="progress" style="margin-bottom: 0; height: 12px;">
                    <div class="progress-bar" role="progressbar" 
                        aria-valuenow="${percentage}" 
                        aria-valuemin="0" 
                        aria-valuemax="100" 
                        style="width: ${percentage}%; background-color: ${percentage > 80 ? '#ff5858' : '#5e64ff'};">
                        ${percentage}%
                    </div>
                </div>
            `;
            value = progressBar;
        }
        
        return value;
    }
};
