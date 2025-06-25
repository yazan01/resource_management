// Copyright (c) 2023, Yazan Hamdan and contributors
// For license information, please see license.txt

frappe.ui.form.on('Resource Allocation', {
    refresh: function(frm) {
        // Set default requested_by to current user
        if (frm.doc.__islocal && !frm.doc.requested_by) {
            frm.set_value('requested_by', frappe.session.user);
        }

        // Show workflow buttons based on status and user role
        setup_workflow_buttons(frm);
        
        // Set field permissions based on status
        set_field_permissions(frm);
        
        // Update available employees table when form loads
        if (frm.doc.project && frm.doc.start_date && frm.doc.end_date && frm.doc.allocation_percentage) {
            update_available_employees(frm);
        }
    },
    
    project: function(frm) {
        if (frm.doc.start_date && frm.doc.end_date && frm.doc.allocation_percentage) {
            update_available_employees(frm);
        }
    },
    
    start_date: function(frm) {
        validate_dates(frm);
        if (frm.doc.project && frm.doc.end_date && frm.doc.allocation_percentage) {
            update_available_employees(frm);
        }
    },
    
    end_date: function(frm) {
        validate_dates(frm);
        if (frm.doc.project && frm.doc.start_date && frm.doc.allocation_percentage) {
            update_available_employees(frm);
        }
    },
    
    allocation_percentage: function(frm) {
        if (frm.doc.project && frm.doc.start_date && frm.doc.end_date) {
            update_available_employees(frm);
        }
    }
});

// Child table events
frappe.ui.form.on('Resource Allocation Employee', {
    select_employee: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        // If this employee is selected, unselect all others
        if (row.select_employee) {
            frm.doc.available_employees_table.forEach(function(r) {
                if (r.name !== cdn) {
                    frappe.model.set_value(r.doctype, r.name, 'select_employee', 0);
                }
            });
            frm.refresh_field('available_employees_table');
        }
    }
});

function setup_workflow_buttons(frm) {
    // Clear existing custom buttons
    frm.clear_custom_buttons();
    
    if (frm.doc.status === "Draft" && !frm.doc.__islocal) {
        // Show Request button for draft status
        frm.add_custom_button(__('Request'), function() {
            request_allocation(frm);
        }, __('Actions'));
        frm.change_custom_button_type('Request', null, 'primary');
    }
    
    // Show approve/reject buttons for CGO role when status is Requested
    if (frm.doc.status === "Requested" && !frm.doc.__islocal && 
        frappe.user.has_role('CGO')) {
        
        frm.add_custom_button(__('Approve'), function() {
            approve_request(frm);
        }, __('Actions'));
        
        frm.add_custom_button(__('Reject'), function() {
            reject_request(frm);
        }, __('Actions'));
        
        frm.change_custom_button_type('Approve', null, 'primary');
        frm.change_custom_button_type('Reject', null, 'danger');
    }
}

function set_field_permissions(frm) {
    // Make all fields read-only based on status and user role
    let is_editable = (frm.doc.status === "Draft" && !frappe.user.has_role('CGO'));
    
    // Project details - editable only in draft for non-CGO users
    frm.set_df_property('project', 'read_only', !is_editable);
    frm.set_df_property('start_date', 'read_only', !is_editable);
    frm.set_df_property('end_date', 'read_only', !is_editable);
    frm.set_df_property('allocation_percentage', 'read_only', !is_editable);
    
    // Request details are always read-only
    frm.set_df_property('requested_by', 'read_only', 1);
    frm.set_df_property('request_date', 'read_only', 1);
    
    // Status is read-only for employees, editable for CGO
    frm.set_df_property('status', 'read_only', !frappe.user.has_role('CGO'));
    
    // Notes editable only in draft or by CGO
    frm.set_df_property('notes', 'read_only', 
        !(frm.doc.status === "Draft" || frappe.user.has_role('CGO')));
}

function request_allocation(frm) {
    // Validate that an employee is selected
    let selected_employees = frm.doc.available_employees_table.filter(r => r.select_employee);
    
    if (selected_employees.length === 0) {
        frappe.msgprint(__("Please select an employee from the available employees table"));
        return;
    }
    
    if (selected_employees.length > 1) {
        frappe.msgprint(__("Please select only one employee"));
        return;
    }
    
    frappe.confirm(
        __('Are you sure you want to submit this resource allocation request?'),
        function() {
            frappe.call({
                method: "resource_management.api.resource_allocation.request_allocation",
                args: {
                    name: frm.doc.name,
                    selected_employee: selected_employees[0].employee
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__("Resource Allocation request submitted successfully"));
                        frm.refresh();
                    }
                }
            });
        }
    );
}

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

function update_available_employees(frm) {
    if (!frm.doc.project || !frm.doc.start_date || !frm.doc.end_date || !frm.doc.allocation_percentage) {
        return;
    }
    
    frappe.call({
        method: "resource_management.api.resource_allocation.get_available_employees",
        args: {
            project: frm.doc.project,
            start_date: frm.doc.start_date,
            end_date: frm.doc.end_date,
            allocation_percentage: frm.doc.allocation_percentage,
            current_allocation: frm.doc.name || ""
        },
        callback: function(r) {
            if (r.message) {
                // Clear existing table
                frm.clear_table('available_employees_table');
                
                // Add available employees first
                r.message.available_employees.forEach(function(emp) {
                    let row = frm.add_child('available_employees_table');
                    row.employee = emp.employee;
                    row.employee_name = emp.employee_name;
                    row.department = emp.department;
                    row.current_allocation = emp.current_allocation;
                    row.available_allocation = emp.available_allocation;
                    row.hourly_cost_rate = emp.hourly_cost_rate;
                    row.estimated_cost = emp.estimated_cost;
                    row.is_available = 1;
                });
                
                // Add unavailable employees at the end
                r.message.unavailable_employees.forEach(function(emp) {
                    let row = frm.add_child('available_employees_table');
                    row.employee = emp.employee;
                    row.employee_name = emp.employee_name;
                    row.department = emp.department;
                    row.current_allocation = emp.current_allocation;
                    row.available_allocation = emp.available_allocation;
                    row.hourly_cost_rate = emp.hourly_cost_rate;
                    row.estimated_cost = emp.estimated_cost;
                    row.is_available = 0;
                });
                
                frm.refresh_field('available_employees_table');
            }
        }
    });
}