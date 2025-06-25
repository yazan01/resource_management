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
        frappe.user.has
