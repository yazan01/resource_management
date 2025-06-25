// Copyright (c) 2023, Yazan Hamdan and contributors
// For license information, please see license.txt

frappe.listview_settings['Resource Allocation'] = {
	add_fields: ["status", "start_date", "end_date", "employee_name", "project_name", "requested_by", "allocation_percentage"],
	
	get_indicator: function(doc) {
		var today = frappe.datetime.get_today();
		
		if (doc.status === "Draft") {
			return [__("Draft"), "gray", "status,=,Draft"];
		} else if (doc.status === "Requested") {
			return [__("Pending Approval"), "orange", "status,=,Requested"];
		} else if (doc.status === "Approved") {
			// Check if allocation is current, future, or past
			if (doc.start_date > today) {
				return [__("Approved - Upcoming"), "blue", "status,=,Approved"];
			} else if (doc.end_date < today) {
				return [__("Approved - Completed"), "green", "status,=,Approved"];
			} else {
				return [__("Approved - Active"), "green", "status,=,Approved"];
			}
		} else if (doc.status === "Rejected") {
			return [__("Rejected"), "red", "status,=,Rejected"];
		}
		
		return [__(doc.status), "gray", "status,=," + doc.status];
	},
	
	// Add buttons based on user role and document status
	onload: function(listview) {
		// Add "New Request" button for employees
		if (!frappe.user.has_role('CGO')) {
			listview.page.add_action_item(__('New Request'), function() {
				frappe.new_doc('Resource Allocation');
			});
		}
		
		// Add filters for CGO to see pending requests
		if (frappe.user.has_role('CGO')) {
			listview.page.add_action_item(__('Pending Requests'), function() {
				frappe.set_route('List', 'Resource Allocation', {'status': 'Requested'});
			});
		}
	},
	
	// Add quick action buttons for CGO
	button: {
		show: function(doc) {
			return doc.status === "Requested" && frappe.user.has_role('CGO');
		},
		get_label: function() {
			return __('Quick Approve');
		},
		get_description: function(doc) {
			return __('Quick approve allocation for {0}', [doc.project_name]);
		},
		action: function(doc) {
			frappe.confirm(
				__('Are you sure you want to approve this resource allocation?<br><br><b>Project:</b> {0}<br><b>Period:</b> {1} to {2}<br><b>Allocation:</b> {3}%', 
					[doc.project_name, doc.start_date, doc.end_date, doc.allocation_percentage]),
				function() {
					frappe.call({
						method: "resource_management.api.resource_allocation.approve_request",
						args: {
							name: doc.name
						},
						callback: function(r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Resource Allocation approved successfully"),
									indicator: 'green'
								});
								cur_list.refresh();
							}
						}
					});
				}
			);
		}
	},
	
	// Format rows to show more details
	formatters: {
		project_name: function(value, df, doc) {
			return `<div>
						<div class="level-item bold">
							${value || doc.project}
						</div>
						<div class="level-item">
							<span class="text-muted">
								${doc.project}
							</span>
						</div>
					</div>`;
		},
		
		employee_name: function(value, df, doc) {
			if (!value) {
				return `<span class="text-muted">Not Selected</span>`;
			}
			return `<div>
						<div class="level-item bold">
							${value}
						</div>
						<div class="level-item">
							<span class="text-muted">
								${doc.employee || ''}
							</span>
						</div>
					</div>`;
		},
		
		allocation_percentage: function(value) {
			let color = '#5e64ff';  // Default blue
			if (value > 80) {
				color = '#ff5858';  // Red for high allocation
			} else if (value > 60) {
				color = '#ffa726';  // Orange for medium allocation
			}
			
			return `<div class="progress" style="margin-bottom: 0; height: 12px;">
						<div class="progress-bar" role="progressbar" 
							aria-valuenow="${value}" 
							aria-valuemin="0" 
							aria-valuemax="100" 
							style="width: ${value}%; background-color: ${color};">
							${value}%
						</div>
					</div>`;
		},
		
		requested_by: function(value, df, doc) {
			// Get user's full name
			return frappe.user_info(value).fullname || value;
		}
	},
	
	// Custom actions for different statuses
	primary_action: function(doc) {
		if (doc.status === "Draft" && !frappe.user.has_role('CGO')) {
			return {
				label: __('Request'),
				action: function() {
					frappe.set_route('Form', 'Resource Allocation', doc.name);
				}
			};
		} else if (doc.status === "Requested" && frappe.user.has_role('CGO')) {
			return {
				label: __('Review'),
				action: function() {
					frappe.set_route('Form', 'Resource Allocation', doc.name);
				}
			};
		}
		return null;
	},
	
	// Hide standard "Edit" option based on permissions
	hide_name_column: false,
	
	// Custom refresh to update indicators
	refresh: function(listview) {
		// Update indicators for time-based status changes
		listview.refresh();
	}
};