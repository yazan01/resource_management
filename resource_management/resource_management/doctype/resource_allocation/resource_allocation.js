// Copyright (c) 2023, Yazan Hamdan and contributors
// For license information, please see license.txt

frappe.ui.form.on('Resource Allocation', {
    refresh: function(frm) {
        // Show approve/reject buttons for requested allocations
        if (frm.doc.status === "Requested" && !frm.doc.__islocal) {
            frm.add_custom_button(__('Approve'), function() {
                approve_request(frm);
            }, __('Actions'));
            
            frm.add_custom_button(__('Reject'), function() {
                reject_request(frm);
            }, __('Actions'));
        }
        
        // Set field permissions based on status
        if (frm.doc.status === "Approved" || frm.doc.status === "Rejected") {
            frm.set_df_property('employee', 'read_only', 1);
            frm.set_df_property('project', 'read_only', 1);
            frm.set_df_property('start_date', 'read_only', 1);
            frm.set_df_property('end_date', 'read_only', 1);
            frm.set_df_property('allocation_percentage', 'read_only', 1);
        }
    },
    
    employee: function(frm) {
        if (frm.doc.employee) {
            // Get employee hourly rate
            frappe.db.get_value('Employee', frm.doc.employee, 'hourly_cost_rate', function(r) {
                if (r && r.hourly_cost_rate) {
                    frm.set_value('hourly_cost_rate', r.hourly_cost_rate);
                }
            });
            
            // Check employee availability
            check_employee_availability(frm);
        }
    },
    
    project: function(frm) {
        // Additional actions when project changes
    },
    
    start_date: function(frm) {
        validate_dates(frm);
        check_employee_availability(frm);
        calculate_estimated_cost(frm);
    },
    
    end_date: function(frm) {
        validate_dates(frm);
        check_employee_availability(frm);
        calculate_estimated_cost(frm);
    },
    
    allocation_percentage: function(frm) {
        check_employee_availability(frm);
        calculate_estimated_cost(frm);
    },
    
    hourly_cost_rate: function(frm) {
        calculate_estimated_cost(frm);
    }
});

function approve_request(frm) {
    frappe.confirm(
        __('Are you sure you want to approve this resource allocation?'),
        function() {
            frappe.call({
                method: "resource_management.api.resource_allocation.approve_request",
                args: {
                    name: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__("Resource Allocation approved successfully"));
                        frm.refresh();
                    }
                }
            });
        }
    );
}

function reject_request(frm) {
    frappe.prompt([
        {
            fieldname: 'rejection_reason',
            label: __('Reason for Rejection'),
            fieldtype: 'Small Text',
            reqd: 1
        }
    ],
    function(values) {
        frappe.call({
            method: "resource_management.api.resource_allocation.reject_request",
            args: {
                name: frm.doc.name,
                rejection_reason: values.rejection_reason
            },
            callback: function(r) {
                if (r.message) {
                    frappe.msgprint(__("Resource Allocation rejected"));
                    frm.refresh();
                }
            }
        });
    },
    __('Reject Resource Allocation'),
    __('Reject')
    );
}

function validate_dates(frm) {
    if (frm.doc.start_date && frm.doc.end_date) {
        if (frm.doc.end_date < frm.doc.start_date) {
            frappe.msgprint(__("End Date cannot be before Start Date"));
            frm.set_value('end_date', '');
        }
    }
}

function check_employee_availability(frm) {
    if (frm.doc.employee && frm.doc.start_date && frm.doc.end_date && frm.doc.allocation_percentage) {
        frappe.call({
            method: "resource_management.api.resource_allocation.get_employee_allocations",
            args: {
                employee: frm.doc.employee,
                start_date: frm.doc.start_date,
                end_date: frm.doc.end_date,
                allocation_percentage: frm.doc.allocation_percentage,
                current_allocation: frm.doc.name || ""
            },
            callback: function(r) {
                if (r.message) {
                    // Display current allocations
                    let allocations = r.message.allocations;
                    let total_allocation = r.message.total_allocation;
                    let available_allocation = r.message.available_allocation;
                    
                    if (total_allocation + frm.doc.allocation_percentage > 100) {
                        frappe.msgprint(__("Warning: Employee is already allocated {0}%. Adding {1}% will exceed 100%.", 
                            [total_allocation, frm.doc.allocation_percentage]));
                    }
                }
            }
        });
    }
}

function calculate_estimated_cost(frm) {
    if (frm.doc.start_date && frm.doc.end_date && frm.doc.allocation_percentage && frm.doc.hourly_cost_rate) {
        // Calculate days between start and end date
        let start_date = frappe.datetime.str_to_obj(frm.doc.start_date);
        let end_date = frappe.datetime.str_to_obj(frm.doc.end_date);
        let diff_days = frappe.datetime.get_diff(end_date, start_date) + 1;
        
        // Calculate working hours (8 hours per day)
        let working_hours = diff_days * 8;
        
        // Calculate allocated hours based on percentage
        let allocated_hours = working_hours * (frm.doc.allocation_percentage / 100);
        
        // Calculate estimated cost
        let estimated_cost = allocated_hours * frm.doc.hourly_cost_rate;
        
        frm.set_value('estimated_total_cost', estimated_cost);
    }
}